# Schemas

Versioned machine-readable contracts belong here.

## Current schemas

- `context-contract-v1.schema.json` defines the required, recommended, and optional context fields for a workflow.
- `context-input-v1.schema.json` defines human/system-supplied context items and provenance metadata for a Context Agent run.
- `context-manifest-v1.schema.json` defines the Context Agent handoff, including readiness, normalized context, tier/autonomy/mode, provenance, capability evidence, and handoff permission.
- `capability-registry-v1.schema.json` defines capabilities available to orchestration, including provider, trigger signals, dependencies, inputs, outputs, risk, tier availability, and human-gate requirements.
- `execution-plan-v1.schema.json` defines the Basic Orchestrator plan, selected/skipped capabilities, dependency-aware ordering, zero-dispatch evidence, and downstream handoff.
- `builder-task-v1.schema.json` defines an explicit Builder assignment linked to a selected execution-plan capability, including allowed/protected path scope and bounded create/update candidate contents.
- `change-set-v1.schema.json` defines the Basic Builder output, deterministic diff/hash evidence, zero-write summary, and handoff to the Verifier.
- `agent-run-report-v1.schema.json` defines the machine-readable evidence record used by demo tooling and the future Human Lead Console.
- `engineering-policy-v1.schema.json` defines consumer platform pins, branch roles, profile/capability requirements, review/delivery gates, permission and risk tiers, protected paths, validation stages, restrictive overrides, explicit exceptions, optional execution budgets, and compatibility metadata.
- `repository-profile-v1.schema.json` defines reusable capability primitives and profile compositions consumed by `engineering-policy/v1`.

Schema changes require valid/invalid fixtures, compatibility documentation, and human review.
