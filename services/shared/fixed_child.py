"""A persistent calculation slot processes its immutable list; it spawns no children."""
import json
import os
import signal
import sys
import time
from shared.fixed_work import calculate_unit, UNITS_PER_BATCH
from shared.model import utc_now
from shared import tracing

stopping = False


def stop(sig, frame):
    global stopping
    stopping = True


def main(run, slot):
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    started, last_report = time.monotonic(), 0
    counters = {'cpu_batches': 0, 'fixed_batches': 0, 'checksum': 0, 'errors': 0}
    batches, state, error = [], 'completed', None
    tracer = tracing.trace.get_tracer('cloud-lab1')

    def report(final=False):
        nonlocal last_report
        elapsed = time.monotonic()-started
        print(json.dumps({'counters': counters, 'batch_results': batches, 'elapsed_seconds': elapsed,
                          **({'final': True, 'state': state, 'error': error} if final else {})}), flush=True)
        last_report = time.monotonic()

    try:
        for batch_id in run['assignment'][run['instance']][slot]:
            if stopping or time.time() >= run['deadline_unix']:
                break
            batch = {'batch_id': batch_id, 'instance': run['instance'], 'slot': slot, 'state': 'running',
                     'calculation_units': 0, 'checksum': 0, 'started_at': utc_now(), 'finished_at': None}
            batches.append(batch)
            with tracer.start_as_current_span('cpu.batch', attributes={'lab.batch.id': batch_id, 'lab.slot': slot, 'lab.instance':run['instance']}) as span:
                for _ in range(UNITS_PER_BATCH):
                    if stopping or time.time() >= run['deadline_unix']:
                        break
                    value = calculate_unit()
                    counters['cpu_batches'] += 1
                    counters['checksum'] += value
                    batch['calculation_units'] += 1
                    batch['checksum'] += value
                    if time.monotonic()-last_report >= 1:
                        report()
                batch['state'] = 'completed' if batch['calculation_units'] == UNITS_PER_BATCH else ('cancelled' if stopping else 'failed')
                batch['finished_at'] = utc_now()
                if batch['state'] == 'completed':
                    counters['fixed_batches'] += 1
                span.set_attribute('lab.outcome', batch['state'])
                span.set_attribute('lab.calculation_units', batch['calculation_units'])
                if batch['state'] == 'failed':
                    span.set_status(tracing.Status(tracing.StatusCode.ERROR, 'Safety deadline exceeded'))
            report()
        if stopping:
            state = 'cancelled'
        elif counters['fixed_batches'] != len(run['assignment'][run['instance']][slot]):
            state, error = 'failed', 'Fixed-work safety deadline exceeded.'
    except Exception as exc:
        state, error = 'failed', f'{type(exc).__name__}: {str(exc)[:250]}'
        counters['errors'] += 1
    finally:
        span = tracing.trace.get_current_span()
        span.set_attribute('lab.outcome', state)
        if state == 'failed':
            span.set_status(tracing.Status(tracing.StatusCode.ERROR, error))
        report(final=True)


if __name__ == '__main__':
    run, slot = json.loads(sys.argv[1]), int(sys.argv[2])
    tracing.configure(os.environ.get('LAB_SERVICE', run['instance']))
    with tracing.attached(run.get('_trace_context')):
        with tracing.trace.get_tracer('cloud-lab1').start_as_current_span('cpu.fixed_slot', attributes=tracing.attributes(run)):
            main(run, slot)
    tracing.shutdown()
