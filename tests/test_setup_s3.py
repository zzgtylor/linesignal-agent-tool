import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

spec=importlib.util.spec_from_file_location('setup_s3',Path(__file__).parents[1]/'scripts/setup_s3.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_new_bucket_is_private_versioned_and_has_only_three_demo_objects():
    client=MagicMock()
    root=Path(__file__).parents[1]/'data/incidents'
    result=module.provision(client,'linesignal-evidence-012345abcd',root)
    client.create_bucket.assert_called_once()
    assert client.put_public_access_block.call_args.kwargs['PublicAccessBlockConfiguration']=={
        'BlockPublicAcls':True,'IgnorePublicAcls':True,'BlockPublicPolicy':True,'RestrictPublicBuckets':True}
    assert client.put_bucket_versioning.call_args.kwargs['VersioningConfiguration']['Status']=='Enabled'
    assert client.put_object.call_count==3
    assert {call.kwargs['Key'] for call in client.put_object.call_args_list}=={
        'incidents/STOP-001.json','incidents/STOP-002.json','incidents/STOP-003.json'}
    assert result['synthetic'] is True


def test_invalid_bucket_name_is_rejected_before_mutation():
    client=MagicMock()
    with pytest.raises(ValueError):
        module.provision(client,'existing-production-bucket',Path('/missing'))
    assert not client.mock_calls


def test_missing_data_is_detected_before_creation(tmp_path):
    client=MagicMock()
    with pytest.raises(FileNotFoundError):
        module.provision(client,'linesignal-evidence-012345abcd',tmp_path)
    assert not client.mock_calls


def test_cli_writes_manifest_only_after_success(monkeypatch,tmp_path):
    import boto3,json
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv',['setup_s3','--bucket','linesignal-evidence-012345abcd'])
    monkeypatch.setattr(boto3,'client',lambda *a,**k:object())
    monkeypatch.setattr(module,'provision',lambda *a,**k:{'bucket':'linesignal-evidence-012345abcd','synthetic':True})
    module.main()
    assert json.loads(Path('demo/deployment.json').read_text())['synthetic'] is True


def test_cli_failure_does_not_publish_a_completed_manifest(monkeypatch,tmp_path):
    import boto3
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv',['setup_s3'])
    monkeypatch.setattr(boto3,'client',lambda *a,**k:object())
    def fail(*a,**k):
        raise RuntimeError('provisioning failed')
    monkeypatch.setattr(module,'provision',fail)
    with pytest.raises(RuntimeError):
        module.main()
    assert not Path('demo/deployment.json').exists()
