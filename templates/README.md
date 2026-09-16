# Templates

Templates provide starting files for consumer repositories, including local steering, policy manifests, issue forms, pull-request descriptions, and workflow callers.

Templates are copied or synchronized through reviewed consumer pull requests. They are not remote instructions that silently change consumer behavior.

## Workflow callers

- `workflows/node-python.yml` calls the shared reusable workflow with Node and Python enabled.
- `workflows/node-python-blender.yml` composes Node, Python, and optional Blender validation.

Both examples intentionally use `<PINNED_PLATFORM_SHA>` rather than a moving `main` or `develop` reference. Consumers replace that placeholder with the immutable commit of a verified platform release during adoption or upgrade.

See `docs/reusable-ci.md` for inputs, stable job names, fast/full semantics, caching, diagnostics, and artifact behavior.
