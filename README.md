# LineSignal — guarded baseline

A read-only production-line assistant built with the Strands Agents SDK and an open model on AWS CloudShell. It can explain generic troubleshooting. A deterministic no-evidence gate refuses incident-specific conclusions when no telemetry tool is registered. The model is not trusted to invent observations.

This baseline has zero tools. The extension is a separate commit. Baseline created during the October 2026 weekend challenge, not represented as a pre-existing production system.

Install with `python -m pip install -e .[test]`. Start Ollama on loopback and pull `qwen3:1.7b`. Run `python -m linesignal.agent` for the incident gate or pass a generic maintenance question with `--prompt`.

Tests: `python -m pytest -xvs --cov=linesignal`.
