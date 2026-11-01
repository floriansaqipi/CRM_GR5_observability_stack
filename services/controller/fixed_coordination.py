"""Reconcile immutable assignments; never infer acknowledgement or replay work."""
import copy
import time
from concurrent.futures import ThreadPoolExecutor
from shared.model import ACTIVE, TERMINAL, utc_now
from shared.fixed_work import UNITS_PER_BATCH, UNIT_CHECKSUM

RESULT_FIELDS = ('state','started_at','finished_at','counters','rates','elapsed_seconds','error','batch_results')


def parallel_calls(coordinator, calls):
    def call(item):
        service, path, body = item
        try:
            return service, coordinator._http(service, path, body)
        except Exception:
            return service, None
    if not calls:
        return {}
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return dict(pool.map(call,calls))


def combine(record, parts):
    counters, batches = {}, {}
    owners = {batch:service for service, slots in record['assignment'].items() for ids in slots for batch in ids}
    for service, part in parts.items():
        for key, value in part.get('counters', {}).items():
            counters[key] = counters.get(key,0)+value
        for batch in part.get('batch_results', []):
            batch_id = batch['batch_id']
            if owners.get(batch_id) != service or batch_id in batches:
                raise ValueError('Invalid or duplicate batch ownership in worker results.')
            batches[batch_id] = copy.deepcopy(batch)
    elapsed = max((p.get('elapsed_seconds',0) for p in parts.values()), default=0)
    record.update(counters=counters,batch_results=sorted(batches.values(),key=lambda b:b['batch_id']),
                  instance_results=copy.deepcopy(parts),elapsed_seconds=round(elapsed,3),
                  rates={'cpu_batches_per_second':round(counters.get('cpu_batches',0)/max(elapsed,.001),3)})
    starts = [p['started_at'] for p in parts.values() if p.get('started_at')]
    if starts:
        record['started_at'] = min(starts)


def advance(coordinator, record, states):
    run_id, targets = record['id'], record['target_services']
    parts = record.setdefault('instance_results', {})
    calls, unknown = [], False
    stop_requested = record['state'] == 'stopping'
    for service in targets:
        snapshot = states.get(service)
        if snapshot is None:
            unknown = True
            continue
        match = snapshot['active'] or snapshot['last_run']
        if (run_id,service) in coordinator.sent:
            if match and match['id'] == run_id:
                parts[service] = {key:copy.deepcopy(match.get(key, [] if key == 'batch_results' else None)) for key in RESULT_FIELDS}
            else:
                previous = parts.get(service, {})
                parts[service] = {**previous,'state':'interrupted','error':'Worker lost the assigned run; it was not replayed.'}
        elif stop_requested:
            parts[service] = {'state':'cancelled','counters':{},'batch_results':[]}
        else:
            # Mark before sending: a missing response is reconciled, never retried.
            coordinator.sent.add((run_id,service))
            coordinator.dispatched.add(run_id)
            calls.append((service,'/internal/runs',record))
    parallel_calls(coordinator,calls)
    if not stop_requested and not record.get('_failure') and any(p.get('state')=='running' for p in parts.values()):
        record['state'] = 'running'
    failure = next(((p['state'],p.get('error')) for p in parts.values() if p.get('state') in ('failed','interrupted')),None)
    if failure:
        record['_failure'] = failure
    if time.time() >= record['deadline_unix']:
        record['_failure'] = ('failed','Fixed-work safety deadline exceeded.')
    if stop_requested or record.get('_failure'):
        stop_calls = []
        for service in targets:
            if service in states and parts.get(service,{}).get('state') in ACTIVE:
                stop_calls.append((service,f'/internal/runs/{run_id}/stop',{'_trace_context':record.get('_trace_context',{})}))
        parallel_calls(coordinator,stop_calls)
        record['state'] = 'stopping'
    try:
        combine(record,parts)
    except ValueError as exc:
        record['_failure'] = ('failed',str(exc))
        record['state'] = 'stopping'
    if unknown:
        record['error'] = 'A participating worker is unreachable; waiting to reconcile its result.'
    if not unknown and len(parts) == len(targets) and all(p.get('state') in TERMINAL for p in parts.values()):
        if record.get('_failure'):
            state,error = record['_failure']
        elif all(p.get('state')=='completed' for p in parts.values()):
            counters = record['counters']
            valid = (len(record['batch_results']) == record['settings']['batch_count'] and
                     all(b['state'] == 'completed' for b in record['batch_results']) and
                     counters.get('cpu_batches') == record['settings']['batch_count']*UNITS_PER_BATCH and
                     counters.get('checksum') == counters['cpu_batches']*UNIT_CHECKSUM)
            state,error = ('completed',None) if valid else ('failed','Fixed-work results did not match the complete assignment.')
        elif stop_requested:
            state,error = 'cancelled',None
        else:
            state,error = 'failed','A calculation participant stopped without completing its assignment.'
        coordinator._finish(record,state,error)
        coordinator.sent.difference_update((run_id,service) for service in targets)


def recover(coordinator, states):
    """Keep saved terminal results; reconstruct only results not yet persisted."""
    groups = {}
    stop_calls = []
    for service, snapshot in states.items():
        match = snapshot['active'] or snapshot['last_run']
        if not match:
            continue
        groups.setdefault(match['id'], {})[service] = match
        if snapshot['active']:
            coordinator.orphans.add(match['id'])
            stop_calls.append((service,f"/internal/runs/{match['id']}/stop",{'reason':'Controller restarted during this experiment.'}))
    parallel_calls(coordinator,stop_calls)
    for run_id, parts in groups.items():
        base = coordinator.records.get(run_id)
        stored = None
        if coordinator.repo.available:
            try:
                stored = coordinator.repo.get(run_id)
            except Exception:
                pass
        if stored and stored['state'] in TERMINAL and run_id not in coordinator.orphans:
            continue
        record = copy.deepcopy(base or stored or next(iter(parts.values())))
        if record['workload'] == 'cpu_fixed':
            merged = {**record.get('instance_results',{}),**{s:{k:copy.deepcopy(p.get(k,[] if k=='batch_results' else None)) for k in RESULT_FIELDS} for s,p in parts.items()}}
            combine(record,merged)
            complete = len(merged) == len(record['target_services']) and all(p['state']=='completed' for p in merged.values())
        else:
            record.update({k:copy.deepcopy(v) for k,v in next(iter(parts.values())).items() if k in RESULT_FIELDS})
            complete = record['state'] in TERMINAL
        if stop_calls:
            record['state'] = 'stopping'
        elif run_id in coordinator.orphans or not complete:
            record.update(state='interrupted',finished_at=utc_now(),error='Controller restarted during this experiment; work was not replayed.')
        elif record['workload'] == 'cpu_fixed':
            record.update(state='completed',finished_at=max(p.get('finished_at') or utc_now() for p in parts.values()),error=None)
        coordinator._remember(record)
    if not stop_calls:
        coordinator.recovering = False
        coordinator.ready = True
