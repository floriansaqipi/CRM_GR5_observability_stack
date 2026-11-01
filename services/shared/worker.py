"""Own one asynchronous child process and retain bounded, idempotent results."""
from collections import OrderedDict
import copy
import json
import subprocess
import sys
import threading
import time
from uuid import uuid4
from shared.model import ACTIVE, utc_now, validate_resolved
from shared.metrics import Metrics
from shared import tracing
from shared.fixed_work import ALGORITHM, assign_batches
from shared.fixed_runner import execute as execute_fixed


class Conflict(Exception):
    pass


class Worker:
    def __init__(self, service, instance=None):
        self.service = service
        self.instance = instance or service
        self.boot_id = str(uuid4())
        self.lock = threading.RLock()
        self.records = OrderedDict()
        self.active_id = None
        self.process = None
        self.processes = []
        self.thread = None
        self.closing = False
        self.metrics = Metrics()

    def start(self):
        pass

    def submit(self, run):
        validate_resolved(run, self.service)
        if run['workload'] == 'cpu_fixed':
            assignment = run.get('assignment', {})
            if not isinstance(assignment, dict):
                raise ValueError('Provide a fixed-work assignment object.')
            instances = sorted(assignment)
            if instances not in (['compute'], ['compute','compute-2']) or self.instance not in instances or \
                    assignment != assign_batches(run['settings']['batch_count'], instances) or \
                    run.get('algorithm_version') != ALGORITHM or run['settings']['duration_seconds'] != 180:
                raise ValueError('Invalid fixed-work assignment.')
            deadline = run.get('deadline_unix')
            if type(deadline) not in (int,float) or deadline > time.time()+181 or deadline < 0:
                raise ValueError('Invalid fixed-work deadline.')
        with self.lock:
            existing = self.records.get(run['id'])
            if existing:
                if any(existing.get(key) != run.get(key) for key in ('settings','workload','assignment','algorithm_version')):
                    raise Conflict('Run ID already used with different settings.')
                return copy.deepcopy(existing)
            if self.closing or self.active_id:
                raise Conflict('This worker is busy or shutting down.')
            record = copy.deepcopy(run)
            record.update(state='starting', started_at=utc_now(), finished_at=None, counters={}, rates={}, elapsed_seconds=0, error=None)
            self.records[run['id']] = record
            self.active_id = run['id']
            while len(self.records) > 100:
                self.records.popitem(last=False)
            target = (lambda run_id: execute_fixed(self, run_id)) if run['workload'] == 'cpu_fixed' else self._execute
            self.thread = threading.Thread(target=target, args=(run['id'],), daemon=True)
            self.thread.start()
            return copy.deepcopy(record)

    def _command(self, record):
        return [sys.executable, '-m', 'shared.workload_child', json.dumps(record)]

    def _execute(self, run_id):
        final = {}
        record = self.records[run_id]
        started = time.monotonic()
        with tracing.attached(record.get('_trace_context')):
            span = tracing.trace.get_tracer('cloud-lab1').start_span('worker.execute', attributes=tracing.attributes(record))
        record['_trace_context'] = tracing.carrier(span)
        self.metrics.begin(record)
        try:
            with self.lock:
                if record['state'] == 'stopping' or self.closing:
                    record['state'] = 'interrupted' if record.get('interruption_reason') else 'cancelled'
                    return
                # Exporter diagnostics go to service logs, never into the result protocol.
                process = subprocess.Popen(self._command(record), stdout=subprocess.PIPE,
                                           text=True, bufsize=1)
                self.process = process
                record['state'] = 'running'

            def read_progress():
                for line in process.stdout:
                    try:
                        message = json.loads(line)
                        with self.lock:
                            self.metrics.progress(record, message)
                            for key in ('counters', 'rates', 'elapsed_seconds'):
                                if key in message:
                                    record[key] = message[key]
                            if message.get('final'):
                                final.update(message)
                    except (ValueError, TypeError):
                        with self.lock:
                            record['error'] = line.strip()[-500:]

            reader = threading.Thread(target=read_progress, daemon=True)
            reader.start()
            deadline = time.monotonic() + record['settings']['duration_seconds'] + 3
            stop_started = None
            while process.poll() is None:
                with self.lock:
                    stop = record['state'] == 'stopping' or self.closing
                timed_out = time.monotonic() >= deadline
                if stop or timed_out:
                    if stop_started is None:
                        process.terminate()
                        stop_started = time.monotonic()
                        if timed_out and not stop:
                            record['error'] = 'Worker deadline exceeded.'
                    elif time.monotonic() - stop_started > 2:
                        process.kill()
                time.sleep(0.05)
            process.wait()
            reader.join(timeout=1)
            with self.lock:
                requested_stop = record['state'] == 'stopping' or self.closing
                record['state'] = ('interrupted' if record.get('interruption_reason') else 'cancelled') if requested_stop else final.get('state', 'failed')
                if final.get('error'):
                    record['error'] = final['error']
                if record.get('interruption_reason'):
                    record['error'] = record['interruption_reason']
                if not final and not record.get('error'):
                    record['error'] = f'Workload exited without a result (exit {process.returncode}).'
                if record['error'] == 'Worker deadline exceeded.':
                    record['state'] = 'failed'
        except Exception as exc:
            with self.lock:
                record.update(state='failed', error=f'{type(exc).__name__}: {str(exc)[:300]}')
        finally:
            with self.lock:
                if self.process is not None and self.process.poll() is None:
                    self.process.kill()
                    self.process.wait(timeout=1)
                if self.process is not None and self.process.stdout:
                    self.process.stdout.close()
                record['finished_at'] = utc_now()
                self.metrics.end_worker(record, time.monotonic() - started)
                tracing.finish_span(span, record)
                self.process = None
                self.active_id = None

    def stop(self, run_id, reason=None):
        with self.lock:
            record = self.records.get(run_id)
            if record is None:
                raise KeyError(run_id)
            if record['state'] in ACTIVE:
                record['state'] = 'stopping'
                if reason:
                    record['interruption_reason'] = reason
            return copy.deepcopy(record)

    def snapshot(self):
        with self.lock:
            return {'service': self.instance, 'boot_id': self.boot_id,
                    'process_count': sum(p.poll() is None for p in self.processes) + int(self.process is not None and self.process.poll() is None),
                    'active': copy.deepcopy(self.records.get(self.active_id)),
                    'last_run': copy.deepcopy(next(reversed(self.records.values()))) if self.records else None}

    def shutdown(self):
        with self.lock:
            self.closing = True
            if self.active_id:
                self.records[self.active_id]['state'] = 'stopping'
                self.records[self.active_id]['interruption_reason'] = 'Workload service stopped during this experiment.'
            thread = self.thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=4)
