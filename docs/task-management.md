# Task Management

## Source of truth

GitHub Issues define platform work. Pull requests define implementation and review. `AGENTS.md` defines execution authority.

## Issue format

Actionable titles use:

```text
[STATE][PRIORITY] Imperative title
```

States:

- `READY`: scope and acceptance are clear and dependencies are complete.
- `IN PROGRESS`: actively owned.
- `REVIEW`: implementation and evidence are complete in a pull request.
- `BLOCKED`: safe recovery is exhausted or a named dependency or decision is required.

Priorities:

- `P0`: blocks platform operation, release safety, or consumer adoption.
- `P1`: required for the first stable platform release.
- `P2`: important reliability, usability, or extensibility work.
- `P3`: later improvement.

Each issue includes outcome, scope, acceptance criteria, dependencies, and implementation notes.

## Deterministic selection

1. Inspect open pull requests for failures, conflicts, or review feedback.
2. Promote objectively unblocked issues immediately.
3. Continue the lowest-numbered `IN PROGRESS` issue.
4. Otherwise select the lowest priority number among eligible `READY` issues.
5. Break ties by issue number.
6. Maintain at most two active implementation branches.
7. Start a second issue only while the first waits exclusively on CI, review, or another non-interactive state and the work is independent.

## Change classes

### Platform foundation

Repository structure, local steering, task management, and self-validation. These changes establish authority and require human review.

### Shared contract or standard

Agent contracts, engineering standards, schemas, profiles, templates, and route policy. Version and test these changes; identify consumer compatibility.

### Reusable workflow or action

Treat inputs, outputs, permissions, job names, secrets, artifacts, and failure behavior as public interfaces. Pin third-party actions and test example consumers.

### Consumer migration

Implement through a focused pull request in the consumer repository. Pin the platform version, preserve local product rules, test rollback, and record before/after measurements.

### Release

Promote `develop` to `main` through a reviewed PR. Tag accepted stable versions. Consumers pin a tag or immutable commit.

## Pull requests

- Ordinary branches start from `develop` and target `develop`.
- Use one issue per PR unless an issue explicitly defines grouped migration work.
- Draft PRs are preferred until checks and evidence are complete.
- Every PR states compatibility impact, affected consumers, validation, and rollback.
- Shared authority, schemas, workflows, and releases require human review.

## Blockers

A blocker comment identifies:

- the exact failure;
- recovery and retries attempted;
- why the agent cannot resolve it safely;
- the smallest action required;
- the exact dependency, permission, setting, credential, or decision.
