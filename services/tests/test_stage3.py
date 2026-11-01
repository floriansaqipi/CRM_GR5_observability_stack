import copy
import atexit
import csv
import io
import json
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from flask import Flask
from prometheus_client import generate_latest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from shared import tracing
from shared.metrics import Metrics, install_http
from shared.io_stats import IOStats
from shared.model import public_run
from shared.worker import Worker
from test_stage2 import FakeRepository, run_record
from coordinator import Coordinator
from app import runtime as imported_runtime

# App import creates a MongoClient even when tests replace the runtime with a fake.
atexit.register(imported_runtime.shutdown)


class MetricsTests(unittest.TestCase):
    def test_http_templates_exclusions_errors_and_histograms(self):
        app, m = Flask('metrics-test'), Metrics()
        install_http(app, m)
        app.add_url_rule('/api/items/<item_id>', view_func=lambda item_id: ('ok', 409))
        app.add_url_rule('/health', endpoint='health', view_func=lambda: 'ok')
        client = app.test_client()
        for suffix in ('one', 'two', 'three'):
            client.get('/api/items/' + suffix)
        client.get('/health')
        client.get('/metrics')
        client.get('/static/missing.css')
        client.get('/missing/unique-id')
        labels = {'method': 'GET', 'route': '/api/items/<item_id>', 'status': '409'}
        self.assertEqual(m.registry.get_sample_value('lab_http_requests_total', labels), 3)
        self.assertEqual(m.registry.get_sample_value('lab_http_request_duration_seconds_count',
                         {'method': 'GET', 'route': '/api/items/<item_id>'}), 3)
        samples = generate_latest(m.registry).decode()
        for value in ('/health', '/static/', 'unique-id', 'route="/metrics"', '/api/items/one'):
            self.assertNotIn(value, samples)
        self.assertIn('route="unmatched"', samples)

    def test_cumulative_progress_and_latency_are_not_double_counted(self):
        m, run = Metrics(), run_record('network')
        m.begin(run)
        message = {'counters': {'network_requests': 2, 'network_bytes': 2048}, 'elapsed_seconds': 1,
                   'telemetry': {'network_request:success': {'buckets': [2]*11, 'count': 2, 'sum': .003}}}
        m.progress(run, message)
        m.progress(run, copy.deepcopy(message))
        # An older replay must not move the cumulative checkpoint backward.
        m.progress(run, {'counters': {'network_requests': 1, 'network_bytes': 1024}})
        m.progress(run, copy.deepcopy(message))
        labels = {'workload': 'network', 'operation': 'network_request', 'outcome': 'success'}
        self.assertEqual(m.registry.get_sample_value('lab_workload_operations_total', labels), 2)
        self.assertEqual(m.registry.get_sample_value('lab_workload_io_duration_seconds_count', labels), 2)
        self.assertIn('le="+Inf"', generate_latest(m.registry).decode())
        run['state'] = 'cancelled'
        m.end_worker(run, 1.5)
        self.assertEqual(m.registry.get_sample_value('lab_workload_elapsed_seconds', {'workload': 'network'}), 0)

    def test_failed_io_and_duplicate_terminal_transition(self):
        stats, m, run = IOStats(), Metrics(), run_record('database')
        with self.assertRaises(RuntimeError):
            with stats.measure('database_write'):
                raise RuntimeError('test error')
        m.progress(run, {'counters': {'errors': 1}, 'telemetry': stats.values})
        labels = {'workload': 'database', 'operation': 'database_write', 'outcome': 'error'}
        self.assertEqual(m.registry.get_sample_value('lab_workload_operations_total', labels), 1)
        run['state'] = 'failed'
        m.terminal(run)
        m.terminal(run)
        self.assertEqual(m.registry.get_sample_value('lab_runs_total', {'workload': 'database', 'outcome': 'failed'}), 1)

    def test_old_history_and_public_csv_compatibility(self):
        run = run_record()
        run.update(state='completed', finished_at=None, _trace_context={'traceparent': 'private'})
        public = public_run(run)
        self.assertIsNone(public['trace_id'])
        self.assertIsNone(public['trace_url'])
        self.assertNotIn('_trace_context', public)
        self.assertIn('cloud-lab1-application', public['application_grafana_url'])
        from app import app
        coordinator = Coordinator(FakeRepository())
        coordinator._remember(run)
        with patch('app.runtime', coordinator):
            response = app.test_client().get('/api/runs/export.csv')
            row = next(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(row['trace_id'], '')
        self.assertEqual(coordinator.metrics.registry.get_sample_value('lab_runs_total',
                         {'workload': 'memory', 'outcome': 'completed'}), None)
        coordinator.shutdown()

    def test_exporter_stderr_does_not_become_a_workload_error(self):
        worker, run = Worker('data'), run_record()
        code = ('import json,sys; print("Trace exporter unavailable",file=sys.stderr); '
                'print(json.dumps({"final":True,"state":"completed","error":None,"counters":{}}))')
        worker._command = lambda record: [sys.executable, '-c', code]
        worker.submit(run)
        worker.thread.join(5)
        self.assertIsNone(worker.active_id)
        self.assertEqual(worker.snapshot()['last_run']['state'], 'completed')
        self.assertIsNone(worker.snapshot()['last_run']['error'])
        worker.shutdown()


class TracingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = InMemorySpanExporter()
        provider = TracerProvider(shutdown_on_exit=False)
        provider.add_span_processor(SimpleSpanProcessor(cls.exporter))
        trace.set_tracer_provider(provider)

    def setUp(self):
        self.exporter.clear()

    def test_explicit_thread_and_process_context(self):
        values = []
        with trace.get_tracer('test').start_as_current_span('request') as parent:
            headers = tracing.carrier()
            def work():
                with tracing.attached(headers):
                    with trace.get_tracer('test').start_as_current_span('thread') as span:
                        values.append(span.get_span_context().trace_id)
            thread = threading.Thread(target=work)
            thread.start()
            thread.join()
            code = ('import json,sys; from opentelemetry.propagate import extract; '
                    'from opentelemetry.trace import get_current_span; '
                    'print(get_current_span(extract(json.loads(sys.argv[1]))).get_span_context().trace_id)')
            result = subprocess.check_output([sys.executable, '-c', code, json.dumps(headers)], text=True)
            self.assertEqual(int(result), parent.get_span_context().trace_id)
            self.assertEqual(values, [parent.get_span_context().trace_id])

    def test_selected_cycle_muted_propagation_and_failure_span(self):
        with trace.get_tracer('test').start_as_current_span('workload'):
            parent = tracing.context.get_current()
            with tracing.operation_cycle(False, parent):
                with trace.get_tracer('test').start_as_current_span('omitted') as span:
                    self.assertFalse(span.is_recording())
                    self.assertTrue(tracing.carrier()['traceparent'].endswith('-00'))
            with tracing.operation_cycle(True, parent):
                with trace.get_tracer('test').start_as_current_span('selected'):
                    pass
            with self.assertRaises(ValueError):
                with tracing.operation_cycle(False, parent):
                    raise ValueError('controlled failure')
        spans = self.exporter.get_finished_spans()
        names = [s.name for s in spans]
        self.assertNotIn('omitted', names)
        self.assertIn('selected', names)
        self.assertTrue(any(s.name == 'workload.failed_cycle' and s.status.status_code == trace.StatusCode.ERROR for s in spans))


if __name__ == '__main__':
    unittest.main()
