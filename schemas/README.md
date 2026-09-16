# Schemas

Versioned machine-readable contracts belong here.

## Current schemas

- `context-contract-v1.schema.json` defines the required, recommended, and optional context fields for a workflow.
- `context-input-v1.schema.json` defines human/system-supplied context items and provenance metadata for a Context Agent run.
- `context-manifest-v1.schema.json` defines the Context Agent handoff, including readiness, normalized context, tier/autonomy/mode, provenance, capability evidence, and handoff permission.
- `capability-registry-v1.schema.json` defines capabilities available to orchestration, including provider, trigger signals, dependencies, inputs, outputs, risk, tier availability, and human-gate requirements.
- `execution-plan-v1.schema.json` defines the Basic Orchestrator plan, selected/skipped capabilities, dependency-aware ordering, zero-dispatch evidence, and downstream handoff.
- `agent-run-report-v1.schema.json` defines the machine-readable evidence record used by demo tooling and the future Human Lead Console.

## Planned schemas

`engineering-policy/v1` will define branch roles, profiles, capabilities, checks, merge authority, promotion gates, explicit local overrides, protected surfaces, and execution budgets.

Schema changes require fixtures, compatibility documentation, and human review.
