# Reusable Consumer CI

`reusable-consumer-ci.yml` is the shared CI entrypoint for consumer repositories. It is called with `workflow_call` and should be pinned by a verified release tag or, preferably for production-critical consumers, an immutable platform commit SHA.

## Stable check surface

The called workflow exposes one stable job name:

- `Platform Consumer CI`

Consumers should keep the caller job id stable as `platform-ci` when they make this check required in branch protection or rulesets. Step names are implementation details and are not part of the compatibility surface.

## Capability composition

Node, Python, and Blender are independent switches:

- `enable_node`
- `enable_python`
- `enable_blender`

`node-python` is the composition of Node and Python only. `node-python-blender` enables all three. Blender is not required for Node/Python consumers.

The workflow intentionally does not encode product paths, visual acceptance rules, package names, or application architecture. Working directories and install/test/build commands are supplied by the consumer.

## Fast and full modes

`mode: fast` runs enabled install and test commands but skips optional Node/Python build commands. It is intended for feature feedback where tests are the completion gate.

`mode: full` runs the same tests plus configured build commands and optional build-artifact upload. Promotion/release checks should use `full` unless repository policy explicitly permits otherwise.

Both modes keep the same stable job name so required checks do not become conditionally pending.

## Toolchain setup

The workflow uses official Node and Python setup actions. Consumers select versions through `node_version` and `python_version`.

Python consumers that use `uv` can set `install_uv: true` and provide repository-native commands such as:

```yaml
python_install_command: uv sync --frozen
python_test_command: uv run pytest
```

Consumers that standardize their local toolchain with `mise` may continue to keep `.mise.toml` authoritative and pass repository-declared commands through the workflow. The shared workflow does not require every consumer to adopt `mise` or `uv`.

## Caching

Caching is opt-in because lockfile locations differ across repositories.

Node caching uses `actions/setup-node` and requires the appropriate package manager plus dependency path. Python caching uses `actions/setup-python` pip caching and a declared dependency path. Consumers using another cache mechanism may leave these switches disabled and perform cache-aware setup in their own commands.

## Blender

When `enable_blender: true`, the workflow installs Blender with the declared `blender_install_command` and executes `blender_test_command`. Both are consumer-configurable. The platform default is a headless smoke test; consumers retain their own Blender scripts, geometry checks, rendering rules, and human visual gates.

## Diagnostics and artifacts

Every run uploads a small build-metadata artifact. Failed runs also upload bounded diagnostics containing repository status and available tool versions. Optional consumer build artifacts are uploaded only after a successful `full` run when `artifact_paths` is non-empty.

Artifact retention is bounded to 1-30 days by workflow input validation; the default is 7 days.

## Pinning

Do not point production consumers at a moving platform branch. Replace `<PINNED_PLATFORM_SHA>` in the templates with the immutable commit of an accepted platform release. See `docs/adoption.md` for release verification and upgrade rules.

## Templates

- `templates/workflows/node-python.yml`
- `templates/workflows/node-python-blender.yml`

These templates deliberately contain no consumer identity or product-specific assumptions.
