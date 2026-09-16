# Platform Releases

A platform release is authoritative only after the accepted `develop` state is promoted to `main`, `VERSION` is correct, and the matching non-draft/non-prerelease GitHub release tag is published from a commit reachable from `main`.

Release preparation must follow [`docs/compatibility.md`](../compatibility.md).

For every release after `v0.1.0`, release evidence should include:

- previous and target versions;
- exact `develop` source and `main` target commits;
- included issues/PRs and green Platform CI;
- `python scripts/validate_compatibility.py` result;
- public surfaces added, compatibly changed, deprecated, or removed;
- migration documents for any breaking/deprecated surface;
- consumer impact and rollback/forward-fix guidance.

Pre-1.0 patch releases are backward-compatible only. A pre-1.0 breaking change requires a minor release plus explicit migration guidance. At and after 1.0, breaking public-interface changes require a major release.

Historical release notes remain records of what was published at that time; later compatibility documentation does not retroactively change a release's contents.
