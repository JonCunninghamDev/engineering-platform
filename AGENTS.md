# Engineering Platform Agent Steering

This repository defines shared engineering behavior used by other repositories. Changes can alter multiple agents and delivery systems, so clarity, compatibility, and review evidence take precedence over rapid unversioned change.

## Repository authority

- GitHub state and repository files are authoritative.
- `main` is the released platform source of truth.
- `develop` is the integration branch.
- Issues are the canonical backlog; pull requests are the canonical implementation and review record.
- Read this file, `README.md`, and `docs/task-management.md` at the beginning of every run.
- Read `docs/adoption.md` for changes affecting consumer repositories.

## Startup contract

At the beginning of every run:

1. Verify repository access with a real GitHub connector call.
2. Confirm the default branch is `main`.
3. Read required steering from `main`.
4. Inspect open issues, pull requests, CI, reviews, comments, and unresolved threads.
5. Verify partially completed writes before repeating them.
6. Compare `main` and `develop`; synchronize approved release history back into `develop` before ordinary work.
7. Continue the lowest-numbered `IN PROGRESS` issue, otherwise the highest-priority eligible `READY` issue.

Do not claim GitHub is unavailable without an actual failed connector call and the exact error.

## Branch and pull-request contract

- Ordinary branch: `agent/issue-<number>-<slug>` from current `develop`.
- Ordinary target: `develop`.
- Production/release promotion: `develop` to `main`.
- Synchronization after promotion: `main` to `develop` with an explicit `Sync:` title once shared route policy is implemented.
- Hotfixes start from `main`, target `main`, and begin with `Hotfix:`; reconcile them back into `develop`.
- Never force-push a shared branch.
- Maintain at most two active implementation branches.

## Implementation authority

The agent owns bounded implementation, tests, documentation, CI troubleshooting, safe conflict resolution, and evidence preparation inside an approved issue.

Human review is required before merging:

- shared agent authority or steering changes;
- policy schema changes with consumer impact;
- reusable workflow behavior changes;
- release and promotion policy changes;
- security, credentials, destructive operations, or migrations;
- backward-incompatible template or profile changes;
- any ambiguous cross-repository risk.

Low-risk tests, typo corrections, examples, and non-authoritative documentation may be merged autonomously only after the platform's merge policy explicitly authorizes that class. Until the bootstrap is accepted, all pull requests require human review.

## Compatibility and versioning

- Prefer additive, backward-compatible changes.
- Version contracts, schemas, profiles, and reusable workflow interfaces.
- Document deprecations before removal.
- Never require consumers to fetch this repository during every agent startup.
- Consumer updates occur through pinned versions and tested pull requests.
- Keep product-specific rules in consumers; central standards may define extension points but must not silently override local product truth.

## Validation

Before review:

- run repository layout validation;
- validate shell, Python, JSON, and YAML files;
- test every executable policy with valid and invalid fixtures;
- update adoption and compatibility documentation when consumer behavior changes;
- identify affected consumer repositories and rollback guidance.

Queued CI is not a blocker. Continue useful inspection or one independent non-overlapping task.

## Troubleshooting

Before marking work blocked:

1. Re-read the exact error and verify GitHub state.
2. Retry transient operations up to two times.
3. Inspect CI jobs, steps, and logs.
4. Inspect branch comparison, changed files, reviews, and comments.
5. Run the narrowest deterministic reproduction.
6. Distinguish repository defects from permissions, service failures, and missing external capabilities.
7. Use a safe GitHub-native alternative when one connector operation is unsupported.
8. Block only when recovery is exhausted or a named human decision, credential, setting, or dependency is required.

## Definition of done

An issue is ready for review when:

- acceptance criteria are satisfied;
- required checks pass;
- contracts and behavior are tested;
- versioning and compatibility effects are documented;
- consumer impact and rollback are explicit;
- the PR is focused and references the issue;
- the exact human decision is stated.
