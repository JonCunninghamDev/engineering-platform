# Governed consumer execution

The governed execution layer bridges a ready Engineering Platform plan to a replaceable worker without weakening the Basic tier.

Basic remains proposal-only:

- Orchestrator dispatch count stays zero.
- Builder actual repository writes stay zero.
- Basic Verifier candidate-code executions stay zero.

A higher-tier caller can instead construct a `governed-execution-request/v1` from consumer-owned context and policy and ask `scripts/governed_execution.py` to produce an `execution-envelope/v1`.

## Execution envelope

The envelope is a policy decision, not a worker implementation. It freezes:

- consumer repository identity;
- integration, release, and temporary feature branch route;
- requested and authorized actions;
- allowed and protected repository paths;
- required CI checks;
- explicit task human gates plus only those policy approval categories applicable to the request's declared change classes;
- execution budgets;
- worker adapter/provider identity;
- Engineering Run ledger identity.

The worker is replaceable. A ChatGPT/Codex adapter, Claude adapter, GitHub-native coding agent, or local executor can consume the same envelope.

## Delivery gates

Authorization does not mean merge authority.

1. `authorize_execution` validates the consumer route and bounded authority.
2. The worker performs only the authorized task on the feature branch.
3. `verify_worker_result` independently checks branch identity, changed paths, actions, protected paths, shared-branch writes, and any required pre-PR evidence.
4. A verified worker result permits PR creation.
5. Policy `human_approval_for` entries are approval categories, not universal gates. Only categories declared by the request's `change_classes` become gates, plus any explicit task-level `human_gates`.
6. `evaluate_delivery_gate` requires every consumer CI check and every applicable human gate before merge authority becomes true.
7. Release writes remain false in this execution envelope. Production promotion is a separate consumer release decision.

This separation lets a visual consumer feature reach a green PR while still stopping for human experiential acceptance.

## First dogfood

World Vibes issue #31 is the first intended measured consumer run. Its envelope should authorize a `feature/* -> develop` implementation and require the product's visual-acceptance gate before integration merge. The Engineering Run ledger records where the current system required human intervention or could not execute a capability.
