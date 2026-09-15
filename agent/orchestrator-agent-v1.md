# Orchestrator Agent v1

The Orchestrator Agent sits after the Context Agent. It accepts only a context handoff that is explicitly ready and allowed, then determines the minimum sufficient capability graph for the stated goal. It does not repair missing context.

## Independent operating dimensions

Every run declares three independent dimensions:

- **service tier**: Basic, Managed, or Full;
- **autonomy**: advisory, supervised, or policy-governed;
- **mode**: demo, test, or production.

`v1.0.0` implements only the **Basic** service tier. Requests for Managed or Full fail closed.

## Basic tier

Basic can:

1. validate a `context-manifest/v1` handoff;
2. inspect a `capability-registry/v1` registry;
3. map the goal/context to capabilities through deterministic registry signals;
4. include required capability dependencies;
5. validate an acyclic dependency graph;
6. explain why capabilities were selected or skipped;
7. produce an `execution-plan/v1` artifact.

Basic does **not** dispatch downstream agents, manage live task state, retry work, re-plan from runtime feedback, schedule parallel execution, or optimize cost/capacity. Those behaviors remain locked at higher tiers.

## Context boundary

The Orchestrator rejects a handoff when:

- `readiness.ready_for_orchestration` is not `true`;
- `handoff.allowed` is not `true`; or
- the handoff targets something other than the Orchestrator.

The Orchestrator does not ask intake questions or reinterpret blocking context. That remains the Context Agent's responsibility.

## Planning

The Basic planner uses the capability registry as its available organization. A capability declares its provider, trigger terms, dependencies, inputs, outputs, risk, minimum service tier, and human-gate requirement.

The planner selects directly relevant Basic capabilities, expands their required dependencies, validates that the resulting graph is acyclic, and orders dependencies before consumers. Capabilities that are considered but unnecessary remain visible with a skip reason.

## Demo mode

Demo mode executes the same validation and planning logic as test and production. Downstream steps are displayed as `WOULD_INVOKE`; no downstream agent is actually dispatched by Basic.

The demo shows:

- active tier, autonomy, and mode;
- capabilities selected and why;
- dependency relationships;
- capabilities considered but skipped and why;
- Managed and Full Orchestrator capabilities locked by tier;
- downstream dispatch count, which is always zero at Basic.

## Handoff

Basic produces:

- `execution-plan.yaml` for the future execution runtime / Human Lead Console;
- `orchestrator-run.json` as machine-readable run evidence.

The execution plan remains planning evidence until a later Managed Orchestrator is authorized to dispatch downstream agents.
