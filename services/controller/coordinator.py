"""A single coordinator owns the global run slot and reconciles worker restarts."""
from collections import OrderedDict
import copy
import re
import threading
import time
from uuid import uuid4
import requests
from concurrent.futures import ThreadPoolExecutor
from shared.model import ACTIVE, TERMINAL, FIELDS, PRESETS, LIMITS, public_run, resolve_request, utc_now
from shared.worker import Conflict
from repository import Repository
from shared.metrics import Metrics
from shared import tracing
from shared.deployment import Deployment, expected_workers
from shared.fixed_work import assign_batches, ALGORITHM, UNITS_PER_BATCH
from fixed_coordination import advance, recover, parallel_calls


class Unavailable(Exception):
    pass


class Coordinator:
    def __init__(self, repository=None):
        self.repo = repository or Repository()
        self.lock = threading.RLock()
        self.records = OrderedDict()
        self.pending = set()
        self.active_id = None
        self.dispatched = set()
        self.worker_boots = {}
        self.worker_available = {'compute': False, 'data': False}
        self.ready = False
        self.recovering = True
        self.orphans = set()
        self.recovered_database = False
        self.boot_time = utc_now()
        self.event = threading.Event()
        self.thread = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.metrics = Metrics()
        self.run_spans = {}
        # A supplied repository is the existing unit-test dependency-injection path.
        self.deployment = Deployment(strict=repository is None)
        self.snapshots = {}
        self.sent = set()
        self.http_sessions = {}

    def deployment_status(self):
        with self.lock:
            return self.deployment.status(self.snapshots)

    def prepare_deployment(self):
        with self.lock:
            if self.active_id or self.recovering:
                raise Conflict('Finish or stop the active experiment before changing deployment.')
            if not all(self.worker_available.values()):
                raise Conflict('Wait until all existing worker states can be established before changing deployment.')
            if not self.deployment.read()['pending']:
                raise ValueError('Deployment scripts must establish the durable maintenance flag first.')
            return {'maintenance':True,'active':None}

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def _remember(self, record):
        # Caller holds lock. Never evict unsaved records or the active run.
        previous = self.records.get(record['id'])
        if record.get('state') in TERMINAL and ((previous and previous.get('state') in ACTIVE) or
                                               (not previous and record['state'] == 'interrupted')):
            self._terminal(record)
        self.records[record['id']] = copy.deepcopy(record)
        self.pending.add(record['id'])
        for run_id in list(self.records):
            if len(self.records) <= 100:
                break
            if run_id not in self.pending and run_id != self.active_id:
                del self.records[run_id]

    def submit(self, body):
        resolved = resolve_request(body)
        with self.lock:
            if self.active_id:
                raise Conflict('An experiment is already active. Stop it or wait for completion.')
            deployment = self.deployment.status(self.snapshots)
            if deployment['pending'] or not deployment['verified']:
                raise Unavailable('Deployment maintenance or resource verification is pending. Run the startup/recovery script.')
            if resolved['settings'].get('memory_mib',0) > deployment['memory_allocation_max_mib']:
                raise ValueError(f"This Data preset permits at most {deployment['memory_allocation_max_mib']} MiB of workload memory.")
            if not self.ready or not all(self.worker_available.values()):
                raise Unavailable('Waiting for both workload services to be reachable and idle.')
            if len(self.pending) >= 100:
                raise Unavailable('Unsaved history is full. Restore MongoDB before starting another experiment.')
            if resolved['workload'] in ('database', 'combined') and not self.repo.available:
                raise Unavailable('MongoDB is unavailable. CPU, memory, and network remain usable.')
            run_id = str(uuid4())
            record = {**resolved, 'id': run_id, 'created_at': utc_now(), 'started_at': None,
                      'finished_at': None, 'target_service': 'compute' if resolved['workload'] in ('cpu','cpu_fixed') else 'data',
                      'state': 'starting', 'counters': {}, 'rates': {}, 'elapsed_seconds': 0, 'error': None}
            record['deployment'] = copy.deepcopy(deployment)
            record['target_services'] = deployment['compute_instances'] if resolved['workload']=='cpu_fixed' else [record['target_service']]
            if resolved['workload'] == 'cpu_fixed':
                record.update(assignment=assign_batches(resolved['settings']['batch_count'],record['target_services']),
                              algorithm_version=ALGORITHM,calculation_units_per_batch=UNITS_PER_BATCH,
                              calculation_processes=2,deadline_unix=time.time()+180,batch_results=[],instance_results={})
            self.active_id = run_id
            self.run_spans[run_id] = tracing.begin_run(record)
            self.metrics.active.labels(record['workload']).set(1)
            self._remember(record)
            return public_run(record)

    def active(self):
        with self.lock:
            return self._public(self.records[self.active_id]) if self.active_id else None

    def _public(self, record):
        return public_run(record, record['id'] not in self.pending)

    def get(self, run_id):
        with self.lock:
            if run_id in self.records:
                return self._public(self.records[run_id])
        if not self.repo.available:
            raise Unavailable('Saved history is unavailable while MongoDB is offline.')
        try:
            record = self.repo.get(run_id)
        except Exception as exc:
            raise Unavailable('Cannot read saved history.') from exc
        if not record:
            raise KeyError(run_id)
        return public_run(record, True)

    def stop(self, run_id):
        with self.lock:
            if run_id in self.records:
                record = self.records[run_id]
                if record['state'] in ACTIVE:
                    record['state'] = 'stopping'
                    self.pending.add(run_id)
                return self._public(record)
        return self.get(run_id)

    def catalog(self):
        with self.lock:
            deployment = self.deployment.status(self.snapshots)
            ready = self.ready and deployment['verified'] and not deployment['pending']
            presets = copy.deepcopy(PRESETS)
            for level,count in (('low',16),('medium',32),('high',64)):
                presets[level]['batch_count'] = count
            limits = copy.deepcopy(LIMITS)
            limits['memory_mib'][1] = deployment['memory_allocation_max_mib']
            return {'presets': presets, 'limits': limits, 'fields': FIELDS, 'deployment':deployment,
                    'workloads': [{'id': kind, 'available': ready and all(self.worker_available.values()) and
                                  (self.repo.available or kind not in ('database', 'combined'))} for kind in FIELDS],
                    'workers': dict(self.worker_available), 'storage_available': self.repo.available,
                    'ready': ready, 'coordinator_ready': self.ready and not self.recovering,
                    'unsaved_count': len(self.pending), 'active': self.active()}

    def _terminal(self, record):
        self.metrics.terminal(record)
        self.metrics.active.labels(record['workload']).set(0)
        span = self.run_spans.pop(record['id'], None)
        if span is None:
            with tracing.attached(record.get('_trace_context')):
                span = tracing.trace.get_tracer('cloud-lab1').start_span('experiment.recovered', attributes=tracing.attributes(record))
        tracing.finish_span(span, record)

    @staticmethod
    def matches(record, filters):
        return (not filters.get('workload') or record['workload'] == filters['workload']) and \
               (not filters.get('state') or record['state'] == filters['state']) and \
               (not filters.get('q') or filters['q'].casefold() in record.get('name', '').casefold())

    def history(self, filters, page=1, page_size=20):
        with self.lock:
            cached = [copy.deepcopy(r) for r in self.records.values() if self.matches(r, filters)]
            excluded = list(self.records)
        query = {key: value for key, value in filters.items() if key in ('workload', 'state') and value}
        if filters.get('q'):
            query['name'] = {'$regex': re.escape(filters['q']), '$options': 'i'}
        stored, total = [], 0
        if self.repo.available:
            try:
                stored, total = self.repo.history(query, excluded, page * page_size)
            except Exception:
                self.repo.available = False
        combined = sorted(cached + stored, key=lambda r: r['created_at'], reverse=True)
        with self.lock:
            items = [self._public(r) for r in combined[(page - 1) * page_size:page * page_size]]
        return {'items': items, 'total': total + len(cached), 'page': page, 'page_size': page_size,
                'storage_available': self.repo.available}

    def _http(self, service, path, body=None):
        url = f'http://{service}:5000{path}'
        headers = body.get('_trace_context', {}) if body else {}
        with tracing.attached(headers):
            if service not in self.http_sessions:
                self.http_sessions[service] = requests.Session()
            session = self.http_sessions[service]
            session.trust_env = False
            response = session.get(url, timeout=(0.5, 1)) if body is None else session.post(url, json=body, timeout=(0.5, 1))
        response.raise_for_status()
        return response.json()

    def _finish(self, record, state, error):
        record.update(state=state, error=error, finished_at=utc_now())
        # A lost process cannot report its last interval. Keep its counts, but do
        # not leave a batch labelled running after its experiment has ended.
        if state != 'completed':
            for batch in record.get('batch_results',[]):
                if batch['state'] == 'running':
                    batch['state'] = state
            for part in record.get('instance_results',{}).values():
                for batch in part.get('batch_results',[]) or []:
                    if batch['state'] == 'running':
                        batch['state'] = state
        self._terminal(record)
        self.pending.add(record['id'])
        self.dispatched.discard(record['id'])
        self.active_id = None

    def _tick(self):
        states = {}
        expected = expected_workers(self.deployment.read()['preset'])
        self.worker_available = {service:self.worker_available.get(service,False) for service in expected}
        for service in expected:
            try:
                states[service] = self._http(service, '/internal/state')
                self.worker_available[service] = True
            except Exception:
                self.worker_available[service] = False
        with self.lock:
            self.snapshots = states
            if self.recovering and len(states) == len(expected):
                recover(self,states)
            if not self.recovering and self.active_id and self.records[self.active_id]['workload']=='cpu_fixed':
                record = self.records[self.active_id]
                previous = record['state']
                advance(self,record,states)
                if previous != record['state']:
                    self.pending.add(record['id'])
            if not self.recovering and self.active_id and self.records[self.active_id]['workload']!='cpu_fixed':
                record = self.records[self.active_id]
                target = record['target_service']
                snapshot = states.get(target)
                if snapshot is None:
                    # Keep the slot until reconnection establishes that the worker is idle.
                    record['error'] = 'Workload service unreachable; waiting to reconcile its outcome.'
                else:
                    match = snapshot['active'] or snapshot['last_run']
                    if record['id'] in self.dispatched:
                        if match and match['id'] == record['id']:
                            previous = record['state']
                            stop_requested = previous == 'stopping'
                            for key in ('started_at', 'finished_at', 'counters', 'rates', 'elapsed_seconds', 'error', 'state'):
                                record[key] = match.get(key)
                            if match['state'] in TERMINAL:
                                self._terminal(record)
                                self.active_id = None
                                self.dispatched.discard(record['id'])
                                self.pending.add(record['id'])
                            elif stop_requested:
                                record['state'] = 'stopping'
                                self._http(target, f"/internal/runs/{record['id']}/stop", {'_trace_context': record.get('_trace_context', {})})
                            if previous != record['state']:
                                self.pending.add(record['id'])
                        else:
                            self._finish(record, 'interrupted', 'Worker restarted or the dispatched run was not acknowledged; work was not retried.')
                    elif record['state'] == 'stopping':
                        self._finish(record, 'cancelled', None)
                    else:
                        self.dispatched.add(record['id'])
                        try:
                            self._http(target, '/internal/runs', record)
                        except Exception:
                            record['error'] = 'Start acknowledgement unavailable; checking the run ID before accepting more work.'
            for service, snapshot in states.items():
                self.worker_boots[service] = snapshot['boot_id']
        if self.repo.ping():
            if not self.recovering and not self.recovered_database:
                for old in self.repo.older_unfinished(self.boot_time):
                    with self.lock:
                        if old['id'] not in self.records or self.records[old['id']]['state'] in ACTIVE:
                            old.update(state='interrupted', finished_at=utc_now(), error='Previous controller session ended before completion.')
                            self._remember(old)
                self.recovered_database = True
            with self.lock:
                pending = [(run_id, copy.deepcopy(self.records[run_id])) for run_id in self.pending]
            for run_id, record in pending:
                try:
                    self.repo.save(record)
                    with self.lock:
                        # A changed state during the write must remain pending.
                        if self.records[run_id]['state'] == record['state']:
                            self.pending.discard(run_id)
                except Exception:
                    self.repo.available = False
                    break

    def _loop(self):
        while not self.event.is_set():
            try:
                self._tick()
            except Exception as exc:
                print(f'Coordinator will retry: {type(exc).__name__}: {str(exc)[:200]}', flush=True)
            self.event.wait(0.5)

    def shutdown(self):
        self.ready = False
        self.event.set()
        with self.lock:
            active = copy.deepcopy(self.records.get(self.active_id))
        if active:
            # Shutdown may overlap the last polling call. Give these requests
            # private sessions rather than sharing the polling thread's clients.
            def stop_target(service):
                try:
                    with requests.Session() as session:
                        session.trust_env = False
                        with tracing.attached(active.get('_trace_context')):
                            session.post(f"http://{service}:5000/internal/runs/{active['id']}/stop",
                                         json={'reason':'Controller stopped during this experiment.'},timeout=(.5,1))
                except Exception:
                    pass
            with ThreadPoolExecutor(max_workers=len(active.get('target_services',[active['target_service']]))) as pool:
                list(pool.map(stop_target,active.get('target_services',[active['target_service']])))
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        self.session.close()
        for session in self.http_sessions.values():
            session.close()
        self.repo.close()
