# Repository Profiles

Profiles compose reusable engineering capabilities without embedding product-specific architecture, paths, visual rules, consumer identity, or agent-vendor assumptions.

## Contract

All profiles use `repository-profile/v1` and are validated by `schemas/repository-profile-v1.schema.json`.

Capability primitives are independent building blocks:

- `capability.node` -> `runtime.node`, `test.node`
- `capability.python` -> `runtime.python`, `test.python`
- `capability.blender` -> `runtime.blender`, `test.blender`
- `capability.browser-e2e` -> `runtime.browser`, `test.browser_e2e`
- `capability.http-contract` -> `runtime.http_client`, `test.http_contract`
- `capability.container-integration` -> `runtime.container`, `test.container_integration`

The three integration-validation primitives are opt-in independently. Selecting browser validation does not imply HTTP or container validation, and none of them prescribe a particular product architecture or test framework. Tool guidance lives in `standards/validation-capabilities-v1.json`.

Compositions reference primitives instead of duplicating them:

- `node-python` includes `capability.node` and `capability.python`
- `node-python-blender` includes `node-python` and `capability.blender`

This keeps Blender and higher-cost integration capabilities optional so a consumer inherits only the toolchain and validation surfaces it explicitly selects.

## Engineering policy examples

`profiles/examples/` contains generic `engineering-policy/v1` examples for Node/Python and Node/Python/Blender consumers. Consumers may add any validation capability primitive independently when their repository actually provides the corresponding command and environment.

The policy declares the verified platform pin, branch roles, selected profiles, required capabilities, review and delivery gates, permission/risk tiers, protected paths, validation stages, optional execution budgets, local restrictive overrides, explicit exceptions, and compatibility metadata.

Validate an example with:

```bash
python scripts/validate_engineering_policy.py \
  --policy profiles/examples/node-python-policy.json
```

Install validation dependencies first with `python -m pip install -r requirements-dev.txt`.

## Permission tiers

`engineering-policy/v1` distinguishes three action classes:

- `autonomous` for low-risk reads and inspection;
- `bounded` for draft or branch-scoped writes that remain reversible and reviewable;
- `approval_required` for external, release, credential, destructive, or otherwise consequential writes.

These terms describe authority, not a specific agent host. Claude Code, Codex, CI, pre-commit tooling, or another host may adapt the same vocabulary without changing the policy contract.

## Protected paths and validation stages

Consumers declare protected repository-relative path patterns independently of the mechanism that enforces them. Validation stages are host-neutral and use `after_write`, `pre_commit`, and `completion_gate` so later adapters can enforce the same policy at different execution points.

## Overrides and exceptions

Machine-applied `overrides` are intentionally **restrict-only**. They may add protected paths, add human-approval requirements, remove capabilities, or lower execution budgets. They cannot broaden autonomous authority.

An `exception` documents an approved deviation with a reason and an `approval_reference`. Declaring an exception does not itself grant new authority; the referenced human/repository approval remains the authority source. Temporary exceptions should include `expires_on` when practical.

## Execution budgets

`execution_budgets` is optional. A consumer can configure any subset of `max_steps`, `max_elapsed_minutes`, `max_retries`, and `max_cost_usd`.

`required_dimensions` identifies only the budget dimensions a host must support for that policy. Unsupported optional dimensions may be reported without making every agent host implement every budget type.

`run_validation_capability.py` supports all four v1 budget dimensions for repository-owned validation commands. It reports `budget_exhausted` separately from `test_failed` and records steps, elapsed time, retries, and accounted cost in structured evidence.

## Compatibility metadata

Policies and profiles declare their schema interface and minimum platform version. Broader public-surface compatibility and deprecation behavior is defined by `docs/compatibility.md` and `standards/platform-compatibility-v1.json`.
