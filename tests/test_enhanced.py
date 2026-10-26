from unittest.mock import MagicMock

import pytest

from linesignal.enhanced import ModelCallBudget, make_evidence_tool, run_enhanced


def test_tool_exposes_one_narrow_parameter_and_records_actual_invocation():
    reader = MagicMock()
    reader.inspect.return_value={'status':'observed','evidence':[]}
    trace=[]
    tool=make_evidence_tool(reader,trace)
    assert tool.tool_name == 'inspect_stop_window'
    result=tool('STOP-001')
    assert result['status'] == 'observed'
    reader.inspect.assert_called_once_with('STOP-001')
    assert trace[0]['input'] == {'incident_id':'STOP-001'}
    assert trace[0]['result']['status'] == 'observed'


def test_tool_read_budget_fails_closed():
    reader=MagicMock()
    reader.inspect.return_value={'status':'observed'}
    trace=[]
    tool=make_evidence_tool(reader,trace)
    tool('STOP-001'); tool('STOP-002')
    result=tool('STOP-003')
    assert reader.inspect.call_count == 2
    assert result['status'] == 'insufficient_evidence'


def test_parallel_tool_calls_cannot_exceed_read_budget():
    import threading,time
    from concurrent.futures import ThreadPoolExecutor
    reader=MagicMock()
    def read(incident_id):
        time.sleep(0.03)
        return {'status':'observed'}
    reader.inspect.side_effect=read
    trace=[]
    tool=make_evidence_tool(reader,trace)
    start=threading.Barrier(3)
    def invoke(incident_id):
        start.wait(timeout=2)
        return tool(incident_id)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(invoke,['STOP-001','STOP-002','STOP-003']))
    assert reader.inspect.call_count == 2
    assert len(trace) == 2
    assert sum(r['status']=='insufficient_evidence' for r in results) == 1


def test_model_budget_stops_run_instead_of_unbounded_retry():
    budget=ModelCallBudget(3)
    for _ in range(3):
        budget.before_model(None)
    with pytest.raises(RuntimeError,match='budget'):
        budget.before_model(None)


def test_model_budget_registers_one_hook():
    registry=MagicMock()
    ModelCallBudget().register_hooks(registry)
    registry.add_callback.assert_called_once()


def test_enhanced_result_requires_a_real_tool_invocation():
    from pathlib import Path
    from linesignal.evidence import analyse_incident
    reader=MagicMock()
    reader.inspect.return_value=analyse_incident((Path(__file__).parents[1]/'data/incidents/STOP-001.json').read_bytes())
    def factory(**kwargs):
        agent=MagicMock()
        def respond(prompt):
            kwargs['hooks'][0].before_model(None)
            kwargs['tools'][0]('STOP-001')
            agent.cancel.assert_called_once()
            assert agent.cancel.call_args.kwargs['after_current_tools'] is True
            return agent.cancel.call_args.kwargs['message']
        agent.side_effect=respond
        return agent
    result=run_enhanced('Investigate STOP-001',reader,object(),factory)
    assert result['tool_count'] == 1
    assert result['model_calls'] == 1
    assert result['trace'][0]['input']['incident_id'] == 'STOP-001'
    assert result['output_route']=='validated_evidence_renderer'
    assert '[E001]' in result['answer']


def test_tool_invokes_validated_output_callback():
    reader=MagicMock()
    reader.inspect.return_value={'status':'insufficient_evidence'}
    ready=MagicMock()
    make_evidence_tool(reader,[],ready)('STOP-001')
    ready.assert_called_once_with(reader.inspect.return_value)


def test_uninvoked_tool_is_a_failed_demonstration():
    with pytest.raises(RuntimeError,match='did not invoke'):
        run_enhanced('Investigate STOP-001',MagicMock(),object(),lambda **_:lambda p:'generic advice')


def test_ambiguous_incident_request_fails_before_model_call():
    factory=MagicMock()
    with pytest.raises(ValueError,match='one incident'):
        run_enhanced('Compare STOP-001 and STOP-002',MagicMock(),object(),factory)
    factory.assert_not_called()


def test_wrong_incident_selection_is_never_a_success():
    from pathlib import Path
    from linesignal.evidence import analyse_incident
    reader=MagicMock()
    reader.inspect.return_value=analyse_incident((Path(__file__).parents[1]/'data/incidents/STOP-002.json').read_bytes())
    def factory(**kwargs):
        agent=MagicMock()
        def respond(prompt):
            kwargs['tools'][0]('STOP-002')
            return agent.cancel.call_args.kwargs['message']
        agent.side_effect=respond
        return agent
    with pytest.raises(RuntimeError,match='different incident'):
        run_enhanced('Investigate STOP-001',reader,object(),factory)


def test_cli_writes_tool_trace_and_uses_fixed_bucket(monkeypatch,tmp_path):
    import json
    import boto3
    import linesignal.enhanced as module
    target=tmp_path/'after.json'
    client=object()
    factory=MagicMock(return_value=client)
    monkeypatch.setattr(boto3,'client',factory)
    monkeypatch.setattr(module,'run_enhanced',lambda prompt,reader:{'mode':'enhanced','trace':[{'tool':'inspect_stop_window'}]})
    monkeypatch.setattr('sys.argv',['enhanced','--bucket','demo-bucket','--out',str(target)])
    module.main()
    assert json.loads(target.read_text())['trace'][0]['tool']=='inspect_stop_window'
    assert factory.call_args.args == ('s3',)


def test_cli_requires_operator_selected_bucket(monkeypatch):
    import linesignal.enhanced as module
    monkeypatch.delenv('LINESIGNAL_BUCKET',raising=False)
    monkeypatch.setattr('sys.argv',['enhanced'])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
