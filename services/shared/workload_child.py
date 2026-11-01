"""Disposable workload process. JSON lines report actual progress to its owner."""
from datetime import datetime, timedelta, timezone
import json
import os
import signal
import sys
import time
import requests
from pymongo import MongoClient
from shared.io_stats import IOStats
from shared import tracing

stopping = False


def request_stop(sig, frame):
    global stopping
    stopping = True


def main(run):
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    settings, kind = run['settings'], run['workload']
    started = time.monotonic()
    deadline = started + settings['duration_seconds']
    counters = {'cpu_batches': 0, 'network_requests': 0, 'network_bytes': 0,
                'database_cycles': 0, 'database_writes': 0, 'database_reads': 0, 'errors': 0}
    client = collection = buffer = None
    session = requests.Session()
    session.trust_env = False
    last_report = 0.0
    error = None
    state = 'completed'
    stats = IOStats()
    tracer = tracing.trace.get_tracer('cloud-lab1')
    parent_context = tracing.context.get_current()
    last_detail = -1.0
    hold_span = cpu_span = None

    def report(final=False):
        nonlocal last_report
        elapsed = max(time.monotonic() - started, 0.001)
        rates = {'network_requests_per_second': round(counters['network_requests'] / elapsed, 3),
                 'database_cycles_per_second': round(counters['database_cycles'] / elapsed, 3),
                 'cpu_batches_per_second': round(counters['cpu_batches'] / elapsed, 3)}
        print(json.dumps({'counters': counters, 'rates': rates, 'elapsed_seconds': round(elapsed, 3),
                          'telemetry': stats.values,
                          **({'final': True, 'state': state, 'error': error} if final else {})}), flush=True)
        last_report = time.monotonic()

    try:
        if kind == 'cpu':
            cpu_span = tracer.start_span('cpu.calculate')
        if kind in ('memory', 'combined'):
            with tracer.start_as_current_span('memory.allocate_and_touch'):
                buffer = bytearray(settings['memory_mib'] * 1024 * 1024)
                for offset in range(0, len(buffer), 4096):
                    buffer[offset] = 1
            counters['allocated_mib'] = settings['memory_mib']
            counters['touched_pages'] = len(buffer) // 4096
            hold_span = tracer.start_span('memory.hold')
        if kind in ('database', 'combined'):
            client = MongoClient(os.environ.get('MONGO_URI', 'mongodb://mongodb:27017/lab'),
                                 serverSelectionTimeoutMS=500, connectTimeoutMS=500,
                                 socketTimeoutMS=1000, timeoutMS=1000, retryWrites=False)
            collection = client.get_default_database().workload_documents
            with tracing.suppress_instrumentation():
                client.admin.command('ping')
        report()
        next_cycle = time.monotonic()
        cycles = 0
        consecutive_errors = 0
        while not stopping and time.monotonic() < deadline:
            if kind == 'cpu':
                cycle_start = time.monotonic()
                busy_until = min(cycle_start + settings['cpu_percent'] / 1000, deadline)
                while not stopping and time.monotonic() < busy_until:
                    sum(n * n % 104729 for n in range(3000))
                    counters['cpu_batches'] += 1
                time.sleep(max(0, min(cycle_start + 0.1, deadline) - time.monotonic()))
            elif kind == 'memory':
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
            else:
                try:
                    now = time.monotonic()
                    detailed = last_detail < 0 or now - last_detail >= 1
                    if detailed:
                        last_detail = now
                    with tracing.operation_cycle(detailed, parent_context):
                        if kind in ('network', 'combined'):
                            url = os.environ.get('COMPUTE_URL', 'http://compute:5000') + '/workloads/network'
                            with stats.measure('network_request'):
                                with session.get(url, params={'size_kib': settings['payload_kib']}, timeout=(0.5, 1), stream=True) as response:
                                    response.raise_for_status()
                                    size = 0
                                    for chunk in response.iter_content(65536):
                                        if stopping or time.monotonic() > deadline:
                                            break
                                        size += len(chunk)
                                    counters['network_bytes'] += size
                                    if size == settings['payload_kib'] * 1024:
                                        counters['network_requests'] += 1
                        if collection is not None and not stopping and time.monotonic() < deadline:
                            document_id = f"{run['id']}:{cycles % 128}"
                            document = {'_id': document_id, 'run_id': run['id'], 'payload': 'x' * settings['document_kib'] * 1024,
                                        'expires_at': datetime.now(timezone.utc) + timedelta(hours=1)}
                            with stats.measure('database_write'):
                                collection.replace_one({'_id': document_id}, document, upsert=True)
                            counters['database_writes'] += 1
                            with stats.measure('database_read'):
                                found = collection.find_one({'_id': document_id})
                                if found is None or found['payload'] != document['payload']:
                                    raise RuntimeError('Database read did not match the write.')
                            counters['database_reads'] += 1
                            counters['database_cycles'] += 1
                    consecutive_errors = 0
                except Exception as exc:
                    counters['errors'] += 1
                    consecutive_errors += 1
                    error = f'{type(exc).__name__}: {str(exc)[:250]}'
                    if consecutive_errors >= 3:
                        raise RuntimeError('Three consecutive workload operations failed.') from exc
                cycles += 1
                next_cycle = max(next_cycle + 1 / settings['rate_per_second'], time.monotonic())
                while not stopping and time.monotonic() < min(next_cycle, deadline):
                    time.sleep(min(0.05, min(next_cycle, deadline) - time.monotonic()))
            if time.monotonic() - last_report >= 1:
                report()
        state = 'cancelled' if stopping else ('failed' if counters['errors'] else 'completed')
    except Exception as exc:
        state = 'cancelled' if stopping else 'failed'
        error = f'{type(exc).__name__}: {str(exc)[:350]}'
    finally:
        if cpu_span:
            cpu_span.set_attribute('lab.cpu.batches', counters['cpu_batches'])
            cpu_span.end()
        if hold_span:
            hold_span.end()
        with tracer.start_as_current_span('memory.release') if buffer is not None else tracing.suppress_instrumentation():
            buffer = None
        if collection is not None:
            try:
                with tracer.start_as_current_span('workload.cleanup'):
                    collection.delete_many({'run_id': run['id']})
            except Exception:
                counters['cleanup_pending'] = 1
        if client is not None:
            client.close()
        session.close()
        report(final=True)
        span = tracing.trace.get_current_span()
        span.set_attribute('lab.outcome', state)
        if state == 'failed':
            span.set_status(tracing.Status(tracing.StatusCode.ERROR, error))
        if state == 'cancelled':
            span.add_event('experiment.cancelled')


if __name__ == '__main__':
    run = json.loads(sys.argv[1])
    tracing.configure(os.environ.get('LAB_SERVICE', run['target_service']))
    with tracing.attached(run.get('_trace_context')):
        with tracing.trace.get_tracer('cloud-lab1').start_as_current_span('workload.run', attributes=tracing.attributes(run)):
            main(run)
    tracing.shutdown()
