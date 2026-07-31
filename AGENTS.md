# Engineering Platform Agent Steering

This repository defines shared engineering behavior used by other repositories. Changes can alter multiple agents and delivery systems, so clarity, compatibility, and review evidence take precedence over rapid unversioned change.

## Repository authority

- GitHub state and repository files are authoritative.
- `main` is the released platform source of truth.
- `develop` is the integration branch.
- Issues are the canonical backlog; pull requests are the canonical implementation and review record.
- Read this file, `README.md`, and `docs/task-management.md` at the beginning of every run.
- Read `docs/adoption.md` for changes affecting consumer repositories.

## Instruction precedence

Resolve instructions in this order:

1. Safety, security, platform, and tool constraints.
2. Direct human instructions for the active task.
3. Accepted issue outcome, scope, and acceptance criteria.
4. Repository-local product, architecture, and steering documents.
5. Synchronized shared platform contracts.
6. General platform standards and profiles.

A direct human instruction may clarify or change an issue goal. Record consequential scope changes in the issue or pull request so repository state remains authoritative after the interaction ends.

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

Green, low-risk pull requests into `develop` may merge autonomously when the repository policy explicitly classifies the change as low risk and no human gate applies.

Explicit human approval is required before merging:

- shared agent authority or steering changes;
- policy schema changes with consumer impact;
- reusable workflow behavior changes;
- security, credentials, destructive operations, or migrations;
- backward-incompatible template or profile changes;
- any ambiguous cross-repository risk;
- every `develop` to `main` release promotion.

## Human acceptance testing

Automated checks are the first validation gate, not the final statement that a consequential goal has succeeded.

When automated checks and acceptance criteria indicate that a consequential goal or coherent milestone has been met:

1. Present the completed outcome and exact test evidence to a human.
2. Ask the human to exercise or inspect the intended result in a realistic workflow.
3. Record whether the human confirmed the goal, found a defect, or changed the goal.
4. Treat defects as continued implementation work rather than a new unrelated task.
5. Do not merge a consequential change or promote `develop` to `main` until the required human acceptance test and approval are recorded.

Human acceptance testing complements deterministic automated tests. It does not replace unit, integration, policy, build, security, or syntax validation.

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
- identify affected consumer repositories and rollback guidance;
- state whether human acceptance testing is required and record its result when complete.

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
- required automated checks pass;
- contracts and behavior are tested;
- versioning and compatibility effects are documented;
- consumer impact and rollback are explicit;
- the PR is focused and references the issue;
- the exact human decision is stated.

An issue is complete when any required human acceptance test and approval have also been recorded, the change has reached its intended branch, and dependent issue states have been updated.
