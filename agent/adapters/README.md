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
