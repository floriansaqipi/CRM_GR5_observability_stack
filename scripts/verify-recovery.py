"""Exercise controller loss without shutdown hooks and the database document cap."""
from datetime import datetime, timezone
import json
import time
from lab_api import ROOT, api, compose, document_count, ready, result, start, wait_for


def main():
    wait_for(ready, 30)
    run = start('memory', duration=60, name='Verification: abrupt controller loss')
    wait_for(lambda: api('/api/runs/'+run['id'])['counters'].get('allocated_mib',0)>0)
    compose('kill','--signal','SIGKILL','controller')
    compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','controller')
    wait_for(ready, 30)
    interrupted = result(run['id'], 10)
    checks = {'abrupt_controller_loss_reconciled': interrupted['state']=='interrupted'}
    run = start('database','high',15,name='Verification: bounded document slots',overrides={'rate_per_second':20})
    counts = []
    while True:
        counts.append(document_count(run['id']))
        current = api('/api/runs/'+run['id'])
        if current['state'] not in ('starting','running','stopping'):
            break
        time.sleep(1)
    checks['database_cap_exercised'] = max(counts)==128 and current['counters']['database_cycles']>128
    checks['database_cap_never_exceeded'] = max(counts)<=128
    checks['document_cap_run_completed'] = current['state']=='completed'
    checks['temporary_documents_released'] = document_count(run['id'])==0
    output = ROOT/'docs/evidence/stage2/recovery.json'
    output.write_text(json.dumps({'recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
                                 'interrupted_run':interrupted,'database_run':current,'document_counts':counts},indent=2)+'\n',encoding='utf-8')
    for name, passed in checks.items():
        print(f'{"PASS" if passed else "FAIL"}: {name}',flush=True)
    if not all(checks.values()):
        raise AssertionError('Additional recovery verification failed.')


if __name__=='__main__':
    main()
