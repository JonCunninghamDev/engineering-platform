# Agent adapters

Agent-host integrations belong here or in consumer repositories. They translate host-specific command/tool behavior into the host-neutral policy vocabulary defined by `engineering-policy/v1`.

Core policy must not contain concepts such as Codex hooks, Claude hooks, shell aliases, or GitHub-specific execution mechanics.

## Required adapter behavior

Before proposing or executing a shell command that could commit changes, a supported adapter must run the command through:

```bash
python scripts/validate_agent_command.py -- git commit ...
```

The command-policy adapter rejects known validation bypasses such as `git commit --no-verify`, `git commit -n`, disabling `core.hooksPath`, and supported hook-bypass environment settings.

After a file write, adapters may run:

```bash
python scripts/run_fast_feedback.py --stage after_write
```

Before commit, the repository hook runs the `pre_commit` stage. Before an agent reports completion, it must run:

```bash
python scripts/run_fast_feedback.py --stage completion_gate --evidence <path>
```

A failed required stage is a failed completion gate, not a warning. Adapters should surface the structured evidence and allow the agent to repair the cause rather than bypass the check.


## Managed execution provider contract

A managed execution adapter receives an authorized `execution-envelope/v1` and must execute against the exact `repository.base_commit`. The core platform does not assume a specific host.

Examples of possible adapters include a Codex/cloud workspace, a GitHub-hosted coding environment, an authorized remote desktop/container, or a local runner. All adapters must return the same `worker-execution-result/v1` evidence.

The result must identify the adapter/provider execution, repository base/head commits, feature branch, commits, changed paths, actions, required validation evidence with exit status and duration, budget consumption, and consequential actions that were attempted and blocked.

An adapter must not treat a natural-language claim such as "tests passed" as validation evidence. Passed checks require zero exit status plus a traceable evidence reference. Consumer policy remains authoritative over required checks, scopes, budgets, and human gates.
