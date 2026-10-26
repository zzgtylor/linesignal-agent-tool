"""One bounded S3 tool: replay a pre-stop window, without claiming causation."""
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone

MAX_BYTES = 128 * 1024
OBJECTS = {'STOP-001': 'incidents/STOP-001.json',
           'STOP-002': 'incidents/STOP-002.json',
           'STOP-003': 'incidents/STOP-003.json'}
LIMITATIONS = ['Temporal precedence is not causal proof.',
               'Sampled signals may miss faster events or unmeasured factors.',
               'Read-only evidence; a trained operator must authorize physical work.']


def _time(value):
    if not isinstance(value, str):
        raise ValueError('invalid_timestamp')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        raise ValueError('invalid_timestamp') from None
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError('timestamp_must_be_utc')
    return result


def _iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _insufficient(reasons, **metadata):
    return dict(status='insufficient_evidence', reason_codes=reasons,
                first_observed=None, earliest_group=[], evidence=[], not_causal_proof=True,
                limitations=LIMITATIONS, **metadata)


def analyse_incident(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('payload_size')
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('invalid_json') from None
    required = {'schema_version','synthetic','incident_id','line_id','stop_at',
                'sample_period_s','samples'}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError('invalid_schema')
    if type(payload['schema_version']) is not int or payload['schema_version'] != 1 or type(payload['synthetic']) is not bool:
        raise ValueError('invalid_schema_version')
    if not isinstance(payload['incident_id'],str) or not re.fullmatch(r'STOP-\d{3}',payload['incident_id']):
        raise ValueError('invalid_incident')
    if not isinstance(payload['line_id'],str) or not re.fullmatch(r'L\d{1,3}',payload['line_id']):
        raise ValueError('invalid_line')
    if type(payload['sample_period_s']) is not int or payload['sample_period_s'] != 2:
        raise ValueError('unsupported_sampling_period')
    stop = _time(payload['stop_at'])
    samples = payload['samples']
    if not isinstance(samples,list) or not 3 <= len(samples) <= 1000:
        raise ValueError('sample_count')
    rows = []
    for sample in samples:
        if not isinstance(sample,dict) or set(sample) != {'at','pressure_bar','motor_current_a','photoeye_blocked','conveyor_running'}:
            raise ValueError('invalid_sample_schema')
        at = _time(sample['at'])
        if not stop-timedelta(seconds=60) <= at <= stop:
            raise ValueError('sample_outside_window')
        for metric,maximum in [('pressure_bar',20),('motor_current_a',100)]:
            value=sample[metric]
            if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError('invalid_measurement')
        if any(type(sample[key]) is not bool for key in ['photoeye_blocked','conveyor_running']):
            raise ValueError('invalid_boolean')
        rows.append(dict(sample, time=at))
    rows.sort(key=lambda row:row['time'])
    timestamps=[row['time'] for row in rows]
    reasons=[]
    if len(set(timestamps)) != len(timestamps):
        reasons.append('duplicate_timestamps')
    if (timestamps[0] != stop-timedelta(seconds=60) or timestamps[-1] != stop
        or len(set(timestamps)) != 31
        or any((b-a).total_seconds() != 2 for a,b in zip(timestamps,timestamps[1:]))):
        reasons.append('missing_samples')
    if rows[-1]['time'] != stop or rows[-1]['conveyor_running']:
        reasons.append('missing_stop_sample')
    if any(not row['conveyor_running'] for row in rows[:-1]):
        reasons.append('multiple_stop_states')
    metadata={'incident_id':payload['incident_id'],'line_id':payload['line_id'],
              'synthetic':payload['synthetic'],'stop_at':_iso(stop),
              'window_start':_iso(stop-timedelta(seconds=60)),
              'sample_count':len(rows),'sample_period_s':2}
    predicates={
        'pressure_bar':lambda row:row['pressure_bar'] < 5,
        'motor_current_a':lambda row:row['motor_current_a'] > 10,
        'photoeye_blocked':lambda row:row['photoeye_blocked'],
    }
    if any(test(rows[0]) or test(rows[1]) for test in predicates.values()):
        reasons.append('abnormal_at_window_start')
    if reasons:
        return _insufficient(reasons, **metadata)
    candidates=[]
    thresholds={'pressure_bar':'< 5 bar','motor_current_a':'> 10 A',
                'photoeye_blocked':'true for at least two samples'}
    for metric,test in predicates.items():
        for i,row in enumerate(rows[:-1]):
            next_row=rows[i+1]
            if next_row['time'] < stop and test(row) and test(next_row):
                candidates.append({'metric':metric,'at':_iso(row['time']),
                    'value':row[metric],'threshold':thresholds[metric],
                    'baseline_value':rows[0][metric],
                    'lead_seconds':int((stop-row['time']).total_seconds()),
                    'consecutive_samples':2})
                break
    candidates.sort(key=lambda item:(item['at'],item['metric']))
    for i,item in enumerate(candidates,1):
        item['evidence_id']=f'E{i:03d}'
    earliest=[item for item in candidates if item['at'] == candidates[0]['at']] if candidates else []
    first=earliest[0] if len(earliest)==1 else None
    status='simultaneous_deviations' if len(earliest)>1 else ('observed' if first else 'no_pre_stop_anomaly')
    return dict(status=status,
                reason_codes=[],first_observed=first,earliest_group=earliest,evidence=candidates,
                not_causal_proof=True,limitations=LIMITATIONS,**metadata)


class S3EvidenceReader:
    """The caller controls only an incident ID, never a bucket, path, or URL."""
    def __init__(self,client,bucket):
        self.client,self.bucket=client,bucket

    def inspect(self,incident_id):
        if not isinstance(incident_id,str) or incident_id not in OBJECTS:
            return _insufficient(['incident_not_allowlisted'])
        try:
            response=self.client.get_object(Bucket=self.bucket,Key=OBJECTS[incident_id])
            body=response['Body']
            try:
                if response.get('ContentLength',0) > MAX_BYTES:
                    return _insufficient(['payload_size'])
                raw=body.read(MAX_BYTES+1)
            finally:
                body.close()
            result=analyse_incident(raw)
            if result['incident_id'] != incident_id:
                return _insufficient(['incident_mismatch'])
            result['source']={'service':'Amazon S3','key':OBJECTS[incident_id],
                'sha256':hashlib.sha256(raw).hexdigest(),
                'etag':response.get('ETag'),'version_id':response.get('VersionId')}
            return result
        except ValueError:
            return _insufficient(['invalid_telemetry'])
        except Exception:
            return _insufficient(['source_unavailable'])
