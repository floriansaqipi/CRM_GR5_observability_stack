"""Four real examples with idle/work/cooldown evidence. No plotting dependencies.

Use --manual to start each example through the browser after progress.json says
awaiting_start. Existing experiment evidence is never overwritten.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from lab_api import ROOT, BASE, api, ready, wait_for, result, document_count

spec = importlib.util.spec_from_file_location('stage3_helpers', Path(__file__).with_name('verify-stage3.py'))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
EXAMPLES = ('cpu', 'memory', 'network', 'combined')
SETTINGS = {'cpu': {'cpu_percent':50}, 'memory': {'memory_mib':64},
            'network': {'payload_kib':256,'rate_per_second':5},
            'combined': {'memory_mib':64,'payload_kib':256,'document_kib':16,'rate_per_second':5}}


def timestamp(value):
    return datetime.fromisoformat(value).timestamp()


def images():
    ids = subprocess.check_output(['docker','compose','--profile','tracing','ps','-q'], cwd=ROOT, text=True).split()
    data = json.loads(subprocess.check_output(['docker','inspect',*ids], cwd=ROOT, text=True))
    return {c['Config']['Labels']['com.docker.compose.service']: c['Image'] for c in data}


def query_range(query, start, end):
    query = query.replace('$__range',str(max(1,int(end-start)))+'s')
    parameters = urlencode({'query':query,'start':start,'end':end,'step':5})
    with urlopen('http://127.0.0.1:9090/api/v1/query_range?'+parameters, timeout=15) as response:
        data = json.load(response)
    if data['status'] != 'success':
        raise AssertionError(data)
    return {'query':query,'result':data['data']['result']}


def summarize(measurements, run):
    summaries = {}
    start = timestamp(run['created_at'])
    for key, measurement in measurements.items():
        if key not in ('cpu_30s','cpu_recent','memory_mib','receive_30s','transmit_30s'):
            continue
        for series in measurement['result']:
            service = series['metric']['service']
            values = [(t,float(v)) for t,v in series['values'] if v not in ('NaN','+Inf','-Inf')]
            if not values:
                continue
            target = summaries.setdefault(service,{})
            target['peak_'+key] = max(value for _,value in values)
            if key == 'memory_mib':
                baseline = [v for t,v in values if t < start]
                after = [v for t,v in values if t >= values[-1][0]-10]
                target['baseline_memory_mib'] = statistics.median(baseline) if baseline else None
                target['cooldown_memory_mib'] = statistics.median(after)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual',action='store_true')
    parser.add_argument('--out',type=Path,default=ROOT/'docs/evidence/stage5')
    arguments = parser.parse_args()
    out = arguments.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if (out/'experiments.json').exists():
        raise FileExistsError('Experiment evidence already exists. Choose a new --out directory.')

    def save(name,data):
        path = out/name
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary = path.with_suffix(path.suffix+'.tmp')
        temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
        temporary.replace(path)

    def phase(kind,state,**extra):
        save('progress.json',{'workload':kind,'phase':state,'updated_utc':datetime.now(timezone.utc).isoformat(),**extra})
        print(kind+': '+state,flush=True)

    wait_for(ready)
    deployment = api('/api/deployment')
    assert deployment['preset']=='baseline' and deployment['tracing'] and deployment['verified'] and not deployment['pending']
    assert api('/api/runs/active')['run'] is None
    frozen_images = images()
    assert len(frozen_images)==9
    credentials_hash = hashlib.sha256((ROOT/'.env').read_bytes()).digest()
    sources = [p for p in (ROOT/'services').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    sources += [ROOT/'compose.yaml',*(ROOT/'monitoring').rglob('*.json')]
    manifest = {'recorded_utc':datetime.now(timezone.utc).isoformat(),'mode':'browser' if arguments.manual else 'api',
                'images':frozen_images,'deployment':deployment,'runs':{},'checks':{},
                'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    save('experiments.json',manifest)
    dashboards = {name:json.loads((ROOT/'monitoring/grafana/dashboards'/name).read_text()) for name in ('container-resources.json','application-performance.json')}
    resources = {p['id']:p for p in dashboards['container-resources.json']['panels'] if 'targets' in p}
    selector = 'compute|data|mongodb|controller'
    queries = {key:resources[number]['targets'][0]['expr'].replace('$service',selector)
               for key,number in {'cpu_30s':2,'cpu_recent':11,'memory_mib':3,'receive_30s':4,'transmit_30s':5,'quota_percent':6,'memory_limit_percent':7,'throttled_period_percent':8,'throttled_seconds_rate':9}.items()}
    queries['cpu_seconds_total'] = 'container_cpu_usage_seconds_total{project="cloud-lab1",service=~"'+selector+'",cpu="total",name!=""}'
    queries['network_receive_bytes_total'] = 'container_network_receive_bytes_total{project="cloud-lab1",service=~"'+selector+'",interface="eth0",name!=""}'
    queries['network_transmit_bytes_total'] = queries['network_receive_bytes_total'].replace('receive','transmit')

    for kind in EXAMPLES:
        assert api('/api/runs/active')['run'] is None
        window_start = time.time()
        phase(kind,'baseline',baseline_seconds=30)
        time.sleep(30)
        if arguments.manual:
            phase(kind,'awaiting_start',expected_name='Stage 5 example: '+kind)
            run = wait_for(lambda:api('/api/runs/active')['run'],180)
        else:
            run = api('/api/runs',{'workload':kind,'profile':'medium','duration_seconds':30,'name':'Stage 5 example: '+kind,
                                   'notes':'One illustrative run with idle baseline and cooldown; not a repeated benchmark.'},202)
        assert run['workload']==kind and run['profile']=='medium'
        assert run['settings']=={**SETTINGS[kind],'duration_seconds':30}
        phase(kind,'running',run_id=run['id'])
        run = result(run['id'],50)
        phase(kind,'cooldown',run_id=run['id'],cooldown_seconds=30)
        time.sleep(30)
        run = wait_for(lambda:(r if (r:=api('/api/runs/'+run['id']))['persistence']=='saved' else None),15)
        window_end = time.time()
        measurements = {key:query_range(query,window_start,window_end) for key,query in queries.items()}
        for panel in dashboards['application-performance.json']['panels']:
            for target in panel.get('targets',[]):
                key = 'application_panel_'+str(panel['id'])
                measurements[key] = query_range(target['expr'].replace('$service','controller|compute|data'),window_start,window_end)
        workers = {service:json.loads(helpers.internal('http://'+service+':5000/internal/state')) for service in ('compute','data')}
        checks = {'completed':run['state']=='completed','zero_errors':run['counters']['errors']==0,
                  'saved':run['persistence']=='saved','images_frozen':images()==frozen_images,
                  'workers_reaped':all(w['process_count']==0 and w['active'] is None for w in workers.values()),
                  'temporary_documents_cleaned':document_count()==0,'no_active_run':api('/api/runs/active')['run'] is None,
                  'resource_series_available':all(measurements[k]['result'] for k in ('cpu_30s','memory_mib','receive_30s','transmit_30s'))}
        entry = {'run':run,'window':{'start':window_start,'end':window_end,'baseline_seconds':timestamp(run['created_at'])-window_start,
                                     'cooldown_seconds':window_end-timestamp(run['finished_at']),'query_step_seconds':5},
                 'resources':summarize(measurements,run),'checks':checks}
        save(kind+'/run.json',entry)
        save(kind+'/measurements.json',measurements)
        manifest['runs'][kind] = entry
        manifest['checks'].update({kind+'_'+name:passed for name,passed in checks.items()})
        save('experiments.json',manifest)
        if not all(checks.values()):
            phase(kind,'failed',checks=checks)
            raise AssertionError(checks)
        if kind=='combined':
            trace = helpers.complete_trace(run)
            save('combined/trace.json',trace)
            spans = helpers.spans(trace)
            span_ids = {span['spanId'] for _,span in spans}
            manifest['checks']['connected_combined_trace'] = ({'controller','compute','data'}=={service for service,_ in spans} and
                any(span['name']=='lab.find' for _,span in spans) and sum(not span.get('parentSpanId') for _,span in spans)==1 and
                all(not span.get('parentSpanId') or span['parentSpanId'] in span_ids for _,span in spans))
    with urlopen(BASE+'/api/runs/export.csv',timeout=15) as response:
        reader = csv.DictReader(response.read().decode().splitlines())
        fieldnames = reader.fieldnames
        rows = list(reader)
    selected = {entry['run']['id']:kind for kind,entry in manifest['runs'].items()}
    for name,records in [('experiment-history.csv',[row for row in rows if row['id'] in selected])]+[
            (kind+'/export.csv',[row for row in rows if row['id']==entry['run']['id']]) for kind,entry in manifest['runs'].items()]:
        with (out/name).open('w',newline='',encoding='utf-8') as stream:
            writer = csv.DictWriter(stream,fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
    manifest['checks']['credentials_preserved'] = hashlib.sha256((ROOT/'.env').read_bytes()).digest()==credentials_hash
    manifest['checks']['final_baseline_tracing_verified'] = api('/api/deployment')['preset']=='baseline' and api('/api/deployment')['verified'] and api('/api/deployment')['tracing']
    manifest['checks']['no_unsaved_results'] = api('/api/workloads')['unsaved_count']==0
    save('experiments.json',manifest)
    assert all(manifest['checks'].values()),manifest['checks']
    phase('all','complete')


if __name__=='__main__':
    main()
