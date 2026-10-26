import importlib.util
import json
from pathlib import Path

import pytest

from linesignal.evidence import analyse_incident

spec=importlib.util.spec_from_file_location('make_demo_data',Path(__file__).parents[1]/'scripts/make_demo_data.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('incident_id,status',[
    ('STOP-001','observed'),('STOP-002','insufficient_evidence'),('STOP-003','no_pre_stop_anomaly')])
def test_generated_fixture_has_the_documented_semantic_outcome(incident_id,status):
    raw=json.dumps(module.make_incident(incident_id)).encode()
    result=analyse_incident(raw)
    assert result['status']==status
    assert result['synthetic'] is True


def test_generation_is_reproducible_and_writes_only_three_fixtures(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    module.main()
    first={p.name:p.read_bytes() for p in Path('data/incidents').glob('*.json')}
    module.main()
    assert len(first)==3
    assert first=={p.name:p.read_bytes() for p in Path('data/incidents').glob('*.json')}
