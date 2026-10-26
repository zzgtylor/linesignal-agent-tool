import json
from pathlib import Path

from linesignal.evidence import analyse_incident
from linesignal.reporting import render_brief


def result(incident_id):
    return analyse_incident((Path(__file__).parents[1]/'data/incidents'/f'{incident_id}.json').read_bytes())


def test_observations_are_rendered_from_validated_numbers():
    text=render_brief(result('STOP-001'))
    assert '10:14:42Z' in text and '18 seconds' in text
    assert '3.8' in text and '[E001]' in text
    assert 'synthetic' in text.lower()
    assert 'not causal proof' in text
    assert 'temperature' not in text


def test_missing_samples_never_generate_diagnosis():
    text=render_brief(result('STOP-002'))
    assert 'Cannot establish' in text
    assert 'missing_samples' in text
    assert '[E001]' not in text


def test_normal_signals_do_not_imply_no_fault():
    text=render_brief(result('STOP-003'))
    assert 'cause remains unknown' in text


def test_tied_signals_are_explicitly_unordered():
    value=result('STOP-001')
    value['status']='simultaneous_deviations'
    value['first_observed']=None
    text=render_brief(value)
    assert 'cannot be ordered' in text
