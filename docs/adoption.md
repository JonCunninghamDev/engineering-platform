# Consumer Adoption

## Principles

The engineering platform centralizes reusable mechanics without becoming a runtime dependency for ordinary development.

A consumer repository must remain understandable, buildable, and recoverable from its own checked-in files.

## Consumer hierarchy

Agents resolve instructions in this order:

1. issue acceptance criteria;
2. repository-specific product and architecture documents;
3. repository-local steering and exceptions;
4. synchronized shared platform contract;
5. general platform standards and profiles.

A shared rule must not silently override a more specific accepted product constraint.

## Pinning

Consumers identify the adopted platform version in a local manifest, eventually standardized by `engineering-policy/v1`.

Until that schema is released, use a minimal file such as:

```yaml
platform:
  repository: JCDevBot/engineering-platform
  commit: <full-commit-sha>
  version: pre-v1
profile: node-python-blender
```

Reusable workflows should be invoked by release tag or full commit SHA. Production-critical consumers should prefer full SHA pinning and upgrade through a pull request.

## Local synchronized steering

A consumer keeps:

- a concise `AGENTS.md` describing repository authority, required local reads, product-specific human gates, and exceptions;
- a checked-in synchronized base contract when the agent environment cannot reliably compose remote instructions;
- the platform commit or version from which that local contract was derived.

Agents should not fetch the platform repository during every run merely to reconstruct ordinary task context.

## Update process

1. A platform release or accepted commit becomes available.
2. Automation or an agent opens a consumer upgrade PR.
3. The PR updates the pin and synchronized local files.
4. Consumer CI validates its complete required suite.
5. Review confirms product-specific exceptions remain intact.
6. Merge only after rollback is clear.

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

Reusable workflow failures should identify the pinned platform reference and expose enough logs for the consumer to determine whether the defect belongs in the platform or the product repository.

## First consumer

`JCDevBot/low-poly-character-studio` will be the first consumer after:

- the platform bootstrap is accepted;
- shared delivery policy and `engineering-policy/v1` are released;
- the reusable `node-python-blender` workflow is validated;
- its active final-GLB issue has merged and synchronized through the existing delivery path.
