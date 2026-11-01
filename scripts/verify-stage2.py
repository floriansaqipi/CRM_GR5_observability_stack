"""Live acceptance: real workloads, failure recovery, history, and monitoring.

This intentionally restarts lab containers. Run without other experiments active.
"""
import csv
from datetime import datetime, timezone
import io
import json
import subprocess
import time
import urllib.request
from lab_api import ROOT, BASE, api, compose, document_count, prom, ready, result, start, stop, wait_for

OUTPUT = ROOT / 'docs/evidence/stage2'
CHECKS, RUNS, SAMPLES = {}, [], []
dashboard = json.loads((ROOT / 'monitoring/grafana/dashboards/container-resources.json').read_text(encoding='utf-8'))


def check(name, condition):
    CHECKS[name] = bool(condition)
    print(f'{"PASS" if condition else "FAIL"}: {name}', flush=True)
    if not condition:
        raise AssertionError(name)


def sample(kind, phase):
    service = 'compute' if kind == 'cpu' else 'data'
    row = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'phase': phase, 'service': service}
    for key, panel in zip(('cpu_cores','memory_mib','receive_bps','transmit_bps'), dashboard['panels'][1:]):
        values = prom(panel['targets'][0]['expr'].replace('$service', service))
        if len(values) == 1:
            row[key] = float(values[0]['value'][1])
    SAMPLES.append(row)
    return row


