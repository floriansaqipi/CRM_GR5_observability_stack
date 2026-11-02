"""Read-only verification of the revised UI's monitoring and saved evidence."""
import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
import re
from lab_api import ROOT, api, prom, ready, wait_for, document_count

spec = importlib.util.spec_from_file_location('stage4_dashboard_helpers',Path(__file__).with_name('verify-stage4-dashboard.py'))
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)
helpers = dashboard.helpers
OUT = ROOT/'docs/evidence/stage5'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',action='store_true')
    arguments = parser.parse_args()
    checks = {}

    def check(name,condition):
        checks[name] = bool(condition)
        print(('PASS ' if condition else 'FAIL ')+name,flush=True)
        (OUT/('preflight-verification.json' if arguments.preflight else 'verification.json')).write_text(json.dumps(checks,indent=2))
        assert condition,name

    wait_for(ready)
    before = json.loads((OUT/'dashboard-before.json').read_text())
    previous = json.loads((ROOT/'docs/evidence/stage4/acceptance.json').read_text())
    for filename,old in before.items():
        live = helpers.grafana('/api/dashboards/uid/'+old['uid'])['dashboard']
        panels = {panel['id']:panel for panel in live['panels']}
        check(filename+'_identity',live['uid']==old['uid'] and live['title']==old['title'])
        # Grafana normalizes variable metadata; compare the query and chosen values.
        check(filename+'_selector_query',live['templating']['list'][0]['query']==old['templating']['list'][0]['query'])
        check(filename+'_refresh_and_range',live['refresh']==old['refresh'] and live['time']==old['time'])
        check(filename+'_grouping_rows',len([p for p in live['panels'] if p['type']=='row'])==3)
        for panel in old['panels']:
            current = panels[panel['id']]
            check(filename+'_panel_'+str(panel['id'])+'_query_preserved',current['targets']==panel['targets'])
            if panel['type']=='timeseries':
                query = current['targets'][0]['expr'].replace('$service','compute|compute-2').replace('$__range','120s')
                for case in ('cpu-2','replica-2'):
                    data = dashboard.query_range(query,previous['runs'][case])
                    # I/O histograms can be absent during fixed CPU work.
                    valid = all(math.isfinite(float(value)) for series in data for _,value in series['values'])
                    if filename=='container-resources.json' or panel['id']==12:
                        check(filename+'_panel_'+str(panel['id'])+'_'+case+'_historic_data',bool(data) and valid)
    state = api('/api/deployment')
    check('baseline_tracing_verified',state['preset']=='baseline' and state['tracing'] and state['verified'] and not state['pending'])
    check('three_healthy_application_scrapes',len(prom('(up{job="applications",project="cloud-lab1"} == 1) and (timestamp(up{job="applications",project="cloud-lab1"}) > time()-15)'))==3)
    original = json.loads((ROOT/'docs/evidence/lifecycle.json').read_text())
    check('stage1_metric_history_preserved',prom(original['persistence_query'],original['persistence_sample_time'])[0]['value'][1]=='1')
    older = api('/api/runs/'+previous['runs']['replica-2']['id'])
    check('stage4_history_preserved',older['batch_results']==previous['runs']['replica-2']['batch_results'])
    check('existing_tests_passed','Ran 31 tests' in (OUT/'unit-tests.txt').read_text() and '\nOK' in (OUT/'unit-tests.txt').read_text())
    if arguments.preflight:
        return
    experiment = json.loads((OUT/'experiments.json').read_text())
    check('four_example_runs',set(experiment['runs'])=={'cpu','memory','network','combined'})
    for name,passed in experiment['checks'].items():
        check('example_'+name,passed)
    rows = list(csv.DictReader((OUT/'browser-example-export.csv').read_text(encoding='utf-8').splitlines()))
    expected = {entry['run']['id']:entry['run'] for entry in experiment['runs'].values()}
    check('browser_example_csv_exact_ids',len(rows)==4 and {row['id'] for row in rows}==set(expected))
    check('browser_example_csv_exact_results',all(json.loads(row['counters'])==expected[row['id']]['counters'] and json.loads(row['settings'])==expected[row['id']]['settings'] for row in rows))
    cancelled = list(csv.DictReader((OUT/'browser-filtered-export.csv').read_text(encoding='utf-8').splitlines()))
    check('browser_cancelled_export_filters',len(cancelled)==1 and cancelled[0]['state']=='cancelled' and cancelled[0]['name']=='Stage 5 UI check: cancellation')
    browser = json.loads((OUT/'browser-verification.json').read_text())
    for name,passed in browser['checks'].items():
        check('browser_'+name,passed)
    for kind in experiment['runs']:
        check(kind+'_report_plot_exists',(OUT/kind/'resources.png').stat().st_size>1000)
    for filename in ('README.md','docs/repository-guide.md','docs/demo-guide.md','docs/experiment-results.md','docs/stage-5.md'):
        path = ROOT/filename
        missing = [target for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8'))
                   if '://' not in target and not target.startswith('#') and not (path.parent/target.split('#')[0]).exists()]
        check(filename+'_local_links',not missing)
    check('no_active_or_unsaved_run',api('/api/runs/active')['run'] is None and api('/api/workloads')['unsaved_count']==0)
    check('temporary_workload_documents_clean',document_count()==0)


if __name__=='__main__':
    main()
