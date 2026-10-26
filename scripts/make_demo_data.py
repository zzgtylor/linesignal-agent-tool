"""Create three clearly synthetic, bounded incident records for S3."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def make_incident(incident_id):
    stop=datetime(2026,10,26,10,15,tzinfo=timezone.utc)
    payload={'schema_version':1,'synthetic':True,'incident_id':incident_id,
        'line_id':'L1','stop_at':stop.isoformat().replace('+00:00','Z'),
        'sample_period_s':2,'samples':[]}
    for offset in range(-60,1,2):
        payload['samples'].append({
            'at':(stop+timedelta(seconds=offset)).isoformat().replace('+00:00','Z'),
            'pressure_bar':6.1 if offset < -18 or incident_id == 'STOP-003' else 3.8,
            'motor_current_a':5.9,
            'photoeye_blocked':offset >= -6 and incident_id != 'STOP-003',
            'conveyor_running':offset < 0})
    if incident_id == 'STOP-002':
        del payload['samples'][10:14]
    return payload


def main():
    root=Path('data/incidents')
    root.mkdir(parents=True,exist_ok=True)
    for incident_id in ['STOP-001','STOP-002','STOP-003']:
        (root/f'{incident_id}.json').write_text(json.dumps(make_incident(incident_id),indent=2)+'\n')
    print('Created three synthetic demo incident files.')


if __name__ == '__main__':
    main()
