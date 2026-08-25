# Engineering Platform

Shared engineering infrastructure for JonCunninghamDev repositories.

**Declared platform version:** `0.1.0`  
**Expected release tag:** `v0.1.0`

The `VERSION` file declares the steering version. A version is published only when the latest non-draft, non-prerelease GitHub release has the matching `v<VERSION>` tag and that tag resolves to a commit on `main`.

This repository is the authoring source of truth for:

- reusable agent operating contracts;
- engineering and delivery standards;
- executable repository policy;
- reusable GitHub Actions workflows and actions;
- issue and pull-request templates;
- language and toolchain profiles;
- steering and workflow scenario tests.

## Agent startup and release verification

When an agent is pointed at this repository, it must:

1. Verify repository access with a real GitHub call and confirm the default branch is `main`.
2. Read this README first.
3. Read `VERSION`, then form the expected release tag as `v<VERSION>`.
4. Query the latest non-draft, non-prerelease GitHub release.
5. Verify that the release tag exactly matches the expected tag and that its tagged commit is reachable from `main`.
6. Read `AGENTS.md`, `docs/task-management.md`, and any other files required for the active task.
7. State the verified release tag and commit before treating this repository as published shared steering.

If the release is absent, mismatched, draft, prerelease, or not reachable from `main`, the agent must not represent the current files as published shared steering. It should report the mismatch and inspect the release workflow, open pull requests, and issue state. Branch-local files may still guide maintenance work on that branch, but they are not an approved consumer release.

## What belongs here

Centralize mechanics that should behave consistently across repositories:

- startup and interrupted-run recovery;
- task states and deterministic selection;
- feature, integration, promotion, synchronization, and hotfix routes;
- CI failure ownership and troubleshooting;
- reusable toolchain setup and caching;
- build and delivery metadata;
- common security, dependency, testing, and observability standards.

Do not centralize product-specific truth:

- product vision;
- repository architecture;
- visual or domain standards;
- application acceptance criteria;
- credentials, environments, and service ownership;
- repository-specific risk exceptions.

## Adoption model

The platform is a versioned authoring source, not a required remote dependency during every agent run.

A consumer repository:

1. pins a verified platform release and its immutable commit;
2. records the adopted tag and commit in a local manifest;
3. keeps a concise local `AGENTS.md` with product-specific context and exceptions;
4. keeps any required synchronized base contract locally for fast startup and offline operation;
5. invokes reusable workflows by pinned release tag or full commit SHA;
6. accepts platform updates through tested pull requests.

Consumers remain independently buildable and revertible. A platform outage must not prevent an agent from reading local repository steering or running local tests.

## Repository layout

```text
agent/       shared operating contracts
standards/   Git, testing, security, delivery, and observability standards
schemas/     versioned machine-readable policy schemas
profiles/    language and toolchain profiles
templates/   consumer repository and workflow templates
actions/     reusable composite or JavaScript actions
.github/     reusable and repository-local workflows
docs/        adoption, task management, release, and governance documentation
tests/       policy and steering scenario fixtures
scripts/     platform validation and maintenance commands
```

## Branches and releases

- `main` is the released platform source of truth.
- `develop` is the integration branch.
- Ordinary issue branches use `agent/issue-<number>-<slug>` and target `develop`.
- Platform releases are promoted from `develop` to `main` after green CI and human approval.
- After Platform CI succeeds on `main`, the release workflow publishes the `v<VERSION>` GitHub release if it does not already exist.
- Consumers pin the verified release tag and full release commit rather than an unversioned branch.

## Current roadmap

Released foundation:

1. Bootstrap the repository foundation.
2. Publish the shared steering baseline as `v0.1.0`.

Next:

1. Centralize delivery-route policy and steering scenarios.
2. Define `engineering-policy/v1` and initial profiles.
3. Add the reusable `node-python-blender` CI workflow.
4. Migrate `JonCunninghamDev/low-poly-character-studio` as the first consumer.
