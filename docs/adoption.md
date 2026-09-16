# Consumer Adoption

## Principles

The engineering platform centralizes reusable mechanics without becoming a runtime dependency for ordinary development.

A consumer repository must remain understandable, buildable, and recoverable from its own checked-in files.

Compatibility and upgrade rules are defined in [`docs/compatibility.md`](compatibility.md). Public surfaces are inventoried in `standards/platform-compatibility-v1.json`.

The platform must not encode the identity, product architecture, prerequisites, or backlog state of any specific consumer repository. Consumer-specific migration work belongs in the consumer repository that owns it.

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

`engineering-policy/v1` provides the machine-readable platform pin, profile selection, branch roles, capabilities, review/delivery gates, permissions, protected paths, validation stages, budgets, and compatibility metadata for consumers that adopt a release containing that schema.

A consumer pin records at minimum:

```yaml
platform:
  repository: JonCunninghamDev/engineering-platform
  version: vX.Y.Z
  commit: <full-release-commit-sha>
profiles:
  - node-python
```

Reusable workflows should be invoked by a verified release tag or full commit SHA. Production-critical consumers should prefer full SHA pinning and upgrade through a pull request.

A contract filename such as `operating-contract-v1.md` is the contract interface version, not proof that a candidate branch is released. Consumer authority comes from the verified platform release tag plus immutable commit. Additive changes can remain within a compatible contract interface only when they do not broaden authority or break consumer expectations; incompatible contract behavior follows `docs/compatibility.md` and requires the appropriate platform version boundary and migration evidence.

## Local synchronized steering

A consumer keeps:

- a concise `AGENTS.md` describing repository authority, required local reads, product-specific human gates, and exceptions;
- a checked-in synchronized base contract when the agent environment cannot reliably compose remote instructions;
- the verified platform release tag and commit from which that local contract was derived;
- any locally copied route validator or scenario fixture tied to the same pinned release.

Agents should not fetch the platform repository during every run merely to reconstruct ordinary task context. Release verification is required during initial adoption and upgrade, not as a runtime dependency for every ordinary consumer task.

## Update process

1. A verified platform release becomes available.
2. Automation or an agent opens a consumer upgrade PR using `templates/platform-upgrade.md` or equivalent evidence.
3. The PR records the current and target release/tag/immutable commit and the compatibility impact.
4. The PR updates the platform pin, synchronized local files, and any copied validators/fixtures.
5. Migration-required public surfaces are handled using the release migration documentation.
6. Consumer CI validates its complete required suite, including local route scenarios when adopted.
7. Review confirms product-specific exceptions remain intact.
8. Merge only after rollback to the previous immutable pin is clear.

A consumer upgrade PR must identify affected public surfaces, test evidence, and rollback even when the compatibility impact is `compatible`.

## Local overrides

Overrides are explicit, narrow, and documented with rationale. Examples include:

- generated-artifact or visual changes requiring human acceptance;
- a repository without public deployment infrastructure;
- a regulated security or data-handling requirement;
- a different integration branch during a temporary migration.

Overrides must not be hidden in workflow implementation. They belong in the consumer policy and local steering. Consumers may narrow autonomous authority but must not silently broaden the shared contract.

## Failure isolation

A platform outage or inaccessible repository must not prevent:

- reading local steering;
- running local tests;
- fixing a consumer defect;
- rolling back a platform upgrade.

Reusable workflow failures should identify the pinned platform release and expose enough logs for the consumer to determine whether the defect belongs in the platform or product repository.

## Consumer readiness

A consumer may adopt the platform when:

- the required shared steering and delivery surfaces are included in a verified platform release;
- the required `engineering-policy/v1`, compatibility contract, profiles, and reusable workflows are included in that release;
- the consumer records an immutable platform pin and preserves its own product-specific rules locally;
- the consumer can validate the adoption through its own complete CI suite;
- rollback to the prior immutable platform pin is explicit.

Consumer-owned prerequisites and migration sequencing are intentionally not tracked here. They belong in the consumer repository.

Do not pin a consumer to unreleased platform `develop` state merely because an immutable development commit exists. Adoption should prove the release, verification, compatibility, and rollback path that all consumers can rely on.
