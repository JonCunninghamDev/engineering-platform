# Platform Compatibility and Upgrade Contract

This document defines the compatibility rules for public Engineering Platform surfaces consumed by other repositories. The machine-readable inventory is `standards/platform-compatibility-v1.json`, validated by `scripts/validate_compatibility.py` against `schemas/platform-compatibility-v1.schema.json`.

## Public surfaces

A surface is public when a consumer is expected to pin, copy, call, validate against, or depend on it. The compatibility manifest currently tracks:

- the agent operating contract;
- `engineering-policy/v1` and `repository-profile/v1` schemas;
- capability and composition profile identifiers;
- the reusable consumer CI workflow, its public inputs, and stable required job name;
- consumer workflow templates.

An implementation detail that is not listed in the compatibility manifest is not automatically a stable public interface.

## Semantic versioning

Platform releases use `MAJOR.MINOR.PATCH` semantic versions.

### Before 1.0

The platform is currently pre-1.0. During this period:

- **Patch** releases (`0.x.Y`) are backward-compatible fixes only. A patch must not remove or reinterpret a published public surface in a way that requires consumer migration.
- **Minor** releases (`0.X.0`) may introduce a breaking public-surface change only when the release explicitly identifies the break, supplies migration instructions, records affected surfaces, and gives consumers a rollback path.
- Additive compatible changes may also ship in a minor release.

A pre-1.0 version number is not permission to make silent breaking changes.

### At and after 1.0

Once the platform reaches 1.0:

- **Patch** releases contain backward-compatible fixes.
- **Minor** releases contain backward-compatible additions or deprecations.
- **Major** releases may contain breaking public-interface changes.

Removing or incompatibly changing a published public surface after 1.0 requires a major release unless a narrowly documented security exception makes continued compatibility unsafe.

## Surface-specific guarantees

### Agent operating contracts

The filename/interface version is part of the contract. Additive clarification that does not broaden authority or break required consumer behavior may remain within the same interface version. Removing required behavior, broadening authority, or changing decision semantics incompatibly requires a new interface version and the platform release boundary required above.

### Policy and profile schemas

Within a schema interface version, existing valid consumer documents must remain valid unless a permitted breaking release includes migration guidance. New optional fields and new values that do not change existing meaning are compatible additions. Removing fields, making optional data required, narrowing accepted values, or changing existing semantics is breaking.

### Capability and profile identifiers

Published capability/profile IDs are stable identifiers. A renamed or replaced identifier is a deprecation plus replacement, not a silent edit. The profile's own semantic version records compatible or incompatible profile evolution, while the platform release records when that profile version is published.

### Reusable workflows

For `.github/workflows/reusable-consumer-ci.yml`:

- declared `workflow_call` input names are public;
- removing an input, changing its meaning incompatibly, or making an optional input newly required is breaking;
- adding a new optional input is compatible;
- the job display name `Platform Consumer CI` is stable because consumers may require it in rulesets/branch protection;
- internal step names and implementation details are not stable public surfaces unless separately registered.

### Templates

Templates are adoption starting points, not remotely executed policy. Compatible edits may improve defaults or documentation. A template change that requires an existing consumer to change its pinned configuration is treated as migration-relevant and must be called out in release notes.

## Deprecation lifecycle

A public surface is not removed merely because a replacement exists. Every machine-readable deprecation records:

- the deprecated `surface_id`;
- the replacement surface;
- the first platform version where the deprecation applies;
- the earliest platform version where removal is allowed;
- a migration document.

The validator requires the removal version to be later than the first-deprecated version. At or after 1.0, removal may not occur until a later major version.

Before 1.0, removal may occur at a later minor version only when the earlier release announced the deprecation and the removal release contains migration guidance. Patch releases never remove a published surface.

## Release compatibility evidence

Every release beyond the current published baseline should identify:

1. previous and target platform versions;
2. public surfaces added, changed, deprecated, or removed;
3. whether each change is compatible or migration-requiring;
4. migration documents for any breaking/deprecated surface;
5. current `standards/platform-compatibility-v1.json` validation evidence;
6. consumer-impact and rollback guidance.

Release notes should distinguish public-interface changes from internal refactors.

## Consumer upgrade evidence

A consumer upgrade pull request must record:

- current platform tag and immutable commit;
- target platform tag and immutable commit;
- compatibility impact (`compatible` or `migration_required`);
- affected public surfaces;
- migration steps performed, when applicable;
- complete consumer CI evidence on the target pin;
- retained product-specific exceptions;
- rollback instructions to the previous immutable pin.

`templates/platform-upgrade.md` provides a reusable checklist.

Consumers should not adopt unreleased `develop` state as authoritative shared steering. A consumer uses the last verified release until a newer release is promoted to platform `main`, published, verified, and adopted through its own tested pull request.

## Machine-readable validation

Run:

```bash
python scripts/validate_compatibility.py
```

The validator checks:

- manifest schema validity;
- `current_platform_version` against `VERSION`;
- unique public-surface IDs and existing repository paths;
- profile identifier/version consistency and minimum platform versions;
- reusable-workflow public input inventory;
- stable workflow job names;
- deprecation surface/replacement references;
- semantic ordering of first-deprecated and earliest-removal versions;
- existence of migration documents.

Platform CI executes this validator. A public-surface edit that drifts from the manifest must fail before merge rather than becoming an undocumented compatibility change.
