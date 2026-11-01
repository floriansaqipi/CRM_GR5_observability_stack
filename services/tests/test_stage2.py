import copy
import csv
import io
import json
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from shared.model import resolve_request, utc_now
from shared.worker import Conflict, Worker
from coordinator import Coordinator, Unavailable
from app import app, CSV_FIELDS


def run_record(kind='memory'):
    return {**resolve_request({'workload': kind, 'duration_seconds': 15}), 'id': str(uuid4()),
            'target_service': 'compute' if kind == 'cpu' else 'data', 'created_at': utc_now()}


def wait_until(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError('Condition did not become true before timeout.')


class FakeRepository:
    def __init__(self):
        self.available = False
        self.rows = {}
        self.fail_save = False

    def ping(self):
        return self.available

    def save(self, run):
        if self.fail_save:
            raise RuntimeError('Database unavailable')
        self.rows[run['id']] = copy.deepcopy(run)

    def history(self, query, excluded, count):
        rows = [r for key, r in self.rows.items() if key not in excluded]
        return rows[:count], len(rows)

    def older_unfinished(self, cutoff):
        return []

    def close(self):
        pass


class ValidationTests(unittest.TestCase):
    def test_presets_and_overrides_are_resolved_and_bounded(self):
        body = {'workload': 'combined', 'profile': 'high', 'overrides': {'memory_mib': 12}}
        resolved = resolve_request(body)
        self.assertEqual(resolved['settings']['memory_mib'], 12)
        self.assertEqual(resolved['settings']['payload_kib'], 1024)
        body['overrides']['memory_mib'] = 99
        self.assertEqual(resolved['settings']['memory_mib'], 12)
        for body in [None, [], {'workload': []}, {'workload': 'unknown'},
                     {'workload': 'cpu', 'duration_seconds': True},
                     {'workload': 'cpu', 'duration_seconds': 14},
                     {'workload': 'cpu', 'duration_seconds': 181},
                     {'workload': 'cpu', 'overrides': {'cpu_percent': 96}},
                     {'workload': 'memory', 'overrides': {'memory_mib': 129}},
                     {'workload': 'network', 'overrides': {'rate_per_second': 21}},
                     {'workload': 'database', 'overrides': {'document_kib': 65}},
                     {'workload': 'cpu', 'overrides': {'memory_mib': 4}}]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                resolve_request(body)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.worker = Worker('data')

    def tearDown(self):
        self.worker.shutdown()

    def test_duplicate_start_overlap_and_cancellation_reap_one_child(self):
        record = run_record()
        self.worker.submit(record)
        wait_until(lambda: self.worker.snapshot()['active']['counters'].get('allocated_mib'))
        process = self.worker.process
        self.worker.submit(record)
        self.assertIs(self.worker.process, process)
        with self.assertRaises(Conflict):
            self.worker.submit(run_record())
        changed = copy.deepcopy(record)
        changed['settings']['memory_mib'] = 1
        with self.assertRaises(Conflict):
            self.worker.submit(changed)
        started = time.monotonic()
        self.worker.stop(record['id'])
        self.worker.stop(record['id'])
        self.worker.thread.join(timeout=5)
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsNotNone(process.poll())
        snapshot = self.worker.snapshot()
        self.assertIsNone(snapshot['active'])
        self.assertEqual(snapshot['last_run']['state'], 'cancelled')
        self.assertGreater(snapshot['last_run']['counters']['touched_pages'], 0)

    def test_immediate_stop_races_do_not_leave_active_processes(self):
        for _ in range(5):
            record = run_record()
            self.worker.submit(record)
            self.worker.stop(record['id'])
            self.worker.thread.join(timeout=5)
            self.assertIsNone(self.worker.active_id)
            self.assertEqual(self.worker.snapshot()['last_run']['state'], 'cancelled')

    def test_parent_deadline_kills_a_child_that_ignores_term(self):
        self.worker._command = lambda record: [sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)']
        self.worker.submit(run_record())
        wait_until(lambda: self.worker.process is not None)
        process = self.worker.process
        self.worker.thread.join(timeout=23)
        self.assertIsNotNone(process.poll())
        self.assertEqual(self.worker.snapshot()['last_run']['state'], 'failed')
        self.assertIn('deadline', self.worker.snapshot()['last_run']['error'])

    def test_service_shutdown_records_interrupted_and_reaps_child(self):
        self.worker.submit(run_record())
        wait_until(lambda: self.worker.snapshot()['active']['counters'].get('allocated_mib'))
        child = self.worker.process
        self.worker.shutdown()
        self.assertIsNotNone(child.poll())
        self.assertEqual(self.worker.snapshot()['last_run']['state'], 'interrupted')


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.coordinator = Coordinator(self.repo)
        self.coordinator.ready = True
        self.coordinator.recovering = False
        self.coordinator.worker_available = {'compute': True, 'data': True}

    def tearDown(self):
        self.coordinator.shutdown()

    def test_concurrent_start_has_exactly_one_global_winner(self):
        results = []
        barrier = threading.Barrier(5)
        def start():
            barrier.wait()
            try:
                results.append(self.coordinator.submit({'workload': 'cpu'}))
            except Conflict:
                results.append(None)
        threads = [threading.Thread(target=start) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_database_outage_keeps_independent_workloads_available(self):
        availability = {w['id']: w['available'] for w in self.coordinator.catalog()['workloads']}
        self.assertTrue(all(availability[k] for k in ('cpu', 'memory', 'network')))
        self.assertFalse(availability['database'])
        with self.assertRaises(Unavailable):
            self.coordinator.submit({'workload': 'database'})
        self.assertEqual(self.coordinator.submit({'workload': 'memory'})['persistence'], 'pending')

    def test_unsaved_cap_refuses_more_work_without_losing_records(self):
        for _ in range(100):
            record = run_record()
            record.update(state='completed', finished_at=utc_now(), counters={}, rates={}, elapsed_seconds=1, error=None)
            self.coordinator._remember(record)
        with self.assertRaises(Unavailable):
            self.coordinator.submit({'workload': 'cpu'})
        self.assertEqual(len(self.coordinator.records), 100)

    def test_failed_save_remains_pending_then_recovers(self):
        run = self.coordinator.submit({'workload': 'memory'})
        self.repo.available = True
        self.repo.fail_save = True
        states = {'service': 'data', 'boot_id': 'a', 'active': None, 'last_run': None}
        with patch.object(self.coordinator, '_http', return_value=states):
            self.coordinator._tick()
        self.assertIn(run['id'], self.coordinator.pending)
        self.repo.available = True
        self.repo.fail_save = False
        with patch.object(self.coordinator, '_http', return_value=states):
            self.coordinator._tick()
        self.assertNotIn(run['id'], self.coordinator.pending)
        self.assertIn(run['id'], self.repo.rows)
        self.assertNotIn(run['id'], self.coordinator.dispatched)

    def test_csv_quotes_notes_and_exports_actual_values(self):
        run = self.coordinator.submit({'workload': 'cpu', 'name': '=test', 'notes': 'Comma, quote " and\nnewline'})
        self.coordinator.records[run['id']].update(state='completed', counters={'cpu_batches': 123}, finished_at=utc_now())
        self.coordinator.active_id = None
        with patch('app.runtime', self.coordinator):
            response = app.test_client().get('/api/runs/export.csv?workload=cpu')
            content = response.get_data(as_text=True)
        row = list(csv.DictReader(io.StringIO(content)))[0]
        self.assertEqual(row['id'], run['id'])
        self.assertEqual(row['name'], "'=test")
        self.assertEqual(row['notes'], 'Comma, quote " and\nnewline')
        self.assertEqual(json.loads(row['counters'])['cpu_batches'], 123)
        self.assertEqual(set(row), set(CSV_FIELDS))


if __name__ == '__main__':
    unittest.main()
