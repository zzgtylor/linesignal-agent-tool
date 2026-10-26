from unittest.mock import MagicMock

import pytest

from linesignal.agent import SYSTEM_PROMPT, build_agent, run_agent, run_baseline, model_id


def test_baseline_has_no_tools():
    factory = MagicMock()
    build_agent(model=object(), agent_factory=factory)
    assert factory.call_args.kwargs['tools'] == []
    assert factory.call_args.kwargs['system_prompt'] == SYSTEM_PROMPT


def test_tool_extension_changes_only_tool_registration():
    factory = MagicMock()
    tool = object()
    model = object()
    build_agent(model=model, evidence_tool=tool, agent_factory=factory)
    assert factory.call_args.kwargs['tools'] == [tool]
    assert factory.call_args.kwargs['model'] is model


@pytest.mark.parametrize('prompt', ['', '  ', 'x' * 4001, 42], ids=['empty','blank','too_long','not_text'])
def test_reject_invalid_prompts(prompt):
    with pytest.raises(ValueError):
        run_agent(prompt, lambda _: 'bad')


def test_answer_and_trace_preserved():
    agent = MagicMock(return_value='Cannot establish a cause without telemetry.')
    result = run_agent('Investigate STOP-001', agent)
    assert result['answer'].startswith('Cannot establish')
    agent.assert_called_once_with('Investigate STOP-001')


def test_system_requires_evidence_and_human_safety():
    assert 'Never invent' in SYSTEM_PROMPT
    assert 'read-only' in SYSTEM_PROMPT
    assert 'causation' in SYSTEM_PROMPT


def test_default_factory(monkeypatch):
    import strands
    factory = MagicMock()
    monkeypatch.setattr(strands, 'Agent', factory)
    build_agent(model='test-model')
    assert factory.call_args.kwargs['callback_handler'] is None


def test_model_configuration_is_bounded(monkeypatch):
    from linesignal.agent import make_model
    import strands.models
    factory = MagicMock()
    monkeypatch.setattr(strands.models, 'BedrockModel', factory)
    monkeypatch.setenv('LINESIGNAL_MODEL', 'test-model')
    monkeypatch.setenv('LINESIGNAL_PROVIDER', 'bedrock')
    make_model()
    assert factory.call_args.kwargs['model_id'] == 'test-model'
    assert factory.call_args.kwargs['max_tokens'] == 900
    assert factory.call_args.kwargs['temperature'] == 0


def test_ollama_configuration_uses_loopback_and_disables_thinking(monkeypatch):
    from linesignal.agent import make_model
    import strands.models.ollama
    factory = MagicMock()
    monkeypatch.setattr(strands.models.ollama, 'OllamaModel', factory)
    monkeypatch.setenv('LINESIGNAL_PROVIDER', 'ollama')
    monkeypatch.delenv('LINESIGNAL_MODEL', raising=False)
    make_model()
    assert factory.call_args.kwargs['host'] == 'http://127.0.0.1:11434'
    assert factory.call_args.kwargs['additional_args']['think'] is False
    assert factory.call_args.kwargs['max_tokens'] <= 900


def test_unknown_provider_fails_explicitly(monkeypatch):
    from linesignal.agent import make_model
    monkeypatch.setenv('LINESIGNAL_PROVIDER', 'unknown')
    with pytest.raises(ValueError,match='provider'):
        make_model()


def test_cli_saves_real_result(monkeypatch, tmp_path):
    import linesignal.agent as module
    target = tmp_path / 'nested' / 'before.json'
    monkeypatch.setattr('sys.argv', ['agent', '--prompt', 'Describe generic troubleshooting', '--out', str(target)])
    monkeypatch.setattr(module, 'make_model', lambda: object())
    monkeypatch.setattr(module, 'build_agent', lambda model: lambda prompt: 'No telemetry available')
    module.main()
    import json
    result = json.loads(target.read_text())
    assert result['mode'] == 'baseline'
    assert result['tool_count'] == 0
    assert result['answer'] == 'No telemetry available'


def test_model_failure_is_never_reported_as_success():
    def failing(_):
        raise RuntimeError('inference unavailable')
    with pytest.raises(RuntimeError, match='inference unavailable'):
        run_agent('Investigate STOP-001', failing)


def test_baseline_incident_gate_does_not_request_unverifiable_diagnosis():
    agent=MagicMock()
    result=run_baseline('Investigate STOP-001',agent)
    assert 'cannot determine' in result['answer'].lower()
    assert result['output_route']=='no_evidence_gate'
    agent.assert_not_called()


def test_baseline_can_answer_generic_questions():
    agent=MagicMock(return_value='Possible causes include sensor misalignment and a jam.')
    assert 'Possible causes' in run_baseline('List generic causes of conveyor stops',agent)['answer']
    agent.assert_called_once()


@pytest.mark.parametrize('provider,expected',[('ollama','qwen3:1.7b'),('bedrock','amazon.nova-lite-v1:0')])
def test_provider_model_metadata_matches_configuration(monkeypatch,provider,expected):
    monkeypatch.setenv('LINESIGNAL_PROVIDER',provider)
    monkeypatch.delenv('LINESIGNAL_MODEL',raising=False)
    assert model_id()==expected
