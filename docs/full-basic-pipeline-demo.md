# Full Basic pipeline demo

Run the complete consumer-agnostic Basic pipeline from the repository root:

```bash
python scripts/demo_full_basic_pipeline.py
```

The command deterministically exercises Context -> Orchestrator -> explicit human demo Builder assignment -> Builder -> Verifier. It writes inspectable evidence under `demo-output/full-basic-pipeline/`:

- `context.json` and `context-run.json`
- `execution-plan.json` and `orchestrator-run.json`
- `builder-task.json`, which is the explicit assignment evidence and is distinct from Orchestrator `WOULD_INVOKE` planning
- `change-set.json` and `builder-run.json`
- `verification-report.json`
- `run-summary.json`, a machine-readable index and boundary summary

This is real platform decision and evidence logic with deterministic generic fixtures. Basic tier does not write to a repository, execute candidate code, or implicitly dispatch the Builder. `change-set.json` is proposed evidence only, and `run-summary.json` records zero repository writes, zero candidate-code executions, and zero Orchestrator dispatches.

For regression coverage, `tests/test_full_basic_pipeline_demo.py` verifies the successful deterministic path and a deliberately corrupted plan-to-Builder handoff that must fail closed before a run summary is emitted.
