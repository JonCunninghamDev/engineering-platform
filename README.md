# Engineering Platform

A governed, agent-native engineering platform for running software work through explicit context, planning, capability, policy, testing, review, observability, and human-decision boundaries.

**Published platform version:** `0.1.0`  
**Published release tag:** `v0.1.0`

`main` is the released/production source of truth. `develop` is the current integration branch and may contain capabilities that are not yet part of the published `v0.1.0` release.

This repository is the **authoring source of truth** for reusable Engineering Platform contracts, schemas, standards, policy, agent implementations, tests, workflows, and release governance.

The long-term goal is not a collection of coding bots. The platform is intended to provide a reusable operating system for governed engineering agents that can work across different repositories, tools, and engagements while keeping authority, evidence, and human accountability explicit.

## Current development state

The current `develop` line includes the first agent-native vertical slices:

- **Basic Context Agent** — validates and normalizes supplied context, identifies missing or conflicting required information, preserves provenance, and emits an inspectable `context.yaml` handoff.
- **Basic Orchestrator Agent** — accepts only a ready Context Agent handoff, inspects a machine-readable capability registry, selects the minimum sufficient capabilities for the stated goal, builds an acyclic dependency graph, explains selected and skipped capabilities, and emits `execution-plan.yaml`.
- **Tier-aware demo behavior** — agent runs explicitly report active service tier, autonomy, and execution mode and show higher-tier capabilities as locked rather than pretending they executed.
- **Two-long-lived-branch delivery model** — `main` is production, `develop` is integration, and all implementation work uses temporary branches created from current `develop` and merged back into `develop` before release promotion.

The Basic Orchestrator intentionally does **not** dispatch downstream agents. Live dispatch, runtime task-state management, retries, replanning, parallel execution, and human-gate routing are planned higher-tier orchestration capabilities.

## Agent operating model

The platform separates four dimensions that must not be conflated:

1. **Role** — what kind of work the agent performs, such as Context, Orchestrator, Builder, Verifier, Reviewer, Architect, or Operations.
2. **Service tier** — how much of that role's responsibility is implemented, currently modeled as Basic, Managed, and Full.
3. **Autonomy** — what the agent may decide or execute without approval.
4. **Execution mode** — whether the run is demo, test, or production.

An effective agent is therefore composed from a role, capability set, tier, autonomy policy, and execution mode rather than from a separate prompt for every product package.

For example:

```text
Context Agent
  tier: BASIC
  autonomy: ADVISORY
  mode: DEMO
```

may normalize supplied context and produce a handoff, while Managed and Full context-retrieval or maintenance capabilities remain visibly locked.

## Current agent flow

The implemented development flow is:

```text
Human / system context
        |
        v
Context Agent
BASIC | tier-aware | demo-capable
        |
        | context.yaml
        v
Orchestrator Agent
BASIC | planner only
        |
        | execution-plan.yaml
        v
Would-invoke downstream capabilities
(no Basic-tier dispatch)
```

The Orchestrator plans against a machine-readable capability registry. It records why a capability was selected, why a relevant capability was skipped, dependency ordering, provider role, risk, tier availability, and human-gate requirements.

This makes orchestration inspectable and prevents the default behavior of invoking every available agent for every task.

## Context and handoff contracts

Agent handoffs are first-class versioned artifacts rather than implicit conversation state.

Current contracts include:

- `context-contract/v1` — declares required, recommended, and optional context for a workflow;
- `context-input/v1` — represents supplied context and provenance;
- `context-manifest/v1` — records normalized context, readiness, provenance, tier/autonomy/mode, capability evidence, and downstream handoff permission;
- `capability-registry/v1` — describes available capabilities, providers, dependencies, risk, tier availability, and human-gate requirements;
- `execution-plan/v1` — records the Orchestrator's selected task graph and planned downstream work;
- `agent-run-report/v1` — provides machine-readable run evidence for demo tooling and future management interfaces.

The design principle is simple: a downstream agent should be able to determine exactly what it received, where the information came from, what level of processing produced it, and whether the handoff is permitted.

## Demo mode

Demo mode uses the real decision and planning logic but stops at consequential execution boundaries.

A demo run should show:

- what the agent received;
- why it was invoked;
- active service tier, autonomy, and mode;
- capabilities used;
- capabilities available at the active tier but unnecessary;
- capabilities locked by higher tiers;
- decisions and reasons;
- artifacts produced;
- downstream handoff;
- actions that **would** execute at a higher permitted level.

Basic Orchestrator demo output therefore reports downstream tasks as `WOULD_INVOKE` and records a dispatch count of zero.

## Human Lead and engagement direction

The planned management layer will treat each company, client, internal project, or other work relationship as an isolated **Engagement**.

A future Human Lead Console is expected to provide a consistent drill-down model:

```text
Engagement
  -> Stories
     -> Engineering Run
        -> Agent execution graph
           -> Agent evidence / artifacts / decisions
```

An engagement may define its own approved tools, repositories, communications sources, credentials, coding standards, cloud environment, policies, and agent tiers. Engagement context and credentials must remain isolated; generic platform capabilities may be reused, but confidential engagement data must not cross engagement boundaries without explicit authorization.

The console itself is not implemented in this repository yet. The contracts and telemetry produced here are intended to make such a UI possible without scraping prose or reconstructing hidden model state.

