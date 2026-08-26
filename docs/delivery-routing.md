# Shared Delivery Routing

The Engineering Platform defines route semantics once so consumer repositories can reuse and test the same branch decisions while keeping their own branch names configurable.

## Route model

| Route | Head | Base | Required title | Authority |
| --- | --- | --- | --- | --- |
| Feature / defect | dedicated task branch | integration branch | ordinary issue title | autonomous when the issue is accepted and no human gate applies |
| Promotion | integration branch | released/default branch | `Release:` | human approval required |
| Synchronization | released/default branch | integration branch | `Sync:` | repository maintenance; autonomous only when local policy allows |
| Hotfix | dedicated hotfix branch | released/default branch | `Hotfix:` | human approval required before released-branch merge |

Ordinary work directly targeting the released/default branch is invalid. Shared-branch-to-same-shared-branch routes and reserved title prefixes on the wrong route are rejected as ambiguous.

A hotfix is reconciled to the integration branch after release through an explicit `Sync:` route.

## Reusable validator

`scripts/validate-delivery-route.py` validates pull-request metadata without product-specific assumptions. Defaults are `main` for the released/default branch and `develop` for integration; consumers can override both names.

Example:

```bash
python scripts/validate-delivery-route.py \
  --base develop \
  --head agent/issue-42-example \
  --title "Issue #42: implement example"
```

The CLI also accepts `GITHUB_BASE_REF`, `GITHUB_HEAD_REF`, `PR_TITLE`, `DEFAULT_BRANCH`, and `INTEGRATION_BRANCH` environment variables. Invalid routes exit non-zero and return an actionable error.

Consumers may copy the validator into local tooling or invoke an equivalent implementation from a pinned Engineering Platform release. Product-specific exceptions remain in consumer policy and must be explicit rather than encoded as silent changes to the shared route semantics.

## Executable matrix

`tests/fixtures/delivery-routes.json` is the canonical valid/invalid route matrix. `tests/test_validate_delivery_route.py` executes every matrix entry and verifies CLI success/failure behavior.

Coverage includes:

- ordinary feature and defect work into integration;
- integration-to-release promotion;
- release-to-integration synchronization;
- dedicated hotfixes;
- custom consumer branch names;
- invalid direct-main ordinary work;
- missing route title prefixes;
- wrong reserved prefixes;
- identical or unsupported branch routes.

## Consumer pinning

Routing policy is versioned with the Engineering Platform release that contains it. Consumers should record both the verified platform tag and immutable commit, then update the pinned validator/contract only through a tested upgrade pull request. A consumer must remain operable if this repository is unavailable.
