# Engineering Platform Upgrade

## Platform pins

- Previous release: `vX.Y.Z`
- Previous commit: `<40-character-sha>`
- Target release: `vX.Y.Z`
- Target commit: `<40-character-sha>`

## Compatibility impact

- Impact: `compatible` / `migration_required`
- Public surfaces affected:
  - `<surface-id>` — `<compatible change or migration>`

## Migration

- Migration document(s): `<path or N/A>`
- Consumer changes performed:
  - `<change>`

## Consumer-specific policy

- Product/architecture truth remains local: yes/no
- Existing local exceptions reviewed and retained intentionally: yes/no
- New exception required: `<reference or none>`

## Validation

- Platform release/tag/commit verification: `<evidence>`
- Compatibility validator evidence: `<evidence>`
- Consumer required CI: `<workflow run>`
- Additional product-specific checks: `<evidence or none>`

## Rollback

Restore the previous immutable platform pin and synchronized local contract/template files through one focused revert or rollback PR:

- Previous release: `vX.Y.Z`
- Previous commit: `<40-character-sha>`
- Additional rollback notes: `<notes>`
