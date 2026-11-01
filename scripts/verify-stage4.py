"""Real allocation/replica checks. Applies presets and performs reversible outages."""
from datetime import datetime, timezone
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from lab_api import ROOT, BASE, api, wait_for, ready, result, start, stop, prom, compose

spec=importlib.util.spec_from_file_location('stage3_helpers',Path(__file__).with_name('verify-stage3.py'))
helpers=importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
OUT=ROOT/'docs/evidence/stage4'; OUT.mkdir(exist_ok=True,parents=True)
checks, runs, deployments, measurements = {}, {}, {}, {}


def save():
    (OUT/'acceptance.json').write_text(json.dumps({'recorded_utc':datetime.now(timezone.utc).isoformat(),
        'checks':checks,'runs':runs,'deployments':deployments,'measurements':measurements},indent=2),encoding='utf-8')


def check(name, condition):
    checks[name]=bool(condition)
    print(('PASS ' if condition else 'FAIL ')+name,flush=True)
    save()
    if not condition: raise AssertionError(name)


def preset(name, tracing=None):
    script='apply-preset.ps1' if tracing is None else 'start.ps1'
    command=['pwsh','-NoProfile','-File',str(ROOT/'scripts'/script),'-Preset',name]
    if tracing is not None:
        command.extend(['-Tracing' if tracing else '-NoTracing','-NoBuild'])
    completed=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    (OUT/f'preset-{name}-{tracing}.txt').write_text(completed.stdout,encoding='utf-8')
    if completed.returncode: raise RuntimeError(completed.stdout[-4000:])
    wait_for(ready,45)
    deployment=api('/api/deployment')
    deployments[name]=deployment
    check(name+'_limits_verified',deployment['preset']==name and deployment['verified'] and not deployment['pending'])
    target_count=1+len(deployment['instances'])
    query='up{job="applications"} and (timestamp(up{job="applications"}) > time()-15)'
    wait_for(lambda:len(prom('('+query+') == 1'))==target_count,30)
    check(name+'_expected_scrapes',len(prom(query))==target_count)
    return deployment


def measured_run(kind, name, batches=32, duration=30):
    body={'workload':kind,'name':name}
    if kind=='cpu_fixed': body['overrides']={'batch_count':batches}
    else: body.update(duration_seconds=duration,overrides={'memory_mib':64})
    begun=time.monotonic(); run=api('/api/runs',body,202)
    check(name+'_start_responsive',time.monotonic()-begun<1)
    peak_cpu, peak_memory, peak_cpu_average = {}, {}, {}
    peak_processes=0
    docker_cpu=None
    while run['state'] in ('starting','running','stopping'):
        time.sleep(1)
        run=api('/api/runs/'+run['id'])
        cpu=prom('sum by(service) (irate(container_cpu_usage_seconds_total{project="cloud-lab1",cpu="total",service=~"compute|compute-2"}[30s]) and on(id) (container_last_seen{project="cloud-lab1",service=~"compute|compute-2"}>time()-15))')
        average=prom('sum by(service) (rate(container_cpu_usage_seconds_total{project="cloud-lab1",cpu="total",service=~"compute|compute-2"}[30s]) and on(id) (container_last_seen{project="cloud-lab1",service=~"compute|compute-2"}>time()-15))')
        memory=prom('max by(service) (container_memory_working_set_bytes{project="cloud-lab1",service=~"compute|compute-2|data"} and on(id) (container_last_seen{project="cloud-lab1",service=~"compute|compute-2|data"}>time()-15))')
        for row in cpu: peak_cpu[row['metric']['service']]=max(peak_cpu.get(row['metric']['service'],0),float(row['value'][1]))
        for row in average: peak_cpu_average[row['metric']['service']]=max(peak_cpu_average.get(row['metric']['service'],0),float(row['value'][1]))
        for row in memory: peak_memory[row['metric']['service']]=max(peak_memory.get(row['metric']['service'],0),float(row['value'][1]))
        if kind=='cpu_fixed' and run['state'] in ('starting','running'):
            code="import json,urllib.request; print(sum(json.load(urllib.request.urlopen('http://'+s+':5000/internal/state'))['process_count'] for s in "+repr(run['target_services'])+"))"
            peak_processes=max(peak_processes,int(subprocess.check_output(['docker','compose','exec','-T','controller','python','-c',code],cwd=ROOT,text=True)))
            if name=='cpu-2' and docker_cpu is None and run['counters'].get('cpu_batches',0)>5000:
                container=subprocess.check_output(['docker','compose','ps','-q','compute'],cwd=ROOT,text=True).strip()
                percent=subprocess.check_output(['docker','stats','--no-stream','--format','{{.CPUPerc}}',container],cwd=ROOT,text=True).strip()
                docker_cpu=float(percent.rstrip('%'))/100
    runs[name]=run
    measurements[name]={'peak_cpu_cores':peak_cpu,'peak_cpu_30s_average':peak_cpu_average,'docker_cpu_sample_cores':docker_cpu,'peak_working_set_bytes':peak_memory,'peak_calculation_processes':peak_processes}
    check(name+'_completed',run['state']=='completed')
    check(name+'_saved_preset',run['deployment']['preset']==api('/api/deployment')['preset'])
    if kind=='cpu_fixed':
        check(name+'_exact_work',run['counters']['cpu_batches']==batches*2500 and run['counters']['fixed_batches']==batches)
        check(name+'_exact_checksum',run['counters']['checksum']==batches*2500*150089160)
        check(name+'_unique_batch_ownership',len({b['batch_id'] for b in run['batch_results']})==batches and len(run['batch_results'])==batches)
        check(name+'_two_processes',peak_processes==2)
    else:
        check(name+'_same_memory_allocation',run['counters']['allocated_mib']==64 and run['elapsed_seconds']>=30)
    for service,memory in peak_memory.items():
        expected=run['deployment']['expected'].get(service)
        if expected: check(name+'_'+service+'_within_memory_limit',memory<=expected['memory_bytes'])
    return run


