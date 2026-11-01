"""One threaded registry per service; workload children never own registries."""
import copy
import threading
import time
from flask import Response, g, request
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import HistogramMetricFamily
from shared.io_stats import IO_BUCKETS

KINDS = ('cpu', 'cpu_fixed', 'memory', 'network', 'database', 'combined')
OPERATIONS = {'cpu_batches': 'cpu_batch', 'network_requests': 'network_request',
              'database_writes': 'database_write', 'database_reads': 'database_read',
              'database_cycles': 'database_cycle', 'errors': 'cycle', 'fixed_batches': 'logical_batch'}


class LatencyCollector:
    def __init__(self):
        self.lock = threading.Lock()
        self.totals = {}

    def merge(self, kind, current, previous):
        with self.lock:
            for key, value in current.items():
                old = previous.get(key, {'buckets': [0] * len(IO_BUCKETS), 'count': 0, 'sum': 0})
                target = self.totals.setdefault((kind, *key.split(':')),
                                               {'buckets': [0] * len(IO_BUCKETS), 'count': 0, 'sum': 0})
                target['count'] += max(0, value['count'] - old['count'])
                target['sum'] += max(0, value['sum'] - old['sum'])
                for index in range(len(IO_BUCKETS)):
                    target['buckets'][index] += max(0, value['buckets'][index] - old['buckets'][index])

    def collect(self):
        histogram = HistogramMetricFamily('lab_workload_io_duration_seconds',
                                          'Full transfer or database call duration, including failed calls.',
                                          labels=['workload', 'operation', 'outcome'])
        with self.lock:
            values = copy.deepcopy(self.totals)
        for labels, value in values.items():
            buckets = [('+Inf' if bound == float('inf') else str(bound), count)
                       for bound, count in zip(IO_BUCKETS, value['buckets'])]
            histogram.add_metric(list(labels), buckets=buckets, sum_value=value['sum'])
        yield histogram


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.requests = Counter('lab_http_requests_total', 'Application requests; excludes probes, scrapes and assets.',
                                ['method', 'route', 'status'], registry=self.registry)
        self.http_duration = Histogram('lab_http_request_duration_seconds', 'Time until response headers are ready.',
                                       ['method', 'route'], buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5),
                                       registry=self.registry)
        self.active = Gauge('lab_runs_active', 'Controller global active experiment.', ['workload'], registry=self.registry)
        self.outcomes = Counter('lab_runs_total', 'Controller-observed terminal transitions, never history reads.',
                                ['workload', 'outcome'], registry=self.registry)
        self.duration = Histogram('lab_workload_duration_seconds', 'Worker lifetime including process startup and cleanup.',
                                  ['workload', 'outcome'], buckets=(1, 5, 15, 30, 60, 120, 180, 210), registry=self.registry)
        self.operations = Counter('lab_workload_operations_total', 'Reported actual operations, including partial results.',
                                   ['workload', 'operation', 'outcome'], registry=self.registry)
        self.bytes = Counter('lab_workload_network_bytes_total', 'Bytes actually received by workload children.',
                             ['workload'], registry=self.registry)
        self.elapsed = Gauge('lab_workload_elapsed_seconds', 'Reported child elapsed time; zero when idle.',
                             ['workload'], registry=self.registry)
        self.worker_active = Gauge('lab_workload_active', 'Worker owns a workload process.', ['workload'], registry=self.registry)
        self.latencies = LatencyCollector()
        self.registry.register(self.latencies)
        self.previous = {}
        self.finished = set()
        for kind in KINDS:
            self.active.labels(kind).set(0)
            self.elapsed.labels(kind).set(0)
            self.worker_active.labels(kind).set(0)

    def begin(self, run):
        # Only one child is active; one cumulative snapshot suffices for delta merging.
        self.previous = {}
        self.worker_active.labels(run['workload']).set(1)

    def progress(self, run, message):
        kind = run['workload']
        old = self.previous.get('counters', {})
        counters = message.get('counters', {})
        for key, operation in OPERATIONS.items():
            delta = max(0, counters.get(key, 0) - old.get(key, 0))
            self.operations.labels(kind, operation, 'error' if key == 'errors' else 'success').inc(delta)
        self.bytes.labels(kind).inc(max(0, counters.get('network_bytes', 0) - old.get('network_bytes', 0)))
        current_io = message.get('telemetry', {})
        previous_io = self.previous.get('telemetry', {})
        self.latencies.merge(kind, current_io, previous_io)
        for key, value in current_io.items():
            operation, outcome = key.split(':')
            if outcome == 'error':
                self.operations.labels(kind, operation, outcome).inc(
                    max(0, value['count'] - previous_io.get(key, {}).get('count', 0)))
        elapsed = max(self.previous.get('elapsed_seconds', 0), message.get('elapsed_seconds', 0))
        self.elapsed.labels(kind).set(elapsed)
        # Keep high-water marks even if a repeated older snapshot arrives.
        snapshot = copy.deepcopy(message)
        snapshot['elapsed_seconds'] = elapsed
        snapshot['counters'] = {key: max(value, counters.get(key, 0)) for key, value in old.items()} | {
            key: max(value, old.get(key, 0)) for key, value in counters.items()}
        snapshot['telemetry'] = copy.deepcopy(previous_io)
        for key, value in current_io.items():
            prior = previous_io.get(key, {'buckets': [0]*len(IO_BUCKETS), 'count': 0, 'sum': 0})
            snapshot['telemetry'][key] = {'count': max(value['count'], prior['count']),
                'sum': max(value['sum'], prior['sum']),
                'buckets': [max(a, b) for a, b in zip(value['buckets'], prior['buckets'])]}
        self.previous = snapshot

    def end_worker(self, run, elapsed):
        kind = run['workload']
        self.duration.labels(kind, run['state']).observe(elapsed)
        self.elapsed.labels(kind).set(0)
        self.worker_active.labels(kind).set(0)

    def terminal(self, run):
        if run['id'] not in self.finished:
            self.finished.add(run['id'])
            self.outcomes.labels(run['workload'], run['state']).inc()
        # Bound bookkeeping in the same way as the coordinator's retained records.
        if len(self.finished) > 200:
            self.finished = {run['id']}


def install_http(app, metrics):
    def excluded():
        return request.path in ('/health', '/metrics') or request.path.startswith('/static/')

    @app.before_request
    def start_timer():
        if not excluded():
            g.metric_started = time.monotonic()

    @app.after_request
    def record(response):
        if hasattr(g, 'metric_started'):
            method = request.method if request.method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS') else 'OTHER'
            route = request.url_rule.rule if request.url_rule else 'unmatched'
            metrics.requests.labels(method, route, str(response.status_code)).inc()
            metrics.http_duration.labels(method, route).observe(time.monotonic() - g.metric_started)
        return response

    @app.get('/metrics')
    def prometheus_metrics():
        return Response(generate_latest(metrics.registry), content_type=CONTENT_TYPE_LATEST)
