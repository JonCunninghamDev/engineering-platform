# Verifier Agent v1

The Verifier is an independent, read-only evidence checker between Builder and Reviewer. At Basic tier it accepts a `builder-task/v1` and the resulting `change-set/v1`, then recomputes evidence from the task instead of trusting Builder claims.

## Basic contract

The Verifier checks task/plan/capability linkage, workflow and goal identity, ordered change identity, allowed/protected scope, Builder zero-write evidence, summary counts, SHA-256 content hashes, and unified diffs. A mismatch fails closed and prevents Reviewer handoff.

The Verifier emits `verification-report/v1`. `verified` permits handoff to Reviewer; `rejected` does not. The report always records `repository_writes: 0` and `candidate_code_executions: 0`.

Basic tier does not stage or mutate a workspace, execute candidate code, run candidate tests, retry implementation, repair Builder output, commit, push, or merge. Candidate-code execution is reported as `unavailable_basic_tier`, not falsely reported as passed.

## Demo

Given Builder artifacts:

```bash
python scripts/verifier_agent.py \
  --task path/to/builder-task.json \
  --change-set path/to/change-set.json \
  --output .agent/verification-report.json
```

Exit status is zero only for a verified proposal. The output is inspectable evidence, not a claim that candidate code was executed.

Managed and Full tiers may later add staged-workspace validation and feedback loops, but those capabilities are intentionally outside this v1 Basic contract.