def write_state(state):
    path=ROOT/'.runtime/deployment.json'
    temp=path.with_suffix('.verify.tmp')
    temp.write_text(json.dumps(state),encoding='utf-8'); temp.replace(path)


def healthy():
    try: return api('/health')
    except Exception: return None


def main():
    wait_for(ready)
    check('no_active_experiment',api('/api/runs/active')['run'] is None)
    # Freeze images for every case: preset application uses --no-build.
    for name in ('cpu-05','cpu-1','cpu-2'):
        preset(name)
        measured_run('cpu_fixed',name)
    check('two_core_configuration_uses_multiple_cores',measurements['cpu-2']['peak_cpu_cores'].get('compute',0)>1.05)
    check('docker_statistics_confirm_multiple_cores',(measurements['cpu-2']['docker_cpu_sample_cores'] or 0)>1.05)
    for name in ('memory-256','memory-512','memory-1024'):
        preset(name)
        if name=='memory-256':
            api('/api/runs',{'workload':'memory','overrides':{'memory_mib':65}},400)
            api('/api/runs',{'workload':'combined','overrides':{'memory_mib':128}},400)
            check('low_memory_invalid_allocation_rejected',True)
        measured_run('memory',name)
    preset('replica-1')
    measured_run('cpu_fixed','replica-1')
    preset('replica-2')
    replica=measured_run('cpu_fixed','replica-2')
    check('replicas_each_receive_half_work',{s:p['counters']['fixed_batches'] for s,p in replica['instance_results'].items()}=={'compute':16,'compute-2':16})
    check('replica_work_and_concurrency_constant',runs['replica-1']['counters']['checksum']==replica['counters']['checksum'] and runs['replica-1']['calculation_processes']==replica['calculation_processes']==2)
    check('comparison_images_constant',len({runs[n]['deployment']['images']['compute'] for n in ('cpu-05','cpu-1','cpu-2','replica-1','replica-2')})==1)
    data=helpers.complete_trace(replica)
    (OUT/'replica-trace.json').write_text(json.dumps(data,indent=2))
    traced=helpers.spans(data)
    check('trace_includes_both_compute_instances',{'compute','compute-2'}<={s for s,_ in traced})
    check('trace_has_one_span_per_logical_batch',sum(s['name']=='cpu.batch' for _,s in traced)==32)
    ids={s['spanId'] for _,s in traced}
    check('replica_trace_connected',sum(not s.get('parentSpanId') for _,s in traced)==1 and all(not s.get('parentSpanId') or s['parentSpanId'] in ids for _,s in traced))

    # Reject preset changes during active work; preserve the original generation.
    active=api('/api/runs',{'workload':'cpu_fixed','name':'Stage 4 stop and deployment conflict'},202)
    wait_for(lambda:api('/api/runs/'+active['id'])['counters'].get('cpu_batches',0)>1000)
    generation=api('/api/deployment')['generation']
    rejected=subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'scripts/apply-preset.ps1'),'-Preset','cpu-2'],cwd=ROOT,text=True,capture_output=True,timeout=20)
    check('active_run_blocks_preset_change',rejected.returncode!=0 and api('/api/deployment')['generation']==generation)
    check('rejected_change_restores_maintenance_flag',not api('/api/deployment')['pending'])
    began=time.monotonic(); cancelled=stop(active['id'])
    runs['cancelled']=cancelled
    measurements['stop_seconds']=time.monotonic()-began
    check('all_slots_stop_within_five_seconds',measurements['stop_seconds']<5 and cancelled['state']=='cancelled')
    counts=json.loads(helpers.internal('http://compute:5000/internal/state'))['process_count']+json.loads(helpers.internal('http://compute-2:5000/internal/state'))['process_count']
    check('cancel_reaps_all_processes',counts==0)
    check('cancel_preserves_partial_counts',cancelled['counters']['cpu_batches']>0)

    for service in ('controller','compute-2'):
        active=api('/api/runs',{'workload':'cpu_fixed','name':'Stage 4 recovery: '+service},202)
        wait_for(lambda:api('/api/runs/'+active['id'])['counters'].get('cpu_batches',0)>2000)
        if service=='controller':
            compose('kill','--signal','SIGKILL',service)
            compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','90',service)
        else: compose('restart',service)
        wait_for(ready,45)
        interrupted=result(active['id'],15)
        runs['recovery-'+service]=interrupted
        check(service+'_restart_interrupted',interrupted['state']=='interrupted')
        check(service+'_restart_trace_preserved',interrupted['trace_id']==active['trace_id'])
        check(service+'_restart_no_replay',interrupted['counters'].get('cpu_batches',0)<80000)
        check(service+'_restart_no_active_run',api('/api/runs/active')['run'] is None)

    # Maintenance survives recreation even when only a read-only state file exists.
    state=json.loads((ROOT/'.runtime/deployment.json').read_text())
    try:
        write_state({**state,'pending':True})
        api('/api/runs',{'workload':'cpu_fixed'},503)
        compose('restart','controller')
        wait_for(healthy,30)
        check('maintenance_survives_controller_restart',api('/api/deployment')['pending'])
        api('/api/runs',{'workload':'cpu_fixed'},503)
        check('maintenance_blocks_starts',True)
    finally: write_state(state)
    wait_for(ready,30)
    preset('replica-2',False)
    measured_run('cpu_fixed','replica-without-tracing',batches=4)
    check('tracing_disabled_run_has_no_trace',runs['replica-without-tracing']['trace_id'] is None)
    running=subprocess.check_output(['docker','compose','--profile','replica','--profile','tracing','ps','--services','--status','running'],cwd=ROOT,text=True).splitlines()
    check('eight_services_without_tracing',len(running)==8)
    preset('baseline',True)
    # No-argument startup must restore the saved deployment and tracing choice.
    restored=subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'scripts/start.ps1'),'-NoBuild'],cwd=ROOT,text=True,capture_output=True,timeout=180)
    check('startup_restores_last_success',restored.returncode==0 and api('/api/deployment')['preset']=='baseline' and api('/api/deployment')['tracing'])
    wait_for(ready,30)

    resource_dashboard=helpers.grafana('/api/dashboards/uid/cloud-lab1-resources')['dashboard']
    for panel in resource_dashboard['panels']:
        if panel['type']!='timeseries': continue
        query=panel['targets'][0]['expr'].replace('$service','compute')
        values=prom(query)
        check('resource_panel_'+str(panel['id'])+'_valid',bool(values) and all(row['value'][1] not in ('NaN','+Inf','-Inf') for row in values))
    previous=json.loads((ROOT/'docs/evidence/lifecycle.json').read_text())
    historical=prom(previous['persistence_query'],previous['persistence_sample_time'])
    check('stage1_metric_history_preserved',bool(historical) and historical[0]['value'][1]=='1')
    check('previous_stage_records_preserved',api('/api/runs?page_size=100')['total']>len(runs))
    old_trace=json.loads((ROOT/'docs/evidence/stage3/browser-run.json').read_text())
    check('stage3_trace_preserved',bool(helpers.trace_data(old_trace['trace_id'])))
    exported=urllib.request.urlopen(BASE+'/api/runs/export.csv').read().decode()
    (OUT/'experiment-history.csv').write_text(exported,encoding='utf-8')
    rows={row['id']:row for row in csv.DictReader(io.StringIO(exported))}
    row=rows[replica['id']]
    check('csv_saved_deployment_matches',json.loads(row['deployment'])['preset']=='replica-2')
    check('csv_batch_results_match',json.loads(row['batch_results'])==replica['batch_results'])
    check('csv_assignment_matches',json.loads(row['assignment'])==replica['assignment'])
    check('old_history_exports_unknown_deployment',any(row['deployment']=='' for row in rows.values()))
    check('baseline_restored_and_idle',api('/api/deployment')['verified'] and api('/api/runs/active')['run'] is None)
    ids=subprocess.check_output(['docker','compose','--profile','replica','--profile','tracing','ps','-q'],cwd=ROOT,text=True).split()
    containers=json.loads(subprocess.check_output(['docker','inspect',*ids],cwd=ROOT,text=True))
    check('no_container_oom_kills',not any(c['State']['OOMKilled'] for c in containers))
    measurements['final_configured_memory_gib']=sum(c['HostConfig']['Memory'] for c in containers)/1024**3
    check('all_presets_within_memory_budget',max(4.5+(d['expected']['data']['memory_bytes']-512*1024**2)/1024**3+(.5 if len(d['compute_instances'])==2 else 0) for d in deployments.values())<=5)
    subprocess.run([sys.executable, str(ROOT/'scripts/verify-stage4-dashboard.py')], cwd=ROOT, check=True)


if __name__=='__main__':
    try: main()
    finally: save()
