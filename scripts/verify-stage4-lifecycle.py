"""Final live regression: exact replica metrics, seven-service mode and persistence."""
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime
from lab_api import ROOT, api, wait_for, ready, result, start, prom, document_count

spec = importlib.util.spec_from_file_location('stage3_helpers', Path(__file__).with_name('verify-stage3.py'))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
out = ROOT/'docs/evidence/stage4'
checks, runs = {}, {}


def check(name, condition):
    checks[name] = bool(condition)
    (out/'lifecycle.json').write_text(json.dumps({'checks': checks, 'runs': runs}, indent=2))
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)
    if not condition:
        raise AssertionError(name)


def script(name, *arguments):
    process = subprocess.run(['pwsh', '-NoProfile', '-File', str(ROOT/'scripts'/name), *arguments],
                             cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    with (out/'final-lifecycle-startup.txt').open('a', encoding='utf-8') as stream:
        stream.write(process.stdout)
    if process.returncode:
        raise RuntimeError(process.stdout[-3000:])


def running_services():
    output = subprocess.check_output(['docker', 'compose', '--profile', 'replica', '--profile', 'tracing',
                                      'ps', '--services', '--status', 'running'], cwd=ROOT, text=True)
    return [line for line in output.splitlines() if line.strip()]


def verify_restart(saved, combined):
    check('normal_shutdown_stops_all_profiles', not running_services())
    script('start.ps1', '-NoBuild')
    wait_for(ready)
    check('normal_restart_restores_baseline_tracing', api('/api/deployment')['preset'] == 'baseline' and
          api('/api/deployment')['tracing'] and api('/api/deployment')['verified'] and len(running_services()) == 9)
    check('stage4_run_survives_stop_start', api('/api/runs/'+combined['id'])['state'] == 'completed' and
          api('/api/runs/'+saved['id'])['batch_results'] == saved['batch_results'])
    check('stage4_trace_survives_stop_start', bool(helpers.trace_data(combined['trace_id'])))
    timestamp = datetime.fromisoformat(combined['finished_at']).timestamp()
    samples = prom('lab_workload_operations_total{service="data",workload="combined",operation="network_request",outcome="success"}', timestamp)
    check('stage4_metrics_survive_stop_start', bool(samples) and float(samples[0]['value'][1]) > 0)
    check('final_no_active_or_unsaved_runs', api('/api/runs/active')['run'] is None and api('/api/workloads')['unsaved_count'] == 0)


def main():
    wait_for(ready)
    check('replica_metric_check_configuration', api('/api/deployment')['preset'] == 'replica-2')
    browser = api('/api/runs?q=Stage%204%20browser&page_size=100')['items']
    (out/'browser-runs.json').write_text(json.dumps(browser, indent=2))
    row = list(csv.DictReader((out/'browser-export.csv').read_text().splitlines()))
    saved = next(run for run in browser if run['name'] == 'Stage 4 browser comparison')
    check('browser_csv_matches_saved_run', len(row) == 1 and row[0]['id'] == saved['id'] and
          json.loads(row[0]['batch_results']) == saved['batch_results'] and
          json.loads(row[0]['deployment']) == saved['deployment'])
    before = {service: helpers.samples(service) for service in ('compute', 'compute-2', 'controller')}
    run = api('/api/runs', {'workload': 'cpu_fixed', 'overrides': {'batch_count': 4},
                           'name': 'Stage 4 exact replica metric deltas'}, 202)
    began = time.monotonic()
    api('/health')
    check('fixed_work_health_under_one_second', time.monotonic()-began < 1)
    runs['fixed'] = run = result(run['id'])
    check('metric_check_completed', run['state'] == 'completed')
    wait_for(lambda: api('/api/runs/'+run['id'])['persistence'] == 'saved')
    for service in ('compute', 'compute-2'):
        after = helpers.samples(service)
        for operation, key in (('cpu_batch', 'cpu_batches'), ('logical_batch', 'fixed_batches')):
            labels = dict(workload='cpu_fixed', operation=operation, outcome='success')
            delta = helpers.value(after, 'lab_workload_operations_total', **labels) - helpers.value(before[service], 'lab_workload_operations_total', **labels)
            check(service+'_'+operation+'_matches_exact_run', delta == run['instance_results'][service]['counters'][key])
    labels = dict(workload='cpu_fixed', outcome='completed')
    check('controller_counts_one_parent_outcome', helpers.value(helpers.samples('controller'), 'lab_runs_total', **labels)-
          helpers.value(before['controller'], 'lab_runs_total', **labels) == 1)

    script('start.ps1', '-Preset', 'baseline', '-NoTracing', '-NoBuild')
    check('seven_service_mode', len(running_services()) == 7 and not api('/api/deployment')['tracing'])
    script('start.ps1', '-Preset', 'baseline', '-Tracing', '-NoBuild')
    wait_for(ready)
    runs['combined'] = combined = result(start('combined', duration=15, name='Stage 4 timed-workload regression')['id'])
    check('existing_combined_workload_completed', combined['state'] == 'completed' and combined['counters']['errors'] == 0)
    check('combined_has_network_and_database_work', combined['counters']['network_requests'] > 0 and
          combined['counters']['database_cycles'] > 0 and combined['counters']['allocated_mib'] == 64)
    check('temporary_documents_cleaned', document_count() == 0)
    trace = helpers.complete_trace(combined)
    (out/'combined-regression-trace.json').write_text(json.dumps(trace, indent=2))
    check('existing_connected_trace_retained', {'controller', 'compute', 'data'} == {service for service, _ in helpers.spans(trace)})
    wait_for(lambda: api('/api/runs/'+combined['id'])['persistence'] == 'saved')
    script('stop.ps1')
    verify_restart(saved, combined)


if __name__ == '__main__':
    main()
