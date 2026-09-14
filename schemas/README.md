# Schemas

Versioned machine-readable contracts belong here.

## Current schemas

- `context-contract-v1.schema.json` defines the required, recommended, and optional context fields for a workflow.
- `context-input-v1.schema.json` defines human/system-supplied context items and provenance metadata for a Context Agent run.
- `context-manifest-v1.schema.json` defines the Context Agent handoff, including readiness, normalized context, tier/autonomy/mode, provenance, capability evidence, and handoff permission.
- `agent-run-report-v1.schema.json` defines the machine-readable evidence record used by demo tooling and the future Human Lead Console.

## Planned schemas

`engineering-policy/v1` will define branch roles, profiles, capabilities, checks, merge authority, promotion gates, explicit local overrides, protected surfaces, and execution budgets.

Schema changes require fixtures, compatibility documentation, and human review.
