# Engineering Platform Agent Entry Point

This file is a routing surface, not the operating manual. Detailed behavior belongs in the machine-readable policy, shared operating contract, and focused standards linked below.

## Repository authority

- GitHub state and checked-in repository files are authoritative.
- `main` is released state; `develop` is integration state; they are the only long-lived branches.
- Issues are the canonical backlog and pull requests are the canonical implementation/review record.
- Direct human instructions for the active task take precedence within safety/tool constraints; record consequential scope changes in durable repository state.
- Product-specific rules belong in consumer repositories, not in this platform.

## Startup reads

Read in this order at the beginning of every run:

1. `README.md` from `main` first for platform identity and release verification.
2. `AGENTS.md` for this routing entrypoint.
3. `engineering-policy.json` for branches, permissions, protected paths, validation stages, budgets, and local human gates.
4. `agent/operating-contract-v1.md` for reusable operating behavior, recovery, delivery routes, and decision discipline.
5. `docs/task-management.md` for deterministic issue selection and status semantics.
6. The active issue and any focused standard, compatibility, adoption, schema, profile, or architecture document it references.
7. Existing pull requests, CI, review threads, and partially completed writes before creating new work.

If published-release verification fails, follow the recovery path in `README.md`; do not treat unreleased `develop` state as published consumer steering.

## Branch invariants

- Temporary implementation branches start from current `develop` and target `develop`.
- Do not implement directly on `main` or `develop`.
- `develop` to `main` is the release route and requires the repository's release gate.
- Approved release history returns to `develop` through the explicit synchronization route when required.
- Delete temporary branches after merge and never force-push a shared branch.
- Protected-path changes require explicit authorization in the active issue as enforced by CI.
- Required validation may not be bypassed; adapter-specific mechanics must remain outside the core policy vocabulary.

## Authoritative pointers

- Local machine policy: `engineering-policy.json`
- Shared operating behavior: `agent/operating-contract-v1.md`
- Task selection and issue lifecycle: `docs/task-management.md`
- Fast-feedback commands and stages: `standards/fast-feedback-v1.json`
- Compatibility and versioning: `docs/compatibility.md`
- Consumer adoption: `docs/adoption.md`
- Reusable CI behavior: `docs/reusable-ci.md`
- Versioned schemas: `schemas/`
- Reusable profiles/capabilities: `profiles/`
- Agent role contracts: `agent/roles/`
- Executable policy tests: `tests/`

## Completion route

Use the configured fast-feedback stages rather than duplicating validation commands here:

```bash
python scripts/run_fast_feedback.py --stage after_write
python scripts/run_fast_feedback.py --stage pre_commit
python scripts/run_fast_feedback.py --stage completion_gate
```

A feature is mergeable into `develop` only when its required tests and Platform CI are green and no gate in `engineering-policy.json` applies. Release promotion remains a separate consequential action.

## Keep this entrypoint small

Do not add detailed troubleshooting, compatibility, testing, style, host-adapter, or workflow procedures here. Update the authoritative linked contract/standard and keep this file as a concise pointer to it.
