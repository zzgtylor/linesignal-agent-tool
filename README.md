# LineSignal

One S3 replay tool gives a maintenance assistant timestamped evidence of what
changed before a production-line stop. All demo telemetry is synthetic.

## Before and after

The baseline explains generic maintenance and refuses incident-specific
conclusions through a deterministic no-evidence gate. The extended Strands
agent can choose exactly one tool: `inspect_stop_window(incident_id)`.
The tool reads an allowlisted Amazon S3 object, validates a 60-second window
of 2-second samples, and returns sustained deviations with source hashes.

The model selects the tool. Validated data generates the report. The tool uses
`agent.cancel(after_current_tools=True, message=brief)` to return directly,
without an unverified second generative expansion. A recorded `cancelled`
stop reason is the intentional return after the tool. Temporal precedence is
not causal proof. Ties and missing data never become a unique order claim.

The baseline was built during this challenge, then extended; it is not claimed
to be an older production system. Guarded baseline commit:
`f5b49dd78aa23baeeb7c86f2c0b080948b392963`.

## Run

Use Python 3.11+, `pip install -e '.[test]'`, and Ollama on loopback port 11434
with `qwen3:1.7b`. The demonstration runtime is AWS CloudShell, which is
interactive and temporary rather than always-on hosting. Bedrock is optional
and was not used because the account required additional verification.

```bash
python -m linesignal.agent --out demo/baseline.json
python scripts/setup_s3.py
# Export the new bucket name from demo/deployment.json as LINESIGNAL_BUCKET.
python -m linesignal.enhanced --out demo/enhanced.json
python -m linesignal.enhanced --prompt 'Investigate STOP-002 on line L1' --out demo/missing.json
```

Setup creates a new private, encrypted, versioned bucket in us-west-2 and
uploads only three validated synthetic fixtures. It does not modify an existing
bucket. Ordinary S3 storage/request charges may apply; this route has no hosted
model API charge. AWS credentials are never committed. The interactive demo
uses the current CloudShell session; for deployment, use a separate reader role
limited to `s3:GetObject` on the three required objects.

| Case | Expected observation |
| --- | --- |
| STOP-001 | Pressure deviation 18 seconds before stop; photoeye blockage 6 seconds before stop. |
| STOP-002 | Four missing samples: refuse to establish sequence. |
| STOP-003 | No monitored threshold deviation: cause remains unknown. |

Thresholds are fixture assumptions, not manufacturer limits. Two consecutive
abnormal samples are required. The tool never controls machinery or authorizes
a restart. Physical checks require a trained operator and site isolation.

## Verification and reuse

```bash
python -m compileall -q linesignal scripts tests
python -m pytest -xvs --cov=linesignal --cov=scripts --cov-report=term-missing
python -m pip wheel --no-deps --no-build-isolation .
```

Tests cover gaps, duplicates, ties, strict types, invalid numbers, arbitrary
paths, oversized objects, stream closure, private fixture setup, call budgets
and report grounding. Mocked tests do not establish live model quality.
Actual run traces and a public walkthrough are added after live verification.

This is a read-only prototype, not a fault predictor. It does not prove
causation or demonstrate a measured reduction in downtime. Its reusable pattern
is the boundary between model-selected retrieval and auditable evidence.
