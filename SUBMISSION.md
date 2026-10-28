# LineSignal: Give a Maintenance Agent an S3 Evidence Replay Tool

A maintenance assistant can explain an air-pressure fault or a blocked photoeye. Without telemetry, it cannot tell an operator which changed first. LineSignal adds one tool that turns that gap into an inspectable, timestamped evidence report.

All demonstration telemetry is synthetic. The executions were performed on AWS CloudShell against private Amazon S3 objects. The public replay and captioned walkthrough show saved execution records rather than a live machine connection.

## The agent before the tool

The baseline gives generic maintenance explanations. Incident-specific prompts hit a deterministic no-evidence gate: it says it cannot determine what changed first, because it has no telemetry access. It has zero tools.

The baseline was built during this challenge and then extended. It is not claimed to be a pre-existing production deployment. The guarded baseline is preserved at commit `f5b49dd78aa23baeeb7c86f2c0b080948b392963`.

## One new tool: inspect_stop_window

The extended Strands agent receives exactly one tool: `inspect_stop_window(incident_id)`. The model chooses whether to call it and supplies an incident ID. The tool maps that ID to one of three allowlisted S3 objects; the model cannot supply an arbitrary bucket, URL, or object path.

The tool reads the 60 seconds before a recorded stop. It validates UTC timestamps, strict field types, finite numbers, duplicate samples, and continuity at two-second intervals. It looks for two consecutive abnormal samples, preserves simultaneous deviations as ties, and attaches the S3 object version and SHA-256 hash to the result.

Validated data generates the final brief. After the current tool completes, Strands returns that brief through `agent.cancel(after_current_tools=True, message=brief)`. The recorded `cancelled` stop reason is intentional: the agent does not add an unverified second generative explanation to the evidence.

The invocation also checks that the selected incident matches the user's request, limits S3 reads with an atomic budget, and caps model calls. It never issues a machine-control or restart command.

## Before and after, with three recorded AWS cases

The baseline response to “Investigate STOP-001” is: it cannot determine the order without timestamped sensor evidence. After adding the tool, the agent produces the following distinct outcomes:

| Case | Recorded result | What the assistant can now say |
| --- | --- | --- |
| STOP-001 | Pressure falls from 6.1 to 3.8 bar at 10:14:42 UTC; the photoeye becomes blocked at 10:14:54 UTC; the recorded stop is at 10:15:00 UTC. | The first sustained monitored deviation is pressure, 18 seconds before the stop; blockage follows 6 seconds before the stop. |
| STOP-002 | Four samples are missing from the requested window. | Evidence is insufficient; it refuses to establish an event sequence. |
| STOP-003 | The complete window contains no sustained monitored threshold deviation. | No monitored pre-stop anomaly was observed; the cause remains unknown. |

The tool unlocks access to evidence and a defensible ordering claim. Temporal precedence does not prove causation. The thresholds are demonstration assumptions, not manufacturer limits.

## AWS implementation and verification

Amazon S3 stores the three synthetic JSON fixtures in a private, versioned bucket with AES-256 server-side encryption. The captured deployment check records all four public-access blocks enabled and confirms that object versions match the execution evidence.

AWS CloudShell in `us-west-2` runs Strands Agents with Qwen3:1.7b through Ollama on loopback. This open-model route was used because Bedrock access required further account verification. CloudShell is an interactive, temporary runtime; the replay is not an always-on hosted agent.

The [recorded verification](demo/verified_runs.json) is bound to runtime source commit `fc66ef59c8ce975441adf250dc93fa83c8b71e75`, with an Ollama HTTP 200 health check and 72 passing Python tests. The repository also contains five replay tests covering recorded-case selection, separate missing/unknown outcomes, timestamp fidelity, walkthrough scene coverage, and visible chart gaps.

Recorded enhanced-case execution times were approximately 117, 6, and 6 seconds. These are observations from three executions, not a latency benchmark or a claim about warm-start performance.

The [fixtures](data/incidents) and [source](linesignal) let a reviewer reproduce the analysis and compare its evidence hashes. The [replay](https://zzgtylor.github.io/linesignal-agent-tool/) presents the baseline, three recorded outcomes, and the timeline.

## Why this pattern is useful

A maintenance brief is more useful when it can point to a specific observed change and explain when the records cannot support a conclusion. The reusable pattern is a model-selected retrieval tool whose validated output remains auditable through the final response.

A builder can adapt the allowlist and schema for another equipment log without giving the model unrestricted storage access. Production use would require equipment-specific limits, clock-quality checks, operator procedures, a least-privilege reader role, and a suitable durable runtime.

LineSignal is a read-only prototype. It does not diagnose every failure, prove a cause, authorize physical work, or demonstrate a measured reduction in downtime. Higher-frequency events and unmeasured signals may change the interpretation.

## Demonstration and submission status

A 126-second, 1280×720 H.264 captioned video has been produced and checked. Public video upload and the AWS project submission have not yet been verified. The public-video URL must be added to the AWS demo field before claiming a completed submission; the replay URL is supplementary.

Prepared on October 28, 2026. The challenge page shows an October 26 deadline. This repository document is not evidence of an on-time entry or a successful late submission.
