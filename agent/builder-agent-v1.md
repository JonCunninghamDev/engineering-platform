# Builder Agent v1

Status: proposed

The Builder Agent turns an explicit implementation assignment into an inspectable candidate change set. It does not infer that work was dispatched merely because an Orchestrator plan contains a `WOULD_INVOKE` row.

## Basic tier

Basic Builder is a bounded proposal stage. It:

1. validates an explicit `builder-task/v1` assignment;
2. verifies the task links to a selected `builder` capability in `execution-plan/v1`;
3. enforces declared allowed and protected repository paths;
4. accepts bounded create/update candidate contents supplied by the active agent host;
5. computes deterministic unified diffs and SHA-256 before/after evidence;
6. explains the accepted change set;
7. emits `change-set/v1` and `agent-run-report/v1`.

Basic Builder does **not** mutate repository files, delete files, run tests, commit or push changes, retry implementation failures, or broaden its own scope.

The distinction is intentional: open-ended implementation content may come from Codex, another model host, or another approved implementation engine, while the Engineering Platform provides a vendor-neutral control and evidence boundary around that content.

## Assignment boundary

`builder-task/v1` is the authority to prepare Builder work. The task must:

- contain an explicit assignment ID, source, and `allowed: true`;
- link to the exact execution-plan run;
- name a selected capability whose provider is `builder`;
- declare allowed paths and optional protected paths;
- contain one or more create/update candidate changes.

An Orchestrator `WOULD_INVOKE` row is planning evidence, not dispatch evidence. Basic Builder therefore requires a separate assignment artifact.

## Scope rules

Repository paths are POSIX-style and repository-relative.

- Absolute paths are rejected.
- `.` and `..` traversal segments are rejected.
- Backslash-separated paths are rejected.
- Allowed paths may be exact files or directory prefixes ending in `/`.
- Protected paths override allowed paths.
- Duplicate change paths are rejected.
- Basic supports only `create` and `update`; delete remains unavailable.

## Demo behavior

Demo mode uses the same validation, diff, and hash logic as other Basic runs, but each candidate file action is reported as `WOULD_WRITE`.

`actual_write_count` is always zero at Basic tier. The handoff status is `proposed_not_applied`.

## Planned higher tiers

Managed adds governed workspace mutation, focused validation, bounded implementation iteration, and task-state updates.

Full adds larger refactor strategy, dependency migration, autonomous implementation recovery, and broader implementation sequencing within policy.

Service tier, autonomy, and execution mode remain independent dimensions. A higher autonomy setting does not grant a Basic Builder a capability that exists only in Managed or Full.
