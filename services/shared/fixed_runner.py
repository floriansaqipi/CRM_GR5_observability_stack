"""Own up to two direct subprocesses. Stop and deadlines never leave grandchildren."""
import copy
import json
import subprocess
import sys
import threading
import time
from shared.model import utc_now
from shared import tracing


def execute(worker, run_id):
    record = worker.records[run_id]
    started = time.monotonic()
    processes, readers, snapshots = [], [], {}
    failure = None
    with tracing.attached(record.get('_trace_context')):
        span = tracing.trace.get_tracer('cloud-lab1').start_span('worker.execute', attributes=tracing.attributes(record))
    record['_trace_context'] = tracing.carrier(span)
    worker.metrics.begin(record)

    def read(slot, process):
        for line in process.stdout:
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    continue
                with worker.lock:
                    snapshots[slot] = message
                    counters, results = {}, {}
                    for snapshot in snapshots.values():
                        for key, value in snapshot.get('counters', {}).items():
                            counters[key] = counters.get(key, 0)+value
                        for batch in snapshot.get('batch_results', []):
                            results[batch['batch_id']] = batch
                    elapsed = time.monotonic()-started
                    record.update(counters=counters, batch_results=sorted(results.values(), key=lambda b:b['batch_id']),
                                  elapsed_seconds=round(elapsed, 3),
                                  rates={'cpu_batches_per_second': round(counters.get('cpu_batches',0)/max(elapsed,.001),3)})
                    worker.metrics.progress(record, {'counters':counters,'elapsed_seconds':elapsed})
            except (ValueError, TypeError):
                pass
        with worker.lock:
            final = snapshots.setdefault(slot, {'counters':{},'batch_results':[]})
            if not final.get('final'):
                final.update(final=True,state='failed',error='Calculation process exited without a final result.')

    try:
        with worker.lock:
            if record['state'] != 'stopping' and not worker.closing:
                child_run = {**record, 'instance': worker.instance}
                for slot in range(len(record['assignment'][worker.instance])):
                    process = subprocess.Popen([sys.executable,'-m','shared.fixed_child',json.dumps(child_run),str(slot)],
                                               stdout=subprocess.PIPE,text=True,bufsize=1)
                    processes.append(process)
                    worker.processes = processes
                    reader = threading.Thread(target=read,args=(slot,process),daemon=True)
                    reader.start()
                    readers.append(reader)
                record['state'] = 'running'
        stop_started = None
        while any(p.poll() is None for p in processes):
            with worker.lock:
                requested_stop = record['state'] == 'stopping' or worker.closing
                if any(s.get('final') and s.get('state') == 'failed' for s in snapshots.values()):
                    failure = next(s.get('error') or 'Calculation slot failed.' for s in snapshots.values() if s.get('state') == 'failed')
                if not failure and any(p.poll() is not None and p.returncode != 0 for p in processes):
                    failure = 'Calculation process exited unexpectedly.'
            timed_out = time.time() >= record['deadline_unix']
            if requested_stop or timed_out or failure:
                if timed_out and not requested_stop:
                    failure = 'Fixed-work safety deadline exceeded.'
                if stop_started is None:
                    stop_started = time.monotonic()
                    for process in processes:
                        if process.poll() is None:
                            process.terminate()
                elif time.monotonic()-stop_started >= 2:
                    for process in processes:
                        if process.poll() is None:
                            process.kill()
            time.sleep(.02)
        for reader in readers:
            reader.join(1)
        with worker.lock:
            if record.get('interruption_reason'):
                record.update(state='interrupted',error=record['interruption_reason'])
            elif record['state'] == 'stopping' or worker.closing:
                record.update(state='cancelled',error=None)
            elif failure or len(snapshots) != len(processes) or not all(s.get('final') and s.get('state') == 'completed' for s in snapshots.values()):
                record.update(state='failed',error=failure or 'Calculation process exited without a complete result.')
            else:
                record.update(state='completed',error=None)
    except Exception as exc:
        record.update(state='failed',error=f'{type(exc).__name__}: {str(exc)[:250]}')
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()
        for reader in readers:
            reader.join(1)
        for process in processes:
            process.stdout.close()
        with worker.lock:
            record['finished_at'] = utc_now()
            worker.metrics.end_worker(record,time.monotonic()-started)
            tracing.finish_span(span,record)
            worker.processes = []
            worker.active_id = None
