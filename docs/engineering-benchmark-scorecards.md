# Engineering benchmark scorecards

Engineering Platform uses benchmark scorecards to determine whether AI-assisted engineering becomes faster and more efficient without sacrificing safety, reliability, architecture conformance, or human product acceptance.

The canonical evidence ledger remains `engineering-run/v1`. A scorecard is a human-readable view over that evidence, not a second source of truth.

## Measurement order

Evaluate runs in this order:

1. Safe
2. Reliable
3. Fast
4. Efficient

A faster run is not an improvement if it increases unsafe behavior, verification failures, regressions, architecture violations, or human repair effort.

## Primary delivery metric

The primary speed metric is **time to accepted change**.

Measure from `intent_received` until the earliest lifecycle point at which all required conditions for the task are satisfied:

- implementation is complete;
- required automated verification passes;
- required verifier/review findings are resolved;
- architecture and policy requirements are satisfied;
- required human product acceptance is recorded.

For tasks requiring human acceptance, use `human_approved` as the accepted-change endpoint. For tasks whose policy allows autonomous completion, use the last required governed lifecycle milestone before merge.

Do not substitute raw model generation time, pull-request creation time, lines changed, or time to first patch for time to accepted change.

## Standard scorecard

Each benchmark should report the following when evidence is available.

### Safety
- protected-path or authority violations;
- unsafe or disallowed actions attempted;
- policy bypasses;
- destructive or irreversible actions;
- credential/security boundary violations.

### Reliability and accuracy
- first-pass verification result;
- eventual verification result;
- repair cycles;
- CI failures;
- verifier findings, separated into blocking and non-blocking;
- regressions discovered during or after the run;
- architecture/policy conformance;
- product-owner acceptance result;
- human-requested product corrections.

### Speed
- lifecycle timestamps from `engineering-run/v1`;
- wall-clock time to first change;
- wall-clock time to verified change;
- wall-clock time to accepted change;
- queue/wait time when separately observable;
- agent execution time when separately observable.

### Human effort and autonomy
- number of human interventions;
- human steering/review time when measured;
- whether the run completed within granted autonomy;
- reason for each consequential human intervention.

### Efficiency
- model/worker identity where available;
- number of agent runs;
- repair/retry count;
- compute, token, credit, or monetary usage when directly reported by the execution system;
- included-vs-paid usage status when directly known;
- tool-call or change-volume diagnostics when useful.

Never estimate unavailable token, credit, monetary, or human-time data. Record it as null/unknown.

## Diagnostic metrics

The following may help explain a run but are not standalone productivity measures:

- lines of code changed;
- files changed;
- commits;
- pull-request count;
- tool calls;
- raw token volume;
- raw model generation time.

Use these only alongside safety, reliability, accepted-change time, and human-effort evidence.

## Comparison protocol

Comparisons must use materially comparable task classes and report important dimensions such as repository, task type, worker/model, autonomy tier, service tier, and time period.

Prefer medians and distributions over averages.

A claim that one configuration is faster or cheaper must also show the corresponding safety, reliability, and human-effort results.

## Single-agent baseline before multi-agent scaling

Do not claim multi-agent improvement without a governed single-agent baseline.

Before a deliberate multi-agent benchmark:

1. Run enough comparable single-agent tasks to establish observed delivery and reliability behavior.
2. Choose a task that can be decomposed into independent workstreams with explicit ownership and integration boundaries.
3. Record the same scorecard fields for both configurations.
4. Include coordination and integration overhead in multi-agent wall-clock and usage measurements.
5. Compare time to accepted change, reliability, human effort, and usage efficiency, not parallel generation speed alone.

Multi-agent execution is justified only when the measured outcome improves the overall governed delivery system.

## Example scorecard

```yaml
task:
  id: example-ambient-mode
  class: feature
  complexity: medium

execution:
  configuration: single-agent
  worker: codex
  agent_runs: 1
  repair_cycles: 1

speed:
  time_to_first_change_seconds: 420
  time_to_verified_change_seconds: 1180
  time_to_accepted_change_seconds: 1420

reliability:
  first_pass_verification: false
  eventual_verification: true
  ci_failures: 1
  verifier_findings:
    blocking: 0
    non_blocking: 1
  regressions_detected: 0
  architecture_conformant: true

human:
  interventions: 2
  measured_minutes: 6
  product_accepted: true
  product_corrections: 1

efficiency:
  usage_reported: false
  included_allowance_only: null
  credits_used: null
  monetary_cost: null
```

The example is illustrative only. Real scorecards must derive values from recorded run evidence rather than inferred or reconstructed estimates.
