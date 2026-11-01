import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
from shared.deployment import Deployment, PRESETS, expected_workers, read_limits
from shared.fixed_work import ALGORITHM, UNITS_PER_BATCH, UNIT_CHECKSUM, assign_batches, calculate_unit
from shared.model import resolve_request, utc_now
from shared.worker import Worker, Conflict
from shared import tracing
from coordinator import Coordinator, Unavailable
from fixed_coordination import combine, advance
from test_stage2 import FakeRepository, wait_until


def fixed_run(instances=None, count=4):
    instances = instances or ['compute']
    return {**resolve_request({'workload':'cpu_fixed','overrides':{'batch_count':count}}),
            'id':str(uuid4()),'target_service':'compute','target_services':instances,'created_at':utc_now(),
            'algorithm_version':ALGORITHM,'assignment':assign_batches(count,instances),
            'deadline_unix':time.time()+180,'state':'starting','counters':{},'batch_results':[]}


class DeploymentTests(unittest.TestCase):
    def test_cgroups_v1_v2_and_unlimited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'cpu').mkdir(); (root/'memory').mkdir()
            (root/'cpu/cpu.cfs_quota_us').write_text('50000')
            (root/'cpu/cpu.cfs_period_us').write_text('100000')
            (root/'memory/memory.limit_in_bytes').write_text(str(256*1024**2))
            self.assertEqual(read_limits(root),{'cgroup_version':1,'cpus':.5,'memory_bytes':256*1024**2})
            (root/'cpu.max').write_text('200000 100000')
            (root/'memory.max').write_text(str(512*1024**2))
            self.assertEqual(read_limits(root)['cpus'],2)
            (root/'cpu.max').write_text('max 100000'); (root/'memory.max').write_text('max')
            self.assertIsNone(read_limits(root)['cpus']); self.assertIsNone(read_limits(root)['memory_bytes'])
            (root/'cpu.max').write_text('broken')
            self.assertIsNone(read_limits(root)['cgroup_version'])

    def test_all_presets_and_effective_mismatch(self):
        self.assertEqual(len(PRESETS),9)
        self.assertEqual(expected_workers('cpu-05')['compute']['cpus'],.5)
        self.assertEqual(expected_workers('memory-1024')['data']['memory_bytes'],1024**3)
        self.assertEqual(len(expected_workers('replica-2')),3)
        with tempfile.TemporaryDirectory() as directory:
            deployment = Deployment()
            deployment.path = Path(directory)/'state.json'
            deployment.path.write_text(json.dumps({'preset':'replica-2','pending':False,'tracing':tracing.enabled()}))
            snapshots = {s:{'configuration':{'instance':s,'limits':v,'tracing_enabled':tracing.enabled()}}
                         for s,v in expected_workers('replica-2').items()}
            self.assertTrue(deployment.status(snapshots)['verified'])
            snapshots['compute-2']['configuration']['limits']['cpus']=.5
            self.assertFalse(deployment.status(snapshots)['verified'])

    def test_maintenance_start_race_and_low_memory_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = Coordinator(FakeRepository())
            coordinator.ready = True; coordinator.recovering = False
            coordinator.worker_available = {'compute':True,'data':True}
            coordinator.deployment = Deployment()
            coordinator.deployment.path = Path(directory)/'state.json'
            state = {'preset':'memory-256','pending':False,'tracing':tracing.enabled()}
            coordinator.deployment.path.write_text(json.dumps(state))
            coordinator.snapshots = {s:{'configuration':{'instance':s,'limits':v,'tracing_enabled':tracing.enabled()}}
                                     for s,v in expected_workers('memory-256').items()}
            with self.assertRaises(ValueError):
                coordinator.submit({'workload':'memory','overrides':{'memory_mib':128}})
            barrier, results = threading.Barrier(2), []
            def start():
                barrier.wait()
                try:
                    coordinator.submit({'workload':'cpu'})
                    results.append('started')
                except Unavailable:
                    results.append('blocked')
            def maintain():
                barrier.wait()
                state['pending']=True
                replacement=coordinator.deployment.path.with_suffix('.tmp')
                replacement.write_text(json.dumps(state)); replacement.replace(coordinator.deployment.path)
                try:
                    coordinator.prepare_deployment(); results.append('maintenance')
                except Conflict:
                    results.append('busy')
            threads=[threading.Thread(target=f) for f in (start,maintain)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            self.assertFalse('started' in results and 'maintenance' in results)
            coordinator.active_id = None
            coordinator.shutdown()


class FixedWorkTests(unittest.TestCase):
    def test_internal_start_rejects_non_object_input(self):
        from shared.worker_app import create_worker
        app,worker=create_worker('data')
        for payload in ([],42,'invalid'):
            response=app.test_client().post('/internal/runs',json=payload)
            self.assertEqual(response.status_code,400)
        worker.shutdown()

    def test_defaults_validation_and_algorithm_checksum(self):
        settings = resolve_request({'workload':'cpu_fixed'})['settings']
        self.assertEqual(settings,{'duration_seconds':180,'batch_count':32})
        self.assertEqual(calculate_unit(),UNIT_CHECKSUM)
        self.assertEqual(UNITS_PER_BATCH,2500)
        traced=fixed_run(); traced['deployment']={'preset':'cpu-2'}
        self.assertEqual(tracing.attributes(traced)['lab.deployment.preset'],'cpu-2')
        self.assertEqual(tracing.attributes(traced)['lab.algorithm.version'],ALGORITHM)
        for body in ({'duration_seconds':30},{'duration_seconds':180.0},{'overrides':{'batch_count':3}},
                     {'overrides':{'batch_count':65}},{'overrides':{'batch_count':True}},
                     {'overrides':{'cpu_percent':50}}):
            with self.subTest(body=body),self.assertRaises(ValueError):
                resolve_request({'workload':'cpu_fixed',**body})

    def test_assignment_is_complete_disjoint_and_repeatable(self):
        single=assign_batches(32,['compute']); dual=assign_batches(32,['compute','compute-2'])
        self.assertEqual(single['compute'],[list(range(0,32,2)),list(range(1,32,2))])
        self.assertEqual(dual,{'compute':[list(range(0,32,2))],'compute-2':[list(range(1,32,2))]})
        for plan in (single,dual):
            self.assertEqual(sorted(n for slots in plan.values() for slot in slots for n in slot),list(range(32)))
            self.assertEqual(sum(len(slots) for slots in plan.values()),2)

    def test_assignment_key_order_does_not_change_idempotence(self):
        worker, run = Worker('compute'),fixed_run(['compute','compute-2'])
        reordered=copy.deepcopy(run)
        reordered['assignment']=dict(reversed(list(run['assignment'].items())))
        try:
            worker.submit(reordered)
            repeated=worker.submit(run)
            self.assertEqual(repeated['id'],run['id'])
            worker.stop(run['id']); worker.thread.join(5)
            self.assertIsNone(worker.active_id)
        finally: worker.shutdown()

    def test_duplicate_assignment_and_group_cancellation(self):
        worker, run = Worker('compute'), fixed_run()
        try:
            worker.submit(run)
            wait_until(lambda:len(worker.processes)==2)
            processes=list(worker.processes)
            worker.submit(run)
            self.assertEqual(worker.processes,processes)
            changed=copy.deepcopy(run)
            changed['settings']['batch_count']=8
            changed['assignment']=assign_batches(8,['compute'])
            with self.assertRaises(Conflict): worker.submit(changed)
            started=time.monotonic()
            worker.stop(run['id']); worker.stop(run['id'])
            worker.thread.join(5)
            self.assertLess(time.monotonic()-started,5)
            self.assertTrue(all(p.poll() is not None for p in processes))
            self.assertEqual(worker.snapshot()['last_run']['state'],'cancelled')
        finally:
            worker.shutdown()

    def test_group_deadline_reaps_term_ignoring_processes(self):
        worker, run = Worker('compute'), fixed_run()
        run['deadline_unix']=time.time()+.5
        real_popen=subprocess.Popen
        def stubborn(*args,**kwargs):
            return real_popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'],**kwargs)
        with patch('shared.fixed_runner.subprocess.Popen',side_effect=stubborn):
            worker.submit(run)
            wait_until(lambda:len(worker.processes)==2)
            processes=list(worker.processes)
            worker.thread.join(5)
        self.assertTrue(all(p.poll() is not None for p in processes))
        self.assertEqual(worker.snapshot()['last_run']['state'],'failed')
        self.assertIn('deadline',worker.snapshot()['last_run']['error'])
        worker.shutdown()

    def test_snapshot_combining_and_duplicate_batch_rejection(self):
        run=fixed_run(['compute','compute-2'])
        parts={'compute':{'counters':{'cpu_batches':2500,'checksum':2500*UNIT_CHECKSUM,'fixed_batches':1},'elapsed_seconds':2,
                          'batch_results':[{'batch_id':0,'state':'completed'}]},
               'compute-2':{'counters':{'cpu_batches':1250,'checksum':1250*UNIT_CHECKSUM},'elapsed_seconds':3,'batch_results':[]}}
        combine(run,parts); combine(run,parts)
        self.assertEqual(run['counters']['cpu_batches'],3750)
        self.assertEqual(len(run['batch_results']),1)
        parts['compute-2']['batch_results']=[{'batch_id':0}]
        with self.assertRaises(ValueError): combine(run,parts)

    def test_missing_acknowledged_run_is_not_retried(self):
        coordinator=Coordinator(FakeRepository())
        run=fixed_run(['compute','compute-2'])
        coordinator.records[run['id']]=run; coordinator.active_id=run['id']
        coordinator.sent={(run['id'],s) for s in run['target_services']}
        states={s:{'active':None,'last_run':None} for s in run['target_services']}
        with patch.object(coordinator,'_http') as http:
            advance(coordinator,run,states)
        self.assertEqual(run['state'],'interrupted')
        self.assertIsNone(coordinator.active_id)
        self.assertFalse(any(call.args[1]=='/internal/runs' for call in http.call_args_list))
        coordinator.shutdown()

    def test_running_participants_update_parent_state(self):
        coordinator=Coordinator(FakeRepository())
        run=fixed_run(['compute','compute-2'])
        coordinator.active_id=run['id']
        coordinator.sent={(run['id'],s) for s in run['target_services']}
        states={s:{'active':{**run,'state':'running','elapsed_seconds':1},'last_run':None} for s in run['target_services']}
        with patch.object(coordinator,'_http'):
            advance(coordinator,run,states)
        self.assertEqual(run['state'],'running')
        coordinator.active_id=None
        coordinator.shutdown()

    def test_completed_work_wins_a_late_stop_race(self):
        coordinator=Coordinator(FakeRepository())
        run=fixed_run(['compute','compute-2'])
        run['state']='stopping'
        coordinator.active_id=run['id']
        coordinator.sent={(run['id'],s) for s in run['target_services']}
        states={}
        for service,slots in run['assignment'].items():
            ids=slots[0]
            part={**run,'state':'completed','elapsed_seconds':1,'counters':{
                'cpu_batches':len(ids)*2500,'checksum':len(ids)*2500*UNIT_CHECKSUM,'fixed_batches':len(ids)},
                'batch_results':[{'batch_id':i,'state':'completed'} for i in ids]}
            states[service]={'active':None,'last_run':part}
        with patch.object(coordinator,'_http'):
            advance(coordinator,run,states)
        self.assertEqual(run['state'],'completed')
        coordinator.shutdown()

    def test_missing_final_result_stops_other_slot(self):
        worker, run = Worker('compute'), fixed_run()
        real_popen=subprocess.Popen
        count=0
        def broken(*args,**kwargs):
            nonlocal count
            count+=1
            code='pass' if count==1 else 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'
            return real_popen([sys.executable,'-c',code],**kwargs)
        started=time.monotonic()
        with patch('shared.fixed_runner.subprocess.Popen',side_effect=broken):
            worker.submit(run)
            worker.thread.join(5)
        self.assertIsNone(worker.active_id)
        self.assertLess(time.monotonic()-started,5)
        self.assertEqual(worker.snapshot()['last_run']['state'],'failed')
        self.assertIn('final result',worker.snapshot()['last_run']['error'])
        worker.shutdown()


if __name__ == '__main__':
    unittest.main()
