"""Read-only deployment state and namespaced cgroup limits. No Docker access."""
import copy
import json
import os
from pathlib import Path
from shared import tracing

PRESETS = json.loads(Path(__file__).with_name('presets.json').read_text())


def read_limits(root='/sys/fs/cgroup'):
    root = Path(root)
    try:
        if (root/'cpu.max').exists():
            quota, period = (root/'cpu.max').read_text().split()
            memory = (root/'memory.max').read_text().strip()
            return {'cgroup_version': 2, 'cpus': None if quota == 'max' else int(quota)/int(period),
                    'memory_bytes': None if memory == 'max' else int(memory)}
        cpu = root/'cpu'
        if not (cpu/'cpu.cfs_quota_us').exists():
            cpu = root/'cpu,cpuacct'
        quota = int((cpu/'cpu.cfs_quota_us').read_text())
        period = int((cpu/'cpu.cfs_period_us').read_text())
        memory = int((root/'memory/memory.limit_in_bytes').read_text())
        return {'cgroup_version': 1, 'cpus': quota/period if quota > 0 else None,
                'memory_bytes': memory if memory < 2**60 else None}
    except (OSError, ValueError, ZeroDivisionError):
        return {'cgroup_version': None, 'cpus': None, 'memory_bytes': None}


def expected_workers(preset):
    settings = PRESETS[preset]
    workers = {'compute': {'cpus': settings['compute_cpus'], 'memory_bytes': 512*1024**2},
               'data': {'cpus': 1, 'memory_bytes': settings['data_memory_mib']*1024**2}}
    if settings['replicas'] == 2:
        workers['compute-2'] = dict(workers['compute'])
    return workers


class Deployment:
    def __init__(self, strict=True):
        self.strict = strict
        self.path = Path(os.environ.get('LAB_DEPLOYMENT_FILE', '/runtime/deployment.json'))

    def read(self):
        if not self.strict:
            return {'preset': 'baseline', 'tracing': tracing.enabled(), 'pending': False, 'generation': 'test'}
        try:
            state = json.loads(self.path.read_text())
            if state['preset'] not in PRESETS:
                raise ValueError('Unknown preset')
            return state
        except (OSError, ValueError, KeyError):
            return {'preset': 'baseline', 'tracing': tracing.enabled(), 'pending': True,
                    'generation': None, 'error': 'Deployment state unavailable. Run the startup script.'}

    def status(self, snapshots):
        state = self.read()
        expected = expected_workers(state['preset'])
        errors, effective = [], {}
        for service, limits in expected.items():
            snapshot = snapshots.get(service, {})
            actual = snapshot.get('configuration', {})
            effective[service] = copy.deepcopy(actual)
            if self.strict:
                if actual.get('instance') != service or actual.get('limits', {}).get('cpus') != limits['cpus'] or \
                        actual.get('limits', {}).get('memory_bytes') != limits['memory_bytes']:
                    errors.append(service + ': effective resource limits do not match the preset.')
                if actual.get('tracing_enabled') != state['tracing']:
                    errors.append(service + ': tracing configuration does not match.')
        if self.strict and tracing.enabled() != state['tracing']:
            errors.append('Controller tracing configuration does not match.')
        return {**state, 'expected': expected, 'effective': effective, 'instances': list(expected),
                'compute_instances': [s for s in expected if s.startswith('compute')],
                'verified': not errors, 'errors': errors,
                'memory_allocation_max_mib': 64 if PRESETS[state['preset']]['data_memory_mib'] == 256 else 128}
