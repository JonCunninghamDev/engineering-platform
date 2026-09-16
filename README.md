# Engineering Platform

A governed, agent-native engineering platform for running software work through explicit context, planning, capability, policy, testing, review, observability, and human-decision boundaries.

**Published platform version:** `1.0.0`  
**Published release tag:** `v1.0.0`  
**Expected release tag:** `v1.0.0`

`main` is the released/production source of truth. `develop` is the current integration branch and may contain capabilities that are not yet part of the published release.

This repository is the authoring source of truth for reusable Engineering Platform contracts, schemas, standards, policy, agent implementations, tests, workflows, and release governance. Product-specific truth belongs in consumer repositories.

## Current platform state

Version 1.0.0 establishes the first stable consumer-ready platform contract. The implemented agent-native flow includes:

- **Basic Context Agent** — validates and normalizes supplied context, identifies missing or conflicting required information, preserves provenance, and emits an inspectable `context.yaml` handoff.
- **Basic Orchestrator Agent** — accepts a ready Context handoff, inspects the machine-readable capability registry, selects the minimum sufficient capabilities, builds an acyclic dependency graph, explains selected and skipped capabilities, and emits `execution-plan.yaml`.
- **Basic Builder Agent** — accepts explicit Builder authority linked to a selected capability, enforces allowed/protected file scope, computes deterministic unified diffs and content hashes, and emits a zero-write `change-set.yaml` proposal.
- **Basic Verifier Agent** — validates Builder evidence and candidate changes against declared requirements and produces deterministic verification evidence for downstream decisions.
- **Tier-aware behavior** — runs explicitly report service tier, autonomy, and execution mode and show higher-tier capabilities as locked rather than pretending they executed.
- **Reusable consumer CI** — validates generic consumer capability/profile compositions without embedding consumer identity or product architecture in the platform.
- **Governed delivery** — protected paths, branch routes, tests, CI, and human release boundaries are enforced as executable policy.

## Agent operating model

The platform separates four dimensions:

1. **Role** — Context, Orchestrator, Builder, Verifier, Reviewer, Architect, Operations, or another explicit provider role.
2. **Service tier** — how much of that role's responsibility is implemented, currently modeled as Basic, Managed, and Full.
3. **Autonomy** — what the agent may decide or execute without approval.
4. **Execution mode** — demo, test, or production.

An effective agent is composed from a role, capability set, tier, autonomy policy, and execution mode rather than from a separate product-specific prompt.

## Current agent flow

```text
Human / system context
        |
        v
Context Agent
        |
        | context.yaml
        v
Orchestrator Agent
        |
        | execution-plan.yaml
        v
Explicit Builder assignment
(builder-task/v1)
        |
        v
Builder Agent
        |
        | change-set.yaml
        v
Verifier Agent
        |
        | verification evidence
        v
Downstream review / human gate as required
```

Planning, assignment, proposed implementation, verification, and consequential execution remain distinct inspectable boundaries.

## Contracts and evidence

Agent handoffs are first-class versioned artifacts rather than implicit conversation state. Current contracts include context contracts and inputs, normalized context manifests, the capability registry, execution plans, Builder assignments, deterministic change sets, verification evidence, policy contracts, and machine-readable agent run reports.

A downstream agent must be able to determine what it received, where it came from, what processing produced it, what authority applies, what evidence exists, and whether the next handoff is permitted.

## Demo mode

Demo mode uses real decision, planning, evidence, and validation logic while stopping at consequential execution boundaries. A run should show inputs, invocation reason, active tier/autonomy/mode, capabilities used, skipped and locked capabilities, decisions and reasons, artifacts, downstream handoffs, and actions that would execute at a higher permitted level.

## Agent startup and release verification

The `VERSION` file declares the expected published platform version. A version is published only when the latest non-draft, non-prerelease GitHub release exists with the matching `v<VERSION>` tag and the tagged commit is reachable from `main`.

When an agent starts work in this repository it must:

1. Verify repository access and confirm the default branch is `main`.
2. Read this README first.
3. Read `VERSION` and form the expected release tag as `v<VERSION>`.
4. Query the latest non-draft, non-prerelease GitHub release and verify that its tag matches the expected tag and its tagged commit is reachable from `main`.
5. Read `AGENTS.md`, `agent/operating-contract-v1.md`, `docs/task-management.md`, and other steering required for the active task.
6. Inspect current issues, pull requests, CI, reviews, and branch state.
7. Confirm `develop` contains all current `main` history before implementation work.
8. Continue the deterministic active task rather than relying on conversational memory.

Branch-local files may guide development, but they are not consumer-authoritative until released through `main`.

## Development workflow

The repository uses exactly two long-lived branches:

- `main` — released/production state;
- `develop` — current integration state and base for implementation work.

Every feature, defect, or release-preparation change follows the governed route:

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
   | Release: PR + explicit human approval
   v
main
```

Rules:

1. Synchronize current `main` history into `develop` before ordinary implementation work when needed.
2. Create implementation branches from current `develop`.
3. Target implementation PRs back to `develop`.
4. Add or update automated tests for changed behavior when behavior changes.
5. Run the full suite before considering a change ready:

   ```bash
   python -m unittest discover -s tests -p 'test_*.py' -v
   ```

6. Platform CI validates route policy, required test-change evidence, repository structure, the full Python suite, Python compilation, shell syntax, JSON, and YAML.
7. Production changes reach `main` only through a `develop -> main` `Release:` PR with explicit human approval.
8. Synchronize approved `main` release history back into `develop` when required.
9. Delete temporary implementation branches after merge.
10. There is no separate direct-to-`main` hotfix route.

## Human gates

Agents may make bounded, reversible, local, testable engineering decisions inside accepted work when repository policy permits them. Human approval remains required for consequential boundaries including shared agent authority, public policy/schema changes with consumer impact, reusable workflow authority, credentials/security authority, destructive migrations, backward-incompatible contracts, ambiguous cross-repository risk, and every `develop -> main` release promotion.

Automated tests are evidence, not a substitute for human acceptance of consequential changes.

## What belongs here

Centralize reusable engineering mechanics and contracts: agent operating contracts, versioned schemas, deterministic task/delivery rules, reusable CI/CD, common testing/security/observability standards, capability and service-tier definitions, telemetry/evidence contracts, and reusable adoption guidance.

Keep product- and engagement-specific truth in consumer repositories or engagement configuration: product purpose, application architecture, domain acceptance criteria, credentials, environment-specific permissions, repository-specific risk exceptions, and product decisions that are not reusable platform policy.

## Adoption model

A consumer repository should pin a verified Engineering Platform release rather than depend on the live platform repository during every run. A consumer can pin the released tag and immutable commit, keep concise repository-local steering and product truth, keep required synchronized contracts locally, invoke reusable workflows by immutable release reference, adopt updates through focused tested pull requests, and remain independently buildable and revertible if this repository is unavailable.

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

## Release history and roadmap

**v0.1.0** established the initial repository, steering, validation, CI, and release foundation.

**v1.0.0** establishes the first stable consumer-ready contract with the Context → Orchestrator → Builder → Verifier flow, tier-aware evidence, governed branch/release policy, reusable consumer CI, protected-path enforcement, and consumer-agnostic adoption/rollback contracts.

The next validation milestone is external consumer adoption. Measured multi-agent scaling follows only after successful consumer operation and collection of a reliable single-agent baseline.
