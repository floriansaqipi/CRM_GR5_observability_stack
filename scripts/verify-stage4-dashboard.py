"""Check provisioned queries over actual Stage 4 experiment time ranges."""
import importlib.util
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen
from lab_api import ROOT

spec = importlib.util.spec_from_file_location('stage3_helpers', Path(__file__).with_name('verify-stage3.py'))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
out = ROOT / 'docs/evidence/stage4'


def query_range(expression, run):
    window = parse_qs(urlsplit(run['grafana_url']).query)
    parameters = urlencode({'query': expression, 'start': int(window['from'][0])/1000,
                            'end': int(window['to'][0])/1000, 'step': 1})
    with urlopen('http://127.0.0.1:9090/api/v1/query_range?' + parameters, timeout=15) as response:
        return json.load(response)['data']['result']


def main():
    acceptance = json.loads((out/'acceptance.json').read_text())
    resources = helpers.grafana('/api/dashboards/uid/cloud-lab1-resources')['dashboard']
    application = helpers.grafana('/api/dashboards/uid/cloud-lab1-application')['dashboard']
    checks, examples = {}, {}
    for name in ('cpu-2', 'replica-2'):
        run = acceptance['runs'][name]
        for panel in resources['panels']:
            if panel['type'] != 'timeseries':
                continue
            expression = panel['targets'][0]['expr'].replace('$service', 'compute|compute-2')
            result = query_range(expression, run)
            values = [float(value) for series in result for _, value in series['values']]
            key = f'{name}_resource_panel_{panel["id"]}_historical_query'
            checks[key] = bool(values) and all(math.isfinite(value) for value in values)
            examples[key] = {'series': len(result), 'maximum': max(values) if values else None}
        for panel in application['panels']:
            if panel['id'] != 12:
                continue
            result = query_range(panel['targets'][0]['expr'], run)
            values = [float(value) for series in result for _, value in series['values']]
            key = name + '_aggregate_calculation_throughput'
            checks[key] = bool(values) and max(values) > 0 and all(math.isfinite(value) for value in values)
            examples[key] = {'series': len(result), 'maximum': max(values) if values else None}
    (out/'dashboard-verification.json').write_text(json.dumps({'checks': checks, 'measurements': examples}, indent=2))
    for key, passed in checks.items():
        print(('PASS ' if passed else 'FAIL ') + key)
    if not all(checks.values()):
        raise AssertionError('A provisioned historical dashboard query failed.')


if __name__ == '__main__':
    main()
