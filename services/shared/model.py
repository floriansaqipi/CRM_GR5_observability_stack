"""Workload presets, validation, and the public run representation."""
from datetime import datetime, timezone
import copy
import json
from urllib.parse import urlencode

ACTIVE = {'starting', 'running', 'stopping'}
TERMINAL = {'completed', 'cancelled', 'failed', 'interrupted'}
FIELDS = {
    'cpu_fixed': ['batch_count'],
    'cpu': ['cpu_percent'], 'memory': ['memory_mib'],
    'network': ['payload_kib', 'rate_per_second'],
    'database': ['document_kib', 'rate_per_second'],
    'combined': ['memory_mib', 'payload_kib', 'document_kib', 'rate_per_second'],
}
LIMITS = {'duration_seconds': [15, 180], 'cpu_percent': [10, 95], 'memory_mib': [1, 128],
          'payload_kib': [1, 1024], 'rate_per_second': [1, 20], 'document_kib': [1, 64], 'batch_count': [4, 64]}
PRESETS = {
    'low': {'cpu_percent': 25, 'memory_mib': 32, 'payload_kib': 64, 'rate_per_second': 2, 'document_kib': 4},
    'medium': {'cpu_percent': 50, 'memory_mib': 64, 'payload_kib': 256, 'rate_per_second': 5, 'document_kib': 16},
    'high': {'cpu_percent': 90, 'memory_mib': 128, 'payload_kib': 1024, 'rate_per_second': 10, 'document_kib': 64},
}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def integer(value, name):
    low, high = LIMITS[name]
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}.')
    return value


def resolve_request(body):
    if not isinstance(body, dict):
        raise ValueError('Provide a JSON object.')
    if set(body) - {'workload', 'profile', 'duration_seconds', 'overrides', 'name', 'notes'}:
        raise ValueError('Unknown experiment settings.')
    kind, profile = body.get('workload'), body.get('profile', 'medium')
    if not isinstance(kind, str) or kind not in FIELDS:
        raise ValueError('Choose CPU, memory, network, database, or combined.')
    if not isinstance(profile, str) or profile not in PRESETS:
        raise ValueError('Choose low, medium, or high intensity.')
    overrides = body.get('overrides', {})
    if not isinstance(overrides, dict) or set(overrides) - set(FIELDS[kind]):
        raise ValueError('Advanced settings must apply to the chosen workload.')
    if kind == 'cpu_fixed':
        if body.get('duration_seconds', 180) != 180 or type(body.get('duration_seconds', 180)) is not int:
            raise ValueError('CPU comparison uses a fixed 180-second safety deadline. Omit duration_seconds or use 180.')
        settings = {'batch_count': integer(overrides.get('batch_count', {'low':16,'medium':32,'high':64}[profile]), 'batch_count'),
                    'duration_seconds': 180}
    else:
        settings = {name: integer(overrides.get(name, PRESETS[profile][name]), name) for name in FIELDS[kind]}
        settings['duration_seconds'] = integer(body.get('duration_seconds', 30), 'duration_seconds')
    text = {}
    for name, cap in [('name', 100), ('notes', 1000)]:
        value = body.get(name, '')
        if not isinstance(value, str) or len(value) > cap:
            raise ValueError(f'{name} must be text of at most {cap} characters.')
        text[name] = value.strip()
    return {'workload': kind, 'profile': profile, 'settings': settings, **text}


def validate_resolved(run, service):
    if not isinstance(run, dict) or not isinstance(run.get('id'), str):
        raise ValueError('Missing run ID.')
    from uuid import UUID
    UUID(run['id'])
    kind = run.get('workload')
    if not isinstance(kind, str) or kind not in FIELDS or (service == 'compute') != (kind in ('cpu', 'cpu_fixed')):
        raise ValueError('This service cannot execute that workload.')
    settings = run.get('settings')
    if not isinstance(settings, dict) or set(settings) != set(FIELDS[kind]) | {'duration_seconds'}:
        raise ValueError('Invalid resolved workload settings.')
    for name, value in settings.items():
        integer(value, name)


def public_run(run, saved=False):
    result = copy.deepcopy(run)
    for key in list(result):
        if key.startswith('_'):
            result.pop(key)
    result['persistence'] = 'saved' if saved else 'pending'
    services = run.get('target_services') or (['compute'] if run['workload'] in ('cpu','cpu_fixed') else ['data'])
    services = list(services)
    if run['workload'] in ('database', 'combined'):
        services.append('mongodb')
    start = int(datetime.fromisoformat(run['created_at']).timestamp() * 1000) - 10000
    end = int(datetime.fromisoformat(run['finished_at']).timestamp() * 1000) + 10000 if run.get('finished_at') else 'now'
    query = [('from', start), ('to', end)] + [('var-service', name) for name in services]
    result['grafana_url'] = 'http://localhost:3000/d/cloud-lab1-resources?' + urlencode(query)
    result.setdefault('deployment', None)
    result.setdefault('batch_results', [])
    result['target_services'] = run.get('target_services', [run['target_service']])
    # The controller participates in application dispatch even for a Data-only run.
    app_query = [('from', start), ('to', end), ('var-service', 'controller')] + [('var-service', s) for s in result['target_services']]
    if run['workload'] in ('network', 'combined'):
        app_query.append(('var-service', 'compute'))
    result['application_grafana_url'] = 'http://localhost:3000/d/cloud-lab1-application?' + urlencode(app_query)
    result['trace_id'] = run.get('trace_id')
    result['trace_url'] = None
    if result['trace_id']:
        pane = {'trace': {'datasource': 'tempo', 'queries': [{'refId': 'A', 'queryType': 'traceql',
                'query': result['trace_id']}], 'range': {'from': str(start), 'to': str(end)}}}
        result['trace_url'] = 'http://localhost:3000/explore?' + urlencode({'schemaVersion': 1, 'panes': json.dumps(pane)})
    return result
