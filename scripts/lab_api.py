"""Host-side helpers for demonstrations and repeatable acceptance checks."""
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:5000'
TERMINAL = {'completed', 'cancelled', 'failed', 'interrupted'}


def api(path, body=None, expected=200):
    request = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            status, data = response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        status, data = exc.code, json.load(exc)
    if status != expected:
        raise AssertionError(f'{path}: expected HTTP {expected}, got {status}: {data}')
    return data


def wait_for(condition, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(0.5)
    raise AssertionError('Timed out waiting for the expected state.')


def ready():
    try:
        catalog = api('/api/workloads')
        return catalog if catalog['ready'] and all(catalog['workers'].values()) else None
    except Exception:
        return None


def start(kind, profile='medium', duration=15, **extra):
    return api('/api/runs', {'workload': kind, 'profile': profile, 'duration_seconds': duration, **extra}, 202)


def result(run_id, timeout=200):
    return wait_for(lambda: (r if (r := api('/api/runs/' + run_id))['state'] in TERMINAL else None), timeout)


def stop(run_id):
    api('/api/runs/' + run_id + '/stop', {}, 202)
    return result(run_id, 5)


def prom(query, timestamp=None):
    params = {'query': query}
    if timestamp is not None:
        params['time'] = timestamp
    url = 'http://127.0.0.1:9090/api/v1/query?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.load(response)['data']['result']


def compose(*args):
    state_path = ROOT/'.runtime/deployment.json'
    prefix = ['docker','compose']
    if state_path.exists():
        state = json.loads(state_path.read_text())
        prefix += ['-f','compose.yaml','-f',f"deployment/{state['preset']}.yaml"]
        if state['preset'] == 'replica-2':
            prefix += ['--profile','replica']
        if state['tracing']:
            prefix += ['--profile','tracing']
        import os
        os.environ['LAB_TRACING_ENABLED'] = str(state['tracing']).lower()
    subprocess.run([*prefix, *args], cwd=ROOT, check=True, timeout=240)


def document_count(run_id=None):
    query = json.dumps({'run_id': run_id}) if run_id else '{}'
    command = f'JSON.stringify(db.getSiblingDB("lab").workload_documents.countDocuments({query}))'
    value = subprocess.check_output(['docker', 'compose', 'exec', '-T', 'mongodb', 'mongosh', '--quiet', '--eval', command], cwd=ROOT, text=True, timeout=10)
    return int(value.strip())
