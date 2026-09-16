# Repository Profiles

Profiles compose reusable engineering capabilities without embedding product-specific architecture, paths, visual rules, consumer identity, or agent-vendor assumptions.

## Contract

All profiles use `repository-profile/v1` and are validated by `schemas/repository-profile-v1.schema.json`.

Capability primitives are independent building blocks:

- `capability.node` -> `runtime.node`, `test.node`
- `capability.python` -> `runtime.python`, `test.python`
- `capability.blender` -> `runtime.blender`, `test.blender`

Compositions reference those primitives instead of duplicating them:

- `node-python` includes `capability.node` and `capability.python`
- `node-python-blender` includes `node-python` and `capability.blender`

This keeps Blender optional and prevents a Node/Python consumer from inheriting Blender requirements merely because another consumer needs them.

## Engineering policy examples

`profiles/examples/` contains generic `engineering-policy/v1` examples for:

- Node/Python consumers;
- Node/Python/Blender consumers.

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

## Compatibility metadata

Policies and profiles declare their schema interface and minimum platform version. This metadata is deliberately small in v1; issue #16 defines the broader platform upgrade/deprecation contract that consumes it.
