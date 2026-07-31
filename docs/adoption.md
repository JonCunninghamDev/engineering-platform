# Consumer Adoption

## Principles

The engineering platform centralizes reusable mechanics without becoming a runtime dependency for ordinary development.

A consumer repository must remain understandable, buildable, and recoverable from its own checked-in files.

## Consumer hierarchy

Agents resolve instructions in this order:

1. direct human instructions for the active task, subject to safety and tool constraints;
2. issue acceptance criteria;
3. repository-specific product and architecture documents;
4. repository-local steering and exceptions;
5. synchronized shared platform contract;
6. general platform standards and profiles.

A shared rule must not silently override a more specific accepted product constraint.

## Release verification

Before adopting or upgrading the platform, the consumer agent must:

1. read the platform README and `VERSION` from `main`;
2. form the expected release tag as `v<VERSION>`;
3. query the latest non-draft, non-prerelease GitHub release;
4. verify that the release tag matches the expected tag;
5. verify that the tagged commit is reachable from platform `main`;
6. record both the verified tag and immutable commit in the consumer repository.

If any check fails, do not treat the candidate platform files as published shared steering. Continue using the consumer's last verified local contract until the platform release is corrected and adopted through a tested pull request.

## Pinning

Consumers identify the adopted platform release in a local manifest, eventually standardized by `engineering-policy/v1`.

Until that schema is released, use a minimal file such as:

```yaml
platform:
  repository: JCDevBot/engineering-platform
  version: v0.1.0
  commit: <full-release-commit-sha>
profile: node-python-blender
```

Reusable workflows should be invoked by a verified release tag or full commit SHA. Production-critical consumers should prefer full SHA pinning and upgrade through a pull request.

## Local synchronized steering

A consumer keeps:

- a concise `AGENTS.md` describing repository authority, required local reads, product-specific human gates, and exceptions;
- a checked-in synchronized base contract when the agent environment cannot reliably compose remote instructions;
- the verified platform release tag and commit from which that local contract was derived.

Agents should not fetch the platform repository during every run merely to reconstruct ordinary task context. Release verification is required during initial adoption and upgrade, not as a runtime dependency for every ordinary consumer task.

## Update process

1. A verified platform release becomes available.
2. Automation or an agent opens a consumer upgrade PR.
3. The PR updates the tag, immutable commit, and synchronized local files.
4. Consumer CI validates its complete required suite.
5. Review confirms product-specific exceptions remain intact.
6. Human acceptance is performed when the change affects consequential consumer behavior.
7. Merge only after rollback is clear.

## Local overrides

Overrides are explicit, narrow, and documented with rationale. Examples include:

- Blender and visual changes requiring human acceptance;
- a repository without public deployment infrastructure;
- a regulated security or data-handling requirement;
- a different integration branch during a temporary migration.

Overrides must not be hidden in workflow implementation. They belong in the consumer policy and local steering.

## Failure isolation

A platform outage or inaccessible private repository must not prevent:

- reading local steering;
- running local tests;
- fixing a consumer defect;
- rolling back a platform upgrade.

Reusable workflow failures should identify the pinned platform release and expose enough logs for the consumer to determine whether the defect belongs in the platform or product repository.

## First consumer

`JCDevBot/low-poly-character-studio` will be the first consumer after:

- the shared steering baseline is released and verified;
- shared delivery policy and `engineering-policy/v1` are released;
- the reusable `node-python-blender` workflow is validated;
- its active final-GLB issue has merged and synchronized through the existing delivery path.
