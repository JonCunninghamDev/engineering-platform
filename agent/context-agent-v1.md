# Context Agent v1

The Context Agent sits between human/task intake and orchestration. Its responsibility is to determine whether downstream work has sufficient scoped context, not to plan or execute the downstream work itself.

## Independent operating dimensions

Every run declares three independent dimensions:

- **service tier**: how much of the Context role is implemented for the run;
- **autonomy**: advisory, supervised, or policy-governed authority;
- **mode**: demo, test, or production execution semantics.

`v1.0.0` implements only the **Basic** service tier. Requests for Managed or Full fail closed rather than silently borrowing planned capabilities.

## Basic tier

Basic can:

1. inspect a `context-contract/v1` workflow contract;
2. normalize context explicitly supplied to the run;
3. identify missing required and recommended fields;
4. detect explicit contradictory values for the same context key;
5. formulate questions for missing required context;
6. produce a `context-manifest/v1` handoff.

Basic does **not** retrieve external context, verify provenance, judge freshness, maintain context continuously, classify sensitivity, or enrich context from external systems. Demo output displays those planned higher-tier capabilities as locked.

## Readiness

The handoff is allowed only when:

- no required context field is missing; and
- no required context field contains conflicting non-empty values.

Recommended context can be absent without blocking orchestration. Optional or recommended conflicts are recorded as non-blocking evidence.

## Demo mode

Demo mode runs the same deterministic intake and readiness logic as test and production. It adds a human-readable explanation showing:

- active tier, autonomy, and mode;
- why the agent was invoked;
- capabilities used;
- capabilities available at Basic but not needed;
- Managed and Full capabilities locked by tier;
- whether the `context.yaml` handoff is allowed.

Demo mode does not claim that locked capabilities were performed.

## CLI

```bash
python scripts/context_agent.py \
  --contract tests/fixtures/context-agent/job-search-contract.json \
  --input tests/fixtures/context-agent/ready-input.json \
  --mode demo \
  --tier basic \
  --autonomy advisory \
  --output context.yaml \
  --run-report context-run.json
```

The YAML handoff is the inspectable artifact intended for the future Orchestrator Agent. The JSON run report is telemetry/UI evidence for the Human Lead Console.
