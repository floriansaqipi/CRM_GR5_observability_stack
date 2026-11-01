"""Live checks against real containers; includes bounded, reversible outages."""
import base64
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from lab_api import ROOT, api, wait_for, ready, start, result, stop, prom, compose, document_count

EVIDENCE = ROOT / 'docs/evidence/stage3'
EVIDENCE.mkdir(parents=True, exist_ok=True)
checks, runs, measurements = {}, {}, {}
os.environ['LAB_TRACING_ENABLED'] = 'true'


def check(name, condition):
    checks[name] = bool(condition)
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)
    if not condition:
        raise AssertionError(name)


def internal(url):
    code = 'import urllib.request; print(urllib.request.urlopen(' + repr(url) + ', timeout=5).read().decode())'
    return subprocess.check_output(['docker', 'compose', 'exec', '-T', 'controller', 'python', '-c', code],
                                   cwd=ROOT, text=True, timeout=12)


def samples(service):
    code = ("import json,urllib.request; from prometheus_client.parser import text_string_to_metric_families; "
            f"body=urllib.request.urlopen('http://{service}:5000/metrics').read().decode(); "
            "print(json.dumps([{'name':s.name,'labels':s.labels,'value':s.value} "
            "for f in text_string_to_metric_families(body) for s in f.samples]))")
    return json.loads(subprocess.check_output(['docker', 'compose', 'exec', '-T', 'controller', 'python', '-c', code],
                                             cwd=ROOT, text=True, timeout=12))


def value(rows, name, **labels):
    return sum(s['value'] for s in rows if s['name'] == name and all(s['labels'].get(k) == v for k, v in labels.items()))


