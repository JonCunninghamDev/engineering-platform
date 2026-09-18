# Schemas

Versioned machine-readable contracts belong here.

## Current schemas

- `context-contract-v1.schema.json` defines the required, recommended, and optional context fields for a workflow.
- `context-input-v1.schema.json` defines human/system-supplied context items and provenance metadata for a Context Agent run. It also supports optional repository linkage for repository-aware Context preparation.
- `context-manifest-v1.schema.json` defines the Context Agent handoff, including readiness, normalized context, tier/autonomy/mode, provenance, capability evidence, handoff permission, and optional repository/spec-readiness evidence.
- `repository-context-v1.schema.json` defines a consumer repository's declaration of authoritative product, architecture, and feature-spec locations without embedding product identity in the platform.
- `capability-registry-v1.schema.json` defines capabilities available to orchestration, including provider, trigger signals, dependencies, inputs, outputs, risk, tier availability, and human-gate requirements.
- `execution-plan-v1.schema.json` defines the Basic Orchestrator plan, selected/skipped capabilities, dependency-aware ordering, zero-dispatch evidence, and downstream handoff.
- `builder-task-v1.schema.json` defines an explicit Builder assignment linked to a selected execution-plan capability, including allowed/protected path scope and bounded create/update candidate contents.
- `change-set-v1.schema.json` defines the Basic Builder output, deterministic diff/hash evidence, zero-write summary, and handoff to the Verifier.
- `agent-run-report-v1.schema.json` defines per-agent decision and handoff evidence used by demo tooling and the future Human Lead Console.
- `engineering-run-v1.schema.json` defines the cross-agent engineering intent ledger used to prove safety, reliability, flow time, human intervention, efficiency, and downstream outcome without treating raw activity as productivity.
- `execution-envelope-v1.schema.json` defines the bounded consumer execution authority passed to a replaceable worker, including branch route, scope, actions, checks, human gates, budgets, and an explicit prohibition on release writes.
- `engineering-policy-v1.schema.json` defines consumer platform pins, branch roles, profile/capability requirements, review/delivery gates, permission and risk tiers, protected paths, validation stages, restrictive overrides, explicit exceptions, optional execution budgets, and compatibility metadata.
- `repository-profile-v1.schema.json` defines reusable capability primitives and profile compositions consumed by `engineering-policy/v1`.
- `platform-compatibility-v1.schema.json` defines the public-surface inventory, pre-1.0/stable versioning rules, workflow/profile compatibility metadata, and machine-readable deprecation lifecycle.
- `architecture-decision-v1.schema.json` defines stable ADR identity, status, rationale, consequences, supersession, and linked executable-rule requirements.
- `architecture-rule-registry-v1.schema.json` defines the bidirectional registry from architecture rules to governing ADRs, executable validators, tests, and repair guidance.
- `validation-capability-registry-v1.schema.json` defines repository-agnostic browser, HTTP, and container validation interfaces plus tool-swappable implementation guidance.
- `validation-capability-evidence-v1.schema.json` defines observable validation results, including attempts, retry counts, duration, configured/consumed budgets, exhaustion dimension, and per-attempt process evidence.

Public schema compatibility is governed by `docs/compatibility.md` and `standards/platform-compatibility-v1.json`. Breaking schema changes must use the appropriate release boundary and migration evidence rather than silently modifying a published interface.
