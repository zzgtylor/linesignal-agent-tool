# LineSignal — baseline

A read-only production-line troubleshooting agent built with the Strands Agents SDK. This baseline has no tools and cannot inspect incident telemetry. It explicitly distinguishes hypotheses from evidence.

Run `python -m pip install -e .[test]`, start Ollama on loopback with `qwen3:0.6b`, then run `python -m linesignal.agent`.

Baseline created on October 26, 2026. The tool extension will be a separate commit so the before/after is reproducible.

Tests: `python -m pytest -xvs --cov=linesignal`.
