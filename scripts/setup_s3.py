"""Create a new private, versioned S3 bucket containing only synthetic demos."""
import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

from linesignal.evidence import OBJECTS, analyse_incident


def provision(client,bucket,root):
    if not re.fullmatch(r'linesignal-evidence-[0-9a-f]{10}',bucket):
        raise ValueError('Use a new project-specific bucket name.')
    documents=[]
    for incident_id,key in OBJECTS.items():
        raw=(root/f'{incident_id}.json').read_bytes()
        record=analyse_incident(raw)
        if record['incident_id'] != incident_id or record['synthetic'] is not True:
            raise ValueError('Only validated synthetic fixtures can be uploaded.')
        documents.append((key,raw))
    client.create_bucket(Bucket=bucket,CreateBucketConfiguration={'LocationConstraint':'us-west-2'})
    client.put_public_access_block(Bucket=bucket,PublicAccessBlockConfiguration={
        'BlockPublicAcls':True,'IgnorePublicAcls':True,
        'BlockPublicPolicy':True,'RestrictPublicBuckets':True})
    client.put_bucket_versioning(Bucket=bucket,VersioningConfiguration={'Status':'Enabled'})
    client.put_bucket_encryption(Bucket=bucket,ServerSideEncryptionConfiguration={
        'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]})
    manifest=[]
    for key,raw in documents:
        response=client.put_object(Bucket=bucket,Key=key,Body=raw,
                                  ContentType='application/json',ServerSideEncryption='AES256')
        manifest.append({'key':key,'sha256':hashlib.sha256(raw).hexdigest(),
                         'version_id':response.get('VersionId')})
    return {'bucket':bucket,'region':'us-west-2','synthetic':True,'objects':manifest}


def main():
    import boto3
    from botocore.config import Config
    parser=argparse.ArgumentParser()
    parser.add_argument('--bucket',default=f'linesignal-evidence-{uuid.uuid4().hex[:10]}')
    args=parser.parse_args()
    client=boto3.client('s3',region_name='us-west-2',
        config=Config(connect_timeout=10,read_timeout=20,retries={'max_attempts':2,'mode':'standard'}))
    result=provision(client,args.bucket,Path('data/incidents'))
    Path('demo').mkdir(exist_ok=True)
    Path('demo/deployment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