## Agent startup and release verification

The `VERSION` file declares the expected published steering version. A version is published only when the **latest non-draft, non-prerelease GitHub release** exists with the matching `v<VERSION>` tag and the tagged commit is reachable from `main`.

When an agent starts work in this repository it must:

1. Verify repository access with a real GitHub operation and confirm the default branch is `main`.
2. Read this README first.
3. Read `VERSION` and form the expected release tag as `v<VERSION>`.
4. Query the latest non-draft, non-prerelease GitHub release and verify that its tag matches the expected tag and its tagged commit is reachable from `main`.
5. Read `AGENTS.md`, `agent/operating-contract-v1.md`, `docs/task-management.md`, and other steering required for the active task.
6. Inspect current issues, pull requests, CI, reviews, and branch state.
7. Confirm `develop` contains all current `main` history before starting implementation work.
8. Continue the deterministic active task rather than relying on conversational memory.

Branch-local files may guide development, but they are not consumer-authoritative until released through `main`.

## Development workflow

The repository uses exactly two long-lived branches:

- `main` — released/production state;
- `develop` — current integration state and the base for all implementation work.

Every feature, defect, or urgent production fix follows the same route:

```text
develop
   |
   v
temporary implementation branch
   |
   | PR + tests + Platform CI
   v
develop
   |
   | reviewed Release: PR + human approval
   v
main
```

Rules:

1. Synchronize current `main` history into `develop` before ordinary implementation work when needed.
2. Create every implementation branch from current `develop`.
3. Target every implementation PR back to `develop`.
4. Add or update automated tests for changed behavior.
5. Run the full suite before considering the change ready for review:

   ```bash
   python -m unittest discover -s tests -p 'test_*.py' -v
   ```

6. Platform CI validates route policy, test-change evidence, repository structure, the full Python suite, Python compilation, shell syntax, JSON, and YAML.
7. Production changes reach `main` only through a `develop -> main` `Release:` PR with required human approval.
8. Synchronize approved `main` release history back into `develop` when required to keep integration current.
9. Delete temporary implementation branches after merge.
10. There is no separate direct-to-`main` hotfix route.

## Implementation authority and human gates

Agents may make bounded, reversible, local, testable engineering decisions inside an accepted issue when repository policy permits them.

Human approval remains required for consequential boundaries including shared agent authority, public policy/schema changes with consumer impact, reusable workflow behavior, credentials and security authority, destructive migrations, backward-incompatible contracts, ambiguous cross-repository risk, and every `develop -> main` release promotion.

Automated tests are evidence, not a substitute for human acceptance of consequential changes.

## What belongs in this repository

Centralize reusable engineering mechanics and contracts:

- agent operating contracts and specialized role contracts;
- context, capability, handoff, run, and policy schemas;
- deterministic task and delivery rules;
- reusable CI/CD workflows and actions;
- common testing, security, observability, and delivery standards;
- capability and service-tier definitions;
- telemetry and evidence contracts;
- reusable templates and adoption guidance.

Keep product- and engagement-specific truth in consumer repositories or engagement configuration:

- product purpose and business rules;
- application architecture and domain-specific acceptance criteria;
- customer/employer credentials and confidential context;
- environment-specific ownership and permissions;
- repository-specific risk exceptions;
- visual/product decisions that are not reusable platform policy.

## Adoption model

A consumer repository should pin a verified Engineering Platform release rather than depend on the live platform repository during every run.

A consumer can:

1. pin a released platform tag and immutable commit;
2. keep concise repository-local steering and product truth;
3. keep required synchronized contracts locally for fast and resilient startup;
4. invoke reusable workflows by pinned release or immutable SHA;
5. adopt platform updates through focused, tested pull requests;
6. remain independently buildable and revertible if this repository is unavailable.

## Repository layout

```text
agent/       operating contracts and specialized agent-role definitions
standards/   shared Git, testing, security, delivery, and observability standards
schemas/     versioned context, capability, handoff, run, and policy schemas
profiles/    reusable language, toolchain, service-tier, and policy profiles
templates/   consumer repository and workflow templates
actions/     reusable actions
.github/     repository-local and reusable GitHub workflows
docs/        adoption, task management, release, routing, and governance documentation
tests/       deterministic policy, agent, and steering tests and fixtures
scripts/     executable platform agents, validation, and maintenance commands
```

## Current roadmap

**Published foundation**

- `v0.1.0` repository, steering, validation, CI, and release foundation.

**Implemented on the current development line**

- two-long-lived-branch delivery policy;
- Basic Context Agent;
- context and run-report contracts;
- Basic Orchestrator Agent and capability registry;
- tier-aware demo behavior and deterministic agent tests.

**Next agent vertical slices**

1. Basic Builder Agent.
2. Basic Verifier Agent.
3. Basic Reviewer Agent.
4. Basic Architect Agent.
5. Basic Operations Agent.

**Platform expansion**

- `engineering-policy/v1` and composable permission profiles;
- Managed and Full service tiers;
- governed downstream dispatch and runtime task-state management;
- telemetry for wall time, agent execution, human attention, cost, rework, and accepted outcomes;
- engagement isolation contracts;
- Human Lead Console integration;
- consumer workflows such as Career Ops / Find Me a Job.