def grafana(path):
    settings = dict(line.split('=', 1) for line in (ROOT/'.env').read_text().splitlines()
                    if '=' in line and not line.startswith('#'))
    auth = base64.b64encode((settings['GRAFANA_ADMIN_USER'] + ':' + settings['GRAFANA_ADMIN_PASSWORD']).encode()).decode()
    request = urllib.request.Request('http://127.0.0.1:3000' + path,
                                     headers={'Authorization': 'Basic ' + auth, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def trace_data(trace_id):
    try:
        return grafana('/api/datasources/proxy/uid/tempo/api/traces/' + trace_id)
    except Exception:
        return None


def spans(data):
    output = []
    for batch in data.get('batches', data.get('resourceSpans', [])):
        service = next(a['value']['stringValue'] for a in batch['resource']['attributes'] if a['key'] == 'service.name')
        for group in batch.get('scopeSpans', []):
            output.extend((service, span) for span in group['spans'])
    return output


def complete_trace(run):
    def fetch():
        data = trace_data(run['trace_id'])
        return data if data and any(s['name'] == 'experiment.run' for _, s in spans(data)) else None
    return wait_for(fetch, 60)


def start_mode(tracing):
    command = ['pwsh', '-NoProfile', '-File', str(ROOT/'scripts/start.ps1')]
    if tracing:
        command.append('-Tracing')
    else:
        command.append('-NoTracing')
    completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
    (EVIDENCE/('startup-tracing.txt' if tracing else 'startup-metrics-only.txt')).write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(completed.stdout[-3000:])
    wait_for(ready, 45)


def main():
    wait_for(ready)
    check('tracing_mode_enabled', api('/api/workloads')['observability']['tracing_enabled'])
    check('no_active_experiment', api('/api/runs/active')['run'] is None)
    wait_for(lambda: len(prom('up{job="applications"} == 1')) == 3, 30)
    check('three_application_targets', True)
    before = samples('compute')
    code = "import urllib.request; [urllib.request.urlopen('http://compute:5000/workloads/network?size_kib=1').read() for _ in range(10)]"
    subprocess.run(['docker', 'compose', 'exec', '-T', 'controller', 'python', '-c', code], cwd=ROOT, check=True)
    after = samples('compute')
    labels = {'route': '/workloads/network', 'method': 'GET'}
    check('known_http_count_delta_10', value(after, 'lab_http_requests_total', **labels) - value(before, 'lab_http_requests_total', **labels) == 10)
    check('known_http_histogram_count_delta_10', value(after, 'lab_http_request_duration_seconds_count', **labels) - value(before, 'lab_http_request_duration_seconds_count', **labels) == 10)
    check('metrics_and_health_excluded', not any(s['labels'].get('route') in ('/health', '/metrics') for s in after))

    before, controller_before = samples('data'), samples('controller')
    begun = time.monotonic()
    run = start('combined', duration=30, name='Stage 3 connected Combined workload')
    measurements['start_response_seconds'] = time.monotonic() - begun
    check('start_returns_under_one_second', measurements['start_response_seconds'] < 1)
    begun = time.monotonic()
    api('/health')
    check('health_responsive', time.monotonic() - begun < 1)
    runs['combined'] = run = result(run['id'])
    check('combined_completed_without_errors', run['state'] == 'completed' and run['counters']['errors'] == 0)
    after = samples('data')
    for key, op in [('network_requests', 'network_request'), ('database_writes', 'database_write'),
                    ('database_reads', 'database_read'), ('database_cycles', 'database_cycle')]:
        labels = {'workload': 'combined', 'operation': op, 'outcome': 'success'}
        check(op + '_counter_matches_run', value(after, 'lab_workload_operations_total', **labels) - value(before, 'lab_workload_operations_total', **labels) == run['counters'][key])
    check('network_bytes_match_run', value(after, 'lab_workload_network_bytes_total', workload='combined') - value(before, 'lab_workload_network_bytes_total', workload='combined') == run['counters']['network_bytes'])
    check('io_histogram_covers_all_cycles', value(after, 'lab_workload_io_duration_seconds_count', workload='combined', operation='network_request', outcome='success') - value(before, 'lab_workload_io_duration_seconds_count', workload='combined', operation='network_request', outcome='success') == run['counters']['network_requests'])
    check('elapsed_resets_when_idle', value(after, 'lab_workload_elapsed_seconds', workload='combined') == 0)
    check('workload_duration_is_separate', value(after, 'lab_workload_duration_seconds_sum', workload='combined', outcome='completed') >= 30)
    time.sleep(1)
    for _ in range(3):
        api('/api/runs/' + run['id'])
    controller_after = samples('controller')
    outcome_labels = {'workload': 'combined', 'outcome': 'completed'}
    check('one_terminal_outcome_despite_repeated_reads', value(controller_after, 'lab_runs_total', **outcome_labels) - value(controller_before, 'lab_runs_total', **outcome_labels) == 1)

    data = complete_trace(run)
    (EVIDENCE/'connected-trace.json').write_text(json.dumps(data, indent=2))
    traced = spans(data)
    services = {service for service, _ in traced}
    names = Counter(s['name'] for _, s in traced)
    check('trace_spans_all_three_flask_services', services == {'controller', 'compute', 'data'})
    check('trace_has_mongodb_client_calls', any(s['name'] == 'lab.find' for _, s in traced))
    ids = {s['spanId'] for _, s in traced}
    roots = [s for _, s in traced if not s.get('parentSpanId')]
    check('trace_has_one_connected_root', len(roots) == 1 and all(not s.get('parentSpanId') or s['parentSpanId'] in ids for _, s in traced))
    check('trace_is_readable_subset', 1 <= names['workload.io_cycle'] <= 31 and names['workload.io_cycle'] < run['counters']['network_requests'])
    check('no_poll_or_probe_spans', not any('/health' in s['name'] or '/metrics' in s['name'] or '/internal/state' in s['name'] for _, s in traced))
    # PyMongo retains bare command names in db.statement even with capture_statement=False.
    commands = {'update', 'find', 'delete', 'endSessions', 'ping'}
    check('no_database_statement_or_payload_capture', all(a['value'].get('stringValue') in commands
          for _, s in traced for a in s.get('attributes', []) if a['key'] in ('db.statement', 'db.query.text')))
    measurements['connected_trace_span_counts'] = dict(names)

    # Fail real dependency calls mid-run; restore immediately afterward.
    failing = start('network', duration=30, name='Stage 3 controlled Compute outage')
    wait_for(lambda: api('/api/runs/' + failing['id'])['counters'].get('network_requests', 0) > 1)
    compose('stop', '-t', '2', 'compute')
    try:
        runs['failed_network'] = failed = result(failing['id'], 30)
        check('dependency_failure_marks_run_failed', failed['state'] == 'failed' and failed['counters']['errors'] >= 3)
    finally:
        compose('start', 'compute')
        wait_for(ready, 40)
    failed_trace = complete_trace(failed)
    (EVIDENCE/'failed-trace.json').write_text(json.dumps(failed_trace, indent=2))
    check('failed_operations_have_error_spans', any(s.get('status', {}).get('code') in ('STATUS_CODE_ERROR', 2) for _, s in spans(failed_trace)))
    check('failed_operations_counted', value(samples('data'), 'lab_workload_operations_total', workload='network', operation='network_request', outcome='error') >= 3)

    for dependency in ('otel-collector', 'tempo'):
        compose('--profile', 'tracing', 'stop', '-t', '3', dependency)
        try:
            active = start('combined', duration=30, name='Stage 3 outage: ' + dependency)
            wait_for(lambda: api('/api/runs/' + active['id'])['counters'].get('database_cycles', 0) >= 3)
            api('/health')
            begun = time.monotonic()
            runs[dependency + '_outage'] = cancelled = stop(active['id'])
            measurements[dependency + '_stop_seconds'] = time.monotonic() - begun
            check(dependency + '_outage_stop_under_five_seconds', measurements[dependency + '_stop_seconds'] < 5)
            check(dependency + '_outage_does_not_corrupt_results', cancelled['state'] == 'cancelled' and cancelled['error'] is None and cancelled['counters']['errors'] == 0)
            check(dependency + '_outage_cleans_documents', document_count(active['id']) == 0)
        finally:
            compose('--profile', 'tracing', 'start', dependency)
        wait_for(lambda: internal('http://' + ('otel-collector:13133/' if dependency == 'otel-collector' else 'tempo:3200/ready')), 40)

    # Normal stop/start must preserve history, resource measurements and the trace WAL.
    compose('--profile', 'tracing', 'down', '--timeout', '15')
    start_mode(True)
    check('saved_history_survives_restart', api('/api/runs/' + run['id'])['state'] == 'completed')
    check('connected_trace_survives_restart', bool(complete_trace(run)))
    check('all_nine_services_have_resource_series', len(prom('count by(service) (container_memory_working_set_bytes{project="cloud-lab1",service!=""})')) >= 9)
    check('previous_stage_evidence_preserved', (ROOT/'docs/evidence/stage2/acceptance.json').exists() and (ROOT/'docs/evidence/measurements.json').exists())

    start_mode(False)
    check('metrics_only_mode_disables_tracing', not api('/api/workloads')['observability']['tracing_enabled'])
    services = subprocess.check_output(['docker','compose','--profile','tracing','ps','--services','--status','running'],cwd=ROOT,text=True).splitlines()
    check('metrics_only_mode_has_seven_running_services', len(services) == 7)
    active = start('memory', duration=15, name='Stage 3 metrics-only workload')
    runs['metrics_only'] = independent = result(active['id'])
    check('metrics_only_workload_has_no_trace', independent['state'] == 'completed' and independent['trace_id'] is None)
    check('metrics_available_without_tracing', len(prom('up{job="applications"} == 1')) == 3)
    start_mode(True)
    check('tracing_mode_restored', api('/api/workloads')['observability']['tracing_enabled'])

    text = urllib.request.urlopen('http://127.0.0.1:5000/api/runs/export.csv').read().decode()
    (EVIDENCE/'experiment-history.csv').write_text(text, encoding='utf-8')
    import csv, io
    rows = list(csv.DictReader(io.StringIO(text)))
    check('csv_contains_saved_trace_association', any(row['id'] == run['id'] and row['trace_id'] == run['trace_id'] for row in rows))
    for service in ('controller', 'compute', 'data'):
        check(service + '_labels_have_no_run_ids', not any(any(v == run['id'] for v in s['labels'].values()) for s in samples(service)))
    containers = json.loads(subprocess.check_output(['docker','inspect', *subprocess.check_output(['docker','compose','--profile','tracing','ps','-q'],cwd=ROOT,text=True).split()],text=True))
    check('no_container_oom_kills', not any(c['State']['OOMKilled'] for c in containers))
    measurements['configured_memory_gib'] = sum(c['HostConfig']['Memory'] for c in containers) / 1024**3
    (EVIDENCE/'deployment.json').write_text(json.dumps([{'name':c['Name'],'memory_limit':c['HostConfig']['Memory'],'oom_killed':c['State']['OOMKilled'],'image':c['Config']['Image']} for c in containers],indent=2))


if __name__ == '__main__':
    try:
        main()
    finally:
        (EVIDENCE/'acceptance.json').write_text(json.dumps({'recorded_utc':datetime.now(timezone.utc).isoformat(),
                    'checks':checks, 'measurements':measurements, 'runs':runs}, indent=2), encoding='utf-8')
