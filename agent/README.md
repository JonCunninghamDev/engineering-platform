# Agent Contracts

Versioned shared operating contracts belong here.

Contracts define general behavior such as startup verification, task selection, implementation authority, troubleshooting, interrupted-run recovery, evidence requirements, recurring-run behavior, and human gates.

## Contracts

- [`operating-contract-v1.md`](operating-contract-v1.md) — reusable contract for ordinary, interrupted, and autonomous recurring agent work.
- [`context-agent-v1.md`](context-agent-v1.md) — specialized Context Agent contract defining Basic-tier intake, readiness, demo behavior, and downstream handoff.
- [`roles/context-agent-v1.json`](roles/context-agent-v1.json) — machine-readable Context Agent role, service-tier capability matrix, autonomy dimensions, and handoff contract.
- [`orchestrator-agent-v1.md`](orchestrator-agent-v1.md) — specialized Orchestrator contract defining Basic-tier capability selection, dependency planning, explanations, and zero-dispatch demo behavior.
- [`roles/orchestrator-agent-v1.json`](roles/orchestrator-agent-v1.json) — machine-readable Orchestrator role and service-tier capability matrix.
- [`builder-agent-v1.md`](builder-agent-v1.md) — specialized Builder contract defining explicit assignment, scope enforcement, deterministic candidate changes, and zero-write Basic behavior.
- [`roles/builder-agent-v1.json`](roles/builder-agent-v1.json) — machine-readable Builder role, service-tier capability matrix, and Verifier handoff boundary.

Product vision, architecture, domain rules, credentials, environments, and repository-specific exceptions remain in consumer repositories.

A consumer should pin a released Engineering Platform version and keep the adopted contract locally when its agent environment cannot reliably compose remote instructions. The consumer must remain operable when this repository is unavailable.
