# Local pre-PR validation adapter

This is a **minimal, validation-only** step toward governed consumer execution (issue #63). It runs the repository-owned validation commands already authorized by an `execution-envelope/v1` inside a **trusted existing checkout**.

It is not a cloud executor, isolated sandbox, coding worker, CI replacement, or proof of PR-creation authority. The full worker must still record code changes, scope, budgets, and actions; `verify_worker_result` must independently validate that evidence. Running this utility never pushes a branch, creates a PR, or merges code.

## Requirements

- Python 3.10+ and Git installed in the execution environment.
- A checkout of the authorized consumer repository on its intended feature branch, clean and with at least one feature commit beyond the authorized base.
- A real `execution-envelope/v1` produced by `authorize_execution` from the consumer's accepted policy. The envelope must designate `executor: {"adapter":"local-checkout","provider":"local"}`.
- All required `verification.pre_pr_checks` must have consumer-owned `verification.pre_pr_commands` bindings. A missing command fails closed.
- Only run this utility on a **trusted developer-controlled host or disposable checkout**. Commands can execute arbitrary software from the repository and therefore are not isolated or inherently secure.

Usage (from an environment with the Engineering Platform scripts available):

```bash
python scripts/local_pre_pr_runner.py \
  --envelope /path/to/approved-execution-envelope.json \
  --checkout /path/to/trusted/consumer-checkout \
  --artifact-dir /path/outside/consumer-checkout/pre-pr-evidence
```

The utility verifies repository identity, remote origin, exact feature branch, base commit ancestry, clean worktree and valid execution authority. It executes the exact required command argument arrays without a shell, respects time/step budgets, records exit status, duration and SHA-256 hash of each full log, and checks for unexpected worktree/head mutations after execution. Logs must stay outside the checkout and may contain sensitive test output: keep them private and do not upload them automatically.

CLI exit codes: `0` means all local checks passed; `1` means one or more checks failed; `2` means validation was blocked before useful execution. The emitted `local-pre-pr-validation/v1` report contains `verification` rows that can be carried into a separately constructed `worker-execution-result/v1` only after the consumer worker and independent verifier validate the complete evidence.

**No positive runner outcome grants merge or PR authority.** This deliberately avoids the earlier dogfood error of treating unexecuted or unverified test commands as evidence.

## Next proof milestone

Run an actual consumer branch through these commands, independently verify the complete worker result with `verify_worker_result`, and create a policy-authorized PR that stops for any human acceptance gate. This local adapter does not yet give an unattended agent a runnable isolated workspace or enforce live GitHub preflight; those remain separate work under issues #63 and #78.
