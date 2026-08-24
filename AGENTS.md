# Engineering Platform Agent Steering

This repository defines shared engineering behavior used by other repositories. Changes can alter multiple agents and delivery systems, so clarity, compatibility, and review evidence take precedence over rapid unversioned change.

## Repository authority

- GitHub state and repository files are authoritative.
- `main` is the released platform source of truth.
- `develop` is the integration branch.
- Issues are the canonical backlog; pull requests are the canonical implementation and review record.
- `VERSION` declares the expected platform release.
- Read `README.md` first, then this file, `agent/operating-contract-v1.md`, and `docs/task-management.md` at the beginning of every run.
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
3. Read `README.md` from `main` first.
4. Read `VERSION` and form the expected release tag as `v<VERSION>`.
5. Query the latest non-draft, non-prerelease GitHub release and verify that its tag matches the expected tag and its tagged commit is reachable from `main`.
6. State the verified release tag and commit before treating this repository as published shared steering.
7. Read this file, `agent/operating-contract-v1.md`, `docs/task-management.md`, and other required steering from `main`.
8. Inspect open issues, pull requests, CI, reviews, comments, and unresolved threads.
9. Verify partially completed writes before repeating them.
10. Compare `main` and `develop`; synchronize approved release history back into `develop` before ordinary work.
11. Continue the lowest-numbered `IN PROGRESS` issue, otherwise the highest-priority eligible `READY` issue.

If release verification fails, do not claim the current files are a published steering release. Report the exact mismatch and inspect the release workflow, branch state, open pull requests, and issue state. Branch-local steering may guide maintenance on that branch, but it is not consumer-authoritative until released.

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

The agent owns bounded implementation, tests, documentation, CI troubleshooting, safe conflict resolution, evidence preparation, interrupted-run recovery, and recurring autonomous execution inside an approved issue. `agent/operating-contract-v1.md` defines the shared decision boundary and recurring-run behavior.

The default rule is: make reversible, local, testable engineering decisions and proceed; stop only at an explicit human gate or after safe recovery is exhausted.

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
- `VERSION`, the README declaration, changelog entry, release notes, and GitHub release tag must agree.
- A platform version is published only when a non-draft, non-prerelease `v<VERSION>` release exists and its tagged commit is reachable from `main`.
- Document deprecations before removal.
- Never require consumers to fetch this repository during every agent startup.
- Consumer updates occur through pinned, verified releases and tested pull requests.
- Keep product-specific rules in consumers; central standards may define extension points but must not silently override local product truth.

## Validation

Before review:

- run repository layout validation;
- validate shell, Python, JSON, and YAML files;
- test every executable policy with valid and invalid fixtures;
- verify version, changelog, release-note, and release-workflow consistency;
- update adoption and compatibility documentation when consumer behavior changes;
- identify affected consumer repositories and rollback guidance;
- state whether human acceptance testing is required and record its result when complete.

Queued CI is not a blocker. Continue useful inspection or one independent non-overlapping task.

## Troubleshooting

Before marking work blocked:

1. Re-read the exact error and verify GitHub state.
2. Retry transient operations up to two times.
3. Inspect CI jobs, steps, and logs.
4. Inspect branch comparison, changed files, reviews, comments, release state, and tags.
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

An issue is complete when any required human acceptance test and approval have also been recorded, the change has reached its intended branch, the expected release exists when publication is in scope, and dependent issue states have been updated.
