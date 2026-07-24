# Engineering Platform

Shared engineering infrastructure for JCDevBot repositories.

This repository is the authoring source of truth for:

- reusable agent operating contracts;
- engineering and delivery standards;
- executable repository policy;
- reusable GitHub Actions workflows and actions;
- issue and pull-request templates;
- language and toolchain profiles;
- steering and workflow scenario tests.

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

1. pins a platform release or immutable commit;
2. keeps a concise local `AGENTS.md` with product-specific context and exceptions;
3. keeps any required synchronized base contract locally for fast startup and offline operation;
4. invokes reusable workflows by pinned release or commit;
5. accepts platform updates through tested pull requests.

Consumers remain independently buildable and revertible. A platform outage must not prevent an agent from reading the local repository steering or running local tests.

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
- Consumers should pin a release tag or full commit SHA rather than an unversioned branch.

## Current roadmap

1. Bootstrap the repository foundation.
2. Centralize delivery-route policy and steering scenarios.
3. Define `engineering-policy/v1` and initial profiles.
4. Add the reusable `node-python-blender` CI workflow.
5. Migrate `JCDevBot/low-poly-character-studio` as the first consumer.
