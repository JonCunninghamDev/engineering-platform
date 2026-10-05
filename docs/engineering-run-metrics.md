# Engineering Run proof metrics

Engineering Platform measures delivery in this order:

1. **Safe**
2. **Reliable**
3. **Fast**
4. **Efficient**

Speed and cost are optimization targets only after safety and reliability are visible. Raw pull-request count, lines of code, tokens, or tool-call volume are diagnostic inputs rather than standalone productivity claims.

## Engineering Run

`engineering-run/v1` is the reconstructable evidence ledger for one unit of engineering intent. It records task identity and comparison dimensions, lifecycle milestones, safety counters, verification/retry evidence, human intervention, optional cost/compute telemetry, delivery outcome, artifact references, and derived flow-time metrics.

Missing evidence stays `null`; the platform must not estimate unavailable timestamps, cost, human effort, usage, or production outcomes.

The standard human-readable benchmark view over this ledger is defined in `docs/engineering-benchmark-scorecards.md`. That scorecard is a presentation and comparison protocol, not a second source of truth.

## Standard milestones

`intent_received -> context_ready -> plan_ready -> builder_assigned -> first_change -> verification_started -> verification_passed -> pr_created -> human_review_started -> human_approved -> merged -> deployed`

Not every run reaches every milestone. Basic tier is expected to stop at verified proposed evidence because repository writes and candidate-code execution are intentionally unavailable.

## Initial proof metrics

The initial aggregation surface reports medians for flow time and human interventions plus rates for safe runs, first-pass verification, eventual verification, and completion within granted autonomy.

The primary delivery-speed metric for benchmark work is **time to accepted change**. For human-gated work, that ends at `human_approved`; for autonomously acceptable work, it ends at the last governed milestone required by policy before merge.

Comparisons should be segmented by repository/service, task class, worker, service tier, autonomy tier, and time period when those dimensions are available.

## Proof standard

A claim such as "45% faster" is acceptable only when it also reports the relevant safety, reliability, human-effort, and acceptance guardrails and can be reconstructed from stored Engineering Run evidence. Prefer medians and distributions over averages because engineering latency is skewed by queues, approvals, retries, and outliers.

Do not claim multi-agent improvement from parallel generation speed alone. Establish a comparable single-agent baseline first, include coordination/integration overhead, and compare time to accepted change, reliability, human effort, and usage efficiency.

The first intended real consumer measurement is World Vibes' capability-aware Photorealistic 3D task. Basic tier should expose its governed execution boundary rather than fake writes; that evidence drives the next execution capability.
