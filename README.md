# Engineering Platform

A governed, agent-native engineering platform for running software work through explicit context, planning, capability, policy, testing, review, observability, and human-decision boundaries.

**Expected platform version:** `1.0.0`  
**Expected release tag:** `v1.0.0`

`main` is the released/production source of truth. `develop` is the current integration branch. During release preparation, `VERSION` and this metadata describe the release being prepared; the version is published only after the matching verified GitHub release exists on `main`.

This repository is the **authoring source of truth** for reusable Engineering Platform contracts, schemas, standards, policy, agent implementations, tests, workflows, and release governance.

## Current stable contract

The v1.0 development line provides a governed agent pipeline with explicit, inspectable boundaries:

- **Basic Context Agent** validates and normalizes supplied context, preserves provenance, and emits `context.yaml`.
- **Basic Orchestrator Agent** accepts ready context, selects minimum sufficient capabilities, builds an acyclic dependency graph, and emits `execution-plan.yaml`.
- **Basic Builder Agent** accepts explicit Builder authority, enforces file scope, computes deterministic diffs and hashes, and emits a zero-write `change-set.yaml` proposal.
- **Basic Verifier Agent** validates Builder evidence against its assigned scope and verification contract and emits deterministic verification evidence.
- **Tier-aware behavior** reports active service tier, autonomy, execution mode, and locked higher-tier capabilities rather than pretending unavailable capabilities executed.
- **Consumer-agnostic policy and CI contracts** support pinned external adoption without embedding consumer identity or product architecture in this repository.
- **Two-long-lived-branch delivery** keeps `main` as production and `develop` as integration, with temporary work branches and explicit release governance.

The Basic Orchestrator intentionally plans rather than silently dispatching downstream authority. Builder and Verifier handoffs remain explicit so planning, assignment, proposed change, and verification are independently inspectable.

## Agent operating model

The platform separates role, service tier, autonomy, and execution mode. An effective agent is composed from a role, capability set, tier, autonomy policy, and execution mode rather than from a separate prompt for every product package.

Current roles include Context, Orchestrator, Builder, and Verifier. Additional roles can be introduced only through governed platform changes.

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
        | deterministic verification evidence
        v
Human / governed downstream decision
```

Agent handoffs are versioned artifacts rather than implicit conversation state. Current contracts cover context, capability registry, execution planning, Builder assignment, change-set evidence, Verifier evidence, engineering policy, and machine-readable run reporting.

## Demo mode

Demo mode uses real decision, planning, and evidence logic but stops at consequential execution boundaries. A demo run should show received context, invocation reason, active tier/autonomy/mode, capabilities used or locked, decisions and reasons, artifacts produced, downstream handoff, and actions that would execute at a higher permitted level.

## Agent startup and release verification

`VERSION` declares the expected platform version. A version is published only when the latest non-draft, non-prerelease GitHub release exists with matching `v<VERSION>` tag and the tagged commit is reachable from `main`.

When an agent starts work in this repository it must:

1. Verify repository access and confirm the default branch is `main`.
2. Read this README and `VERSION`.
3. Verify the expected release against GitHub release metadata when operating from released `main`.
4. Read `AGENTS.md`, `agent/operating-contract-v1.md`, `docs/task-management.md`, and steering required for the active task.
5. Inspect current issues, pull requests, CI, reviews, and branch state.
6. Confirm `develop` contains all current `main` history before ordinary implementation work.
7. Continue the deterministic active task rather than relying on conversational memory.

Branch-local files may guide development, but they are not consumer-authoritative until released through `main`.

## Development workflow

The repository uses exactly two long-lived branches:

- `main` — released/production state;
- `develop` — current integration state and base for implementation work.

Ordinary implementation follows:

```text
develop -> temporary implementation branch -> PR + tests + Platform CI -> develop
```

Release preparation follows the separately governed metadata route:

```text
develop -> release/X.Y.Z -> Prepare Release: PR + Platform CI -> develop
```

Production promotion remains:

```text
develop -> reviewed Release: PR + explicit human approval -> main
```

Rules:

1. Synchronize current `main` history into `develop` before ordinary implementation when needed.
2. Create implementation and release-preparation branches from current `develop`.
3. Target work back to `develop` and require the route-specific policy evidence.
4. Add or update automated tests for changed executable behavior. Metadata-only release preparation does not require artificial test edits.
5. Run the full suite before considering executable changes ready:

   ```bash
   python -m unittest discover -s tests -p 'test_*.py' -v
   ```

6. Platform CI validates route policy, required test evidence, repository structure, Python tests and compilation, shell syntax, JSON, and YAML.
7. Production reaches `main` only through a `develop -> main` `Release:` PR with explicit human approval.
8. Synchronize approved `main` release history back into `develop` when required.
9. Delete temporary branches after merge.
10. There is no separate direct-to-`main` hotfix route.

## Implementation authority and human gates

Agents may make bounded, reversible, local, testable engineering decisions inside accepted work when repository policy permits them. Human approval remains required for consequential boundaries including shared agent authority, public policy/schema changes with consumer impact, reusable workflow behavior, credentials/security authority, destructive migrations, backward-incompatible contracts, ambiguous cross-repository risk, and every `develop -> main` release promotion.

Automated tests are evidence, not a substitute for human acceptance of consequential changes.

## What belongs in this repository

Centralize reusable engineering mechanics and contracts: agent operating contracts, context/capability/handoff/run/policy schemas, deterministic task and delivery rules, reusable CI/CD, common testing/security/observability standards, service-tier definitions, telemetry/evidence contracts, templates, and adoption guidance.

Keep product- and engagement-specific truth in consumer repositories: product purpose, application architecture, customer/employer credentials, environment-specific ownership, repository-specific exceptions, visual/product decisions, and migration work.

## Adoption model

A consumer repository should pin a verified Engineering Platform release rather than depend on the live platform repository during every run. Consumers can pin a released tag and immutable commit, keep concise repository-local steering and synchronized contracts, invoke reusable workflows by immutable version, adopt updates through focused tested PRs, and remain independently buildable and revertible if this repository is unavailable.

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

**v1.0.0 release target**

- governed Context -> Orchestrator -> Builder -> Verifier pipeline;
- deterministic evidence and tier-aware behavior;
- consumer-agnostic policy, CI, compatibility, and rollback contracts;
- protected-path and pull-request governance;
- explicit release preparation and human-approved production promotion.

**After v1.0.0 publication**

1. Validate the external consumer adoption path in issue #5.
2. Gather operating evidence and a single-agent baseline from a real consumer.
3. Add measured multi-agent scaling under issue #27 only after those dependencies are satisfied.
