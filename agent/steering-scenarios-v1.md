# Agent Steering Scenarios v1

These scenarios make the operating-contract decision boundary concrete. The executable mirror is `tests/fixtures/agent-steering-scenarios-v1.json`, validated by `tests/test_agent_steering_scenarios.py`.

| Scenario | Default decision | Expected behavior |
| --- | --- | --- |
| Feature | autonomous | Implement bounded accepted scope, test, and record evidence. |
| Defect | autonomous | Reproduce narrowly, fix within scope, and validate. |
| CI failure | recover | Inspect jobs/logs, retry transient failures, then fix or isolate. |
| Branch conflict | recover | Resolve ordinary behavior-preserving conflicts without a preference gate. |
| Promotion | human gate | Prepare release evidence; a human approves integration-to-release merge. |
| Synchronization | autonomous | Use explicit `Sync:` routing when local policy allows low-risk maintenance merge. |
| Hotfix | human gate | Implement bounded fix, but require approval before released-branch merge. |
| Incident | recover | Diagnose and isolate first; escalate only consequential action or unresolved risk. |
| Credential | human gate | Do not add, expose, rotate, or broaden secret authority autonomously. |
| Visual | human gate when locally required | Follow the consumer's explicit visual/experience acceptance rule. |
| Architecture | autonomous when reversible | Record rationale and proceed if it does not expand product or cross-repository authority. |
| Destructive work | human gate | Prepare rollback/migration evidence before irreversible action. |
| Interrupted run | recover | Reconstruct from repository state and resume from the exact durable next action. |
| Recurring run | recover | Verify existing writes first and continue idempotently without duplicate artifacts. |

## Decision rule

- Reversible + local + testable: decide and proceed.
- Reversible + cross-cutting: record rationale and proceed when repository policy allows.
- Hard to reverse + bounded: prepare evidence and apply the repository's human gate.
- Hard to reverse + cross-repository, security, privacy, production, or cost impact: require human approval.

The consumer may narrow autonomous authority with explicit local rules. It must not silently broaden the shared contract.