def exercise(kind, profile='medium', duration=15, **extra):
    name = f'Verification: {kind} {profile}'
    before = time.monotonic()
    run = start(kind, profile, duration, name=name, notes='Stage 2 live acceptance; real measurements.', **extra)
    CHECKS['start_returns_promptly'] = CHECKS.get('start_returns_promptly', True) and time.monotonic() - before < 1
    while True:
        run = api('/api/runs/' + run['id'])
        sample(kind, name)
        if run['state'] not in ('starting','running','stopping'):
            break
        time.sleep(3)
    check(f'{kind}_{profile}_completes', run['state'] == 'completed' and run['counters'].get('errors') == 0)
    run = wait_for(lambda: (r if (r := api('/api/runs/' + run['id']))['persistence'] == 'saved' else None), 10)
    RUNS.append(run)
    return run


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    wait_for(ready, 30)
    check('no_other_experiment_active', api('/api/runs/active')['run'] is None)
    for body in [{'workload':'cpu','duration_seconds':181}, {'workload':'memory','overrides':{'memory_mib':129}},
                 {'workload':'network','overrides':{'payload_kib':1025}}]:
        api('/api/runs', body, 400)
    check('invalid_inputs_rejected', True)
    low = exercise('cpu', 'low', 35)
    high = exercise('cpu', 'high', 35)
    low_samples = [r['cpu_cores'] for r in SAMPLES if r['phase'] == 'Verification: cpu low'][-3:]
    high_samples = [r['cpu_cores'] for r in SAMPLES if r['phase'] == 'Verification: cpu high'][-3:]
    check('cpu_intensities_distinct', sum(high_samples)/len(high_samples) > sum(low_samples)/len(low_samples) + 0.3)
    baseline = sample('memory', 'Data idle baseline').get('memory_mib', 0)
    memory = exercise('memory')
    peak = max(r.get('memory_mib', 0) for r in SAMPLES if r['phase'] == 'Verification: memory medium')
    check('memory_rises', peak > baseline + 48)
    time.sleep(10)
    recovered = sample('memory', 'Memory cooldown')['memory_mib']
    check('memory_releases', recovered < baseline + 24)
    network = exercise('network')
    check('network_real_bytes', network['counters']['network_bytes'] > 1024*1024 and network['counters']['network_requests'] > 5)
    check('network_visible_in_prometheus', max(r.get('receive_bps',0) for r in SAMPLES if r['phase']=='Verification: network medium') > 100000)
    database = exercise('database', 'high', 15, overrides={'rate_per_second':20})
    check('database_real_write_read_pairs', database['counters']['database_cycles'] > 10 and database['counters']['database_reads'] == database['counters']['database_writes'])
    check('database_documents_cleaned', document_count(database['id']) == 0)
    combined = exercise('combined')
    check('combined_all_components', combined['counters']['allocated_mib'] == 64 and combined['counters']['network_requests'] > 0 and combined['counters']['database_cycles'] > 0)
    check('combined_documents_cleaned', document_count(combined['id']) == 0)
    active = start('combined', duration=60, name='Verification: cancel combined')
    wait_for(lambda: api('/api/runs/'+active['id'])['counters'].get('database_cycles',0)>0)
    api('/api/runs', {'workload':'cpu'}, 409)
    check('overlap_rejected', True)
    health_start = time.monotonic()
    check('health_during_work', api('/health')['status']=='ok' and time.monotonic()-health_start<1)
    # Duplicate the internal command for this same run, then check one child remains.
    command = 'import requests,json; r=json.loads(' + repr(json.dumps(active)) + '); print(requests.post("http://data:5000/internal/runs",json=r,timeout=2).status_code)'
    before = subprocess.check_output(['docker','top','cloud-lab1-data-1','-eo','pid,args'], text=True)
    status = subprocess.check_output(['docker','compose','exec','-T','controller','python','-c',command], cwd=ROOT, text=True)
    after = subprocess.check_output(['docker','top','cloud-lab1-data-1','-eo','pid,args'], text=True)
    child_before = [line.split()[0] for line in before.splitlines() if 'shared.workload_child' in line]
    child_after = [line.split()[0] for line in after.splitlines() if 'shared.workload_child' in line]
    check('duplicate_internal_start_is_idempotent', status.strip()=='202' and len(child_before)==1 and child_before==child_after)
    began = time.monotonic()
    cancelled = stop(active['id'])
    check('stop_within_five_seconds', time.monotonic()-began<5 and cancelled['state']=='cancelled')
    api('/api/runs/'+active['id']+'/stop', {}, 202)
    check('cancel_preserves_partial_counts', cancelled['counters']['database_cycles']>0)
    wait_for(lambda: document_count(active['id'])==0, 8)
    check('cancel_cleans_documents', True)
    RUNS.append(cancelled)
    for service in ('controller','data'):
        active = start('memory', duration=60, name=f'Verification: {service} restart')
        wait_for(lambda: api('/api/runs/'+active['id'])['counters'].get('allocated_mib',0)>0)
        compose('restart', service)
        wait_for(ready, 30)
        interrupted = result(active['id'], 15)
        check(service+'_restart_interrupts_without_retry', interrupted['state']=='interrupted')
        RUNS.append(interrupted)
    compose('stop','mongodb')
    wait_for(lambda: not api('/api/workloads')['storage_available'], 10)
    catalog = api('/api/workloads')
    check('database_workloads_disabled_when_offline', all(not w['available'] for w in catalog['workloads'] if w['id'] in ('database','combined')))
    api('/api/runs', {'workload':'database'}, 503)
    unsaved = []
    for kind in ('cpu','memory','network'):
        run = start(kind, name='Verification: MongoDB offline '+kind)
        counter = {'cpu':'cpu_batches','memory':'allocated_mib','network':'network_requests'}[kind]
        wait_for(lambda: api('/api/runs/'+run['id'])['counters'].get(counter,0)>0)
        run = stop(run['id'])
        check(kind+'_works_without_database', run['state']=='cancelled' and run['persistence']=='pending')
        unsaved.append(run['id'])
        RUNS.append(run)
    with urllib.request.urlopen(BASE+'/api/runs/export.csv') as response:
        offline_csv = response.read().decode()
    check('pending_runs_exportable', all(run_id in offline_csv for run_id in unsaved))
    compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','mongodb')
    wait_for(lambda: api('/api/workloads')['storage_available'] and api('/api/workloads')['unsaved_count']==0, 20)
    check('pending_history_saved_after_reconnect', all(api('/api/runs/'+run_id)['persistence']=='saved' for run_id in unsaved))
    compose('stop','data')
    wait_for(lambda: not api('/api/workloads')['workers']['data'], 10)
    api('/api/runs', {'workload':'cpu'}, 503)
    check('unknown_worker_state_blocks_new_runs', True)
    compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','data')
    wait_for(ready, 20)
    timestamp = time.time()-10
    historical = prom('up{job="cadvisor"}', timestamp)
    compose('down','--timeout','10')
    compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180')
    wait_for(ready, 30)
    check('historical_metrics_survive_full_restart', historical==prom('up{job="cadvisor"}', timestamp))
    check('saved_history_survives_full_restart', api('/api/runs/'+database['id'])['state']=='completed')
    with urllib.request.urlopen(BASE+'/api/runs/export.csv') as response:
        csv_text = response.read().decode()
    (OUTPUT/'experiment-history.csv').write_text(csv_text,encoding='utf-8')
    rows = {row['id']:row for row in csv.DictReader(io.StringIO(csv_text))}
    check('csv_matches_actual_result', json.loads(rows[database['id']]['counters'])==database['counters'] and json.loads(rows[database['id']]['settings'])==database['settings'])
    services = prom('count by (service) (container_memory_working_set_bytes{project="cloud-lab1",service!=""})')
    check('seven_services_in_prometheus', {'controller','data','compute','mongodb','cadvisor','prometheus','grafana'} <= {r['metric']['service'] for r in services})
    check('all_starts_prompt', CHECKS['start_returns_promptly'])


if __name__=='__main__':
    try:
        main()
    finally:
        OUTPUT.mkdir(parents=True,exist_ok=True)
        (OUTPUT/'acceptance.json').write_text(json.dumps({'recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':CHECKS,'runs':RUNS,'samples':SAMPLES},indent=2)+'\n',encoding='utf-8')
