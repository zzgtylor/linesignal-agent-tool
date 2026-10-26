"""LineSignal with exactly one new evidence tool."""
import argparse
import json
import os
import re
import threading
from pathlib import Path

from strands import Agent, tool
from strands.hooks import BeforeModelCallEvent, HookProvider

from .agent import build_agent, make_model, run_agent, model_id
from .evidence import S3EvidenceReader, _insufficient
from .reporting import render_brief


class ModelCallBudget(HookProvider):
    def __init__(self, limit=4):
        self.limit,self.calls=limit,0

    def before_model(self,event):
        self.calls+=1
        if self.calls > self.limit:
            raise RuntimeError('Model call budget exhausted')

    def register_hooks(self,registry):
        registry.add_callback(BeforeModelCallEvent,self.before_model)


def make_evidence_tool(reader,trace,on_ready=None):
    reservation_lock=threading.Lock()
    read_count=0
    @tool
    def inspect_stop_window(incident_id: str) -> dict:
        """Inspect the 60 seconds before a line stop using bounded S3 telemetry.

        Returns timestamped, sustained deviations, source hashes and data-quality
        status. Temporal order is not causal proof. No machine control.

        Args:
            incident_id: One of STOP-001, STOP-002 or STOP-003.
        """
        nonlocal read_count
        with reservation_lock:
            if read_count >= 2:
                return _insufficient(['tool_read_budget_exhausted'])
            read_count+=1
        result=reader.inspect(incident_id)
        with reservation_lock:
            trace.append({'tool':'inspect_stop_window','input':{'incident_id':incident_id},
                          'result':result})
        if on_ready is not None:
            on_ready(result)
        return result
    return inspect_stop_window


def run_enhanced(prompt,reader,model=None,agent_factory=None):
    incidents=set(re.findall(r'\bSTOP-\d{3}\b',prompt)) if isinstance(prompt,str) else set()
    if len(incidents)!=1:
        raise ValueError('Provide exactly one incident ID.')
    trace=[]
    budget=ModelCallBudget()
    def factory(**kwargs):
        return (agent_factory or Agent)(hooks=[budget],**kwargs)
    def on_ready(evidence):
        agent.cancel(message=render_brief(evidence),after_current_tools=True)
    agent=build_agent(model if model is not None else make_model(),
                      make_evidence_tool(reader,trace,on_ready),factory)
    result=run_agent(prompt,agent)
    if not trace:
        raise RuntimeError('Model did not invoke the evidence tool; run is not a successful demonstration.')
    if trace[-1]['input']['incident_id'] != next(iter(incidents)):
        raise RuntimeError('Model selected a different incident; no successful result is recorded.')
    result['answer']=render_brief(trace[-1]['result'])
    result.update(mode='enhanced',tool_count=1,trace=trace,
                  output_route='validated_evidence_renderer',
                  model_calls=budget.calls,provider=os.getenv('LINESIGNAL_PROVIDER','ollama'),
                  model=model_id())
    return result


def main():
    import boto3
    from botocore.config import Config
    parser=argparse.ArgumentParser()
    parser.add_argument('--bucket',default=os.getenv('LINESIGNAL_BUCKET'))
    parser.add_argument('--prompt',default='Investigate STOP-001.')
    parser.add_argument('--out',default='demo/enhanced.json')
    args=parser.parse_args()
    if not args.bucket:
        parser.error('Provide --bucket or LINESIGNAL_BUCKET; the bucket is never selected by the model.')
    client=boto3.client('s3',region_name=os.getenv('AWS_REGION','us-west-2'),
        config=Config(connect_timeout=10,read_timeout=20,
                      retries={'max_attempts':2,'mode':'standard'}))
    result=run_enhanced(args.prompt,S3EvidenceReader(client,args.bucket))
    target=Path(args.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
