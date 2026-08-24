# Agent Contracts

Versioned shared operating contracts belong here.

Contracts define general behavior such as startup verification, task selection, implementation authority, troubleshooting, interrupted-run recovery, evidence requirements, recurring-run behavior, and human gates.

## Contracts

- [`operating-contract-v1.md`](operating-contract-v1.md) — proposed reusable contract for ordinary, interrupted, and autonomous recurring agent work.

Product vision, architecture, domain rules, credentials, environments, and repository-specific exceptions remain in consumer repositories.

A consumer should pin a released Engineering Platform version and keep the adopted contract locally when its agent environment cannot reliably compose remote instructions. The consumer must remain operable when this repository is unavailable.
