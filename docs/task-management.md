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
- `REVIEW`: implementation and automated evidence are complete; required human acceptance testing or approval may still be pending.
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
7. Start a second issue only while the first waits exclusively on CI, human acceptance testing, review, or another non-interactive state and the work is independent.

## Goal validation

Automated tests establish deterministic evidence. Human acceptance testing establishes that a consequential goal or coherent milestone works as intended.

When the implementation meets its stated acceptance criteria:

1. Move the issue to `REVIEW` and present the completed outcome, test evidence, known limitations, and rollback path.
2. For consequential changes, have a human exercise or inspect the result in a realistic workflow.
3. Record the human result in the pull request: confirmed, defect found, or goal changed.
4. If a defect is found, return the issue to `IN PROGRESS` and continue within the same issue unless the human explicitly separates the work.
5. Require explicit human approval for consequential changes and every `develop` to `main` promotion.

Green, low-risk pull requests into `develop` may merge autonomously when policy explicitly allows the change class. Human acceptance testing does not replace automated tests.

## Change classes

### Platform foundation

Repository structure, local steering, task management, and self-validation. These changes establish authority and require human review and acceptance testing.

### Shared contract or standard

Agent contracts, engineering standards, schemas, profiles, templates, and route policy. Version and test these changes; identify consumer compatibility. Consequential changes require human acceptance testing and approval.

### Reusable workflow or action

Treat inputs, outputs, permissions, job names, secrets, artifacts, and failure behavior as public interfaces. Pin third-party actions and test example consumers. Require human acceptance testing before release.

### Consumer migration

Implement through a focused pull request in the consumer repository. Pin the platform version, preserve local product rules, test rollback, record before/after measurements, and have a human validate the migrated workflow.

### Release

Promote `develop` to `main` through a reviewed pull request. Every promotion requires explicit human acceptance testing and approval. Tag accepted stable versions. Consumers pin a tag or immutable commit.

## Pull requests

- Ordinary branches start from `develop` and target `develop`.
- Use one issue per PR unless an issue explicitly defines grouped migration work.
- Draft PRs are preferred until checks and evidence are complete.
- Every PR states compatibility impact, affected consumers, automated validation, human acceptance-test status, and rollback.
- Green, low-risk PRs into `develop` may merge autonomously when no human gate applies.
- Shared authority, schemas, workflows, consequential changes, and releases require human approval.

## Blockers

A blocker comment identifies:

- the exact failure;
- recovery and retries attempted;
- why the agent cannot resolve it safely;
- the smallest action required;
- the exact dependency, permission, setting, credential, or decision.
