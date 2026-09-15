# Agent Contracts

Versioned shared operating contracts belong here.

Contracts define general behavior such as startup verification, task selection, implementation authority, troubleshooting, interrupted-run recovery, evidence requirements, recurring-run behavior, and human gates.

## Contracts

- [`operating-contract-v1.md`](operating-contract-v1.md) — reusable contract for ordinary, interrupted, and autonomous recurring agent work.
- [`context-agent-v1.md`](context-agent-v1.md) — first specialized role contract, defining the Basic Context Agent, tier boundaries, readiness rules, demo behavior, and downstream handoff.
- [`roles/context-agent-v1.json`](roles/context-agent-v1.json) — machine-readable Context Agent role, service-tier capability matrix, autonomy dimensions, and handoff contract.

Product vision, architecture, domain rules, credentials, environments, and repository-specific exceptions remain in consumer repositories.

A consumer should pin a released Engineering Platform version and keep the adopted contract locally when its agent environment cannot reliably compose remote instructions. The consumer must remain operable when this repository is unavailable.
