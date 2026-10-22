# Trusted-local consumer execution coordinator

Experimental continuation of issue #63. This composes existing governed execution and local pre-PR validation; it does not replace the Basic agents or grant a new published service tier.

## Implemented path

1. Authorize the consumer-owned policy and request with `authorize_execution`.
2. Verify the existing checkout's repository identity, temporary branch, clean worktree and base ancestry.
3. Fetch all live GitHub branches and open/draft PRs, selected issue state, exact PR check/review evidence and paginated review threads. Run the existing resume preflight. Missing, ambiguous or moving evidence blocks worker dispatch.
4. Optionally invoke one operator-configured worker as an argument array without a shell. The worker receives the authorized envelope path via `ENGINEERING_EXECUTION_ENVELOPE` and must leave committed changes on the assigned feature branch.
5. Observe commits and changed paths using Git, reject out-of-scope/protected changes, and verify that the worker did not move observed remote refs.
6. Run the consumer's mandatory pre-PR command bindings through `local_pre_pr_runner`, reserving the step/time budget and rejecting failed checks, mutations, missing bindings and zero-test output.
7. Independently verify `worker-execution-result/v1` with `verify_worker_result`.
8. Persist the journal, validation records, worker result, verification and `engineering-run/v1` ledger outside the consumer checkout; stop with readiness evidence for fresh delivery review.

No branch creation, push, PR creation, CI dispatch, merge or production promotion occurs in this coordinator. Those writes require the live delivery integration in #78 and consumer-specific human gates. `ready_for_pr` is a recorded outcome, not a reusable authorization token. The journal deliberately keeps its delivery permissions false.

## Trust and authority

This is a trusted-local adapter, **not a sandbox or unattended hosting service**. A worker and repository-owned test commands are arbitrary host processes. Scope is checked after execution to prevent accepting/publishing invalid results; this does not prevent a malicious worker from touching host files, using inherited credentials, or making external requests. Use only an operator-trusted provider and checkout. An isolated provider remains required for untrusted work.

The existing consumer authority, policy schema, Basic zero-dispatch/zero-write behavior, reusable CI and release gates remain unchanged. Provider configuration comes from the operator, never from an uploaded image, issue body or model output. No billable provider is launched by default. Provider cost is unknown rather than fabricated as zero; a configured cost ceiling blocks this adapter before dispatch because it cannot supply authoritative billing telemetry.

The current GitHub read adapter supports the existing main/develop branch-preflight helper. The coordination function accepts a replaceable reconciler; consumers with other branch conventions need a compatible verified adapter. An existing remote feature branch with a linked open task/PR is required. An orphan branch is not silently adopted.

## Invocation

Supply an accepted consumer policy/request that produces an authorized envelope with `executor: {"adapter":"local-checkout","provider":"local"}`. All required checks must have consumer-owned command bindings. The worker is optional: omit it to validate already-committed implementation work.

```bash
python scripts/consumer_execution_loop.py \
  --policy /path/to/accepted-consumer-policy.json \
  --request /path/to/accepted-execution-request.json \
  --checkout /path/to/existing/consumer-checkout \
  --storage /private/control-plane/run-ledger \
  --worker-command /path/to/operator-owned-worker-argv.json
```

The worker configuration is a JSON array of executable and arguments for a trusted provider. Its adapter/provider identity must be established by the operator as declared in the execution request; the file itself is not a provider authentication mechanism. The adapter independently observes Git outcomes, but does not claim comprehensive OS side-effect telemetry.

Exit codes are `0` for recorded validated readiness, `1` for a blocked run, and `2` for invalid invocation/authorization. Output never grants merge authority. Worker logs are retained only as a hash. Validation logs remain private under the external run directory and may contain sensitive test output; do not publish them automatically.

## Recovery and evidence

Run identity pins the policy, request, provider command and checkout. Files are written atomically and the journal is protected by an exclusive local process lock. A second process cannot execute the same run concurrently. A changed assignment cannot reuse the run ID. Interrupted worker or validation phases require reconciliation rather than automatic retries. Failed checks preserve a blocked journal and do not produce verified worker results. A completed run checks its head, artifact/log hashes and live remote refs before returning cached evidence, without rerunning its worker or checks.

This local filesystem journal is not a hosted control plane or distributed lock. The step count measures worker dispatch and required-check subprocesses; it does not measure opaque provider-internal tool calls. A production provider must enforce its own internal limits and expose the required telemetry. Provider subprocess groups are killed on timeout on supported POSIX hosts; this is not a general isolation guarantee. Negative tests cover scope, budgets, failed/missing checks, zero-test output, stale heads, remote movement, interrupted work, concurrent executors and tampered evidence.

The Engineering Run ledger includes only observed lifecycle milestones and verification outcomes. Unmeasured cost, CI, human effort and host-safety telemetry remain unknown. It records neither product acceptance nor a release. Basic agent evidence remains independently inspectable.

## Remaining acceptance

Run a real consumer through the coordinator with an authorized isolated/provider boundary, normalize remote CI evidence into the external ledger, enforce live PR/merge write gates, perform human acceptance, then release and adopt a verified immutable platform pin. Issue #63 remains open until the required productized path is proven. This optional prototype is not yet a stable published compatibility surface.
