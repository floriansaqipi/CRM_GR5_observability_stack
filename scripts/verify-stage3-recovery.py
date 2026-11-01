"""Preserve trace association through controller loss and worker restart."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
from lab_api import ROOT, api, compose, ready, result, start, wait_for, prom

spec = importlib.util.spec_from_file_location('stage3_checks', Path(__file__).with_name('verify-stage3.py'))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def main():
    wait_for(ready)
    t.check('tracing_enabled', api('/api/workloads')['observability']['tracing_enabled'])
    for service in ('controller', 'data'):
        original = start('memory', duration=60, name='Stage 3 recovery: ' + service)
        wait_for(lambda: api('/api/runs/' + original['id'])['counters'].get('allocated_mib', 0) > 0)
        if service == 'controller':
            compose('kill', '--signal', 'SIGKILL', 'controller')
            compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '90', 'controller')
        else:
            compose('restart', 'data')
        wait_for(ready, 45)
        interrupted = result(original['id'], 10)
        t.runs[service] = interrupted
        t.check(service + '_restart_marks_interrupted', interrupted['state'] == 'interrupted')
        t.check(service + '_restart_preserves_trace_id', interrupted['trace_id'] == original['trace_id'])
        data = t.complete_trace(interrupted) if service == 'data' else wait_for(
            lambda: (d if (d := t.trace_data(original['trace_id'])) and
                     any(s['name'] == 'experiment.recovered' for _, s in t.spans(d)) else None), 45)
        (t.EVIDENCE/(service + '-recovery-trace.json')).write_text(json.dumps(data, indent=2))
        t.check(service + '_trace_has_interrupted_outcome', any(
            a['key'] == 'lab.outcome' and a['value'].get('stringValue') == 'interrupted'
            for _, span in t.spans(data) for a in span.get('attributes', [])))
        t.check(service + '_restart_releases_worker', api('/api/runs/active')['run'] is None)
    # An old Stage 2 sample proves the existing Prometheus volume still contains history.
    old = json.loads((ROOT/'docs/evidence/lifecycle.json').read_text())
    historical = prom(old['persistence_query'], old['persistence_sample_time'])
    t.measurements['stage1_historical_sample'] = historical
    t.check('stage1_prometheus_sample_preserved', bool(historical) and historical[0]['value'][1] == '1')


if __name__ == '__main__':
    try:
        main()
    finally:
        (t.EVIDENCE/'recovery.json').write_text(json.dumps({'recorded_utc':datetime.now(timezone.utc).isoformat(),
            'checks':t.checks,'runs':t.runs,'measurements':t.measurements}, indent=2), encoding='utf-8')
