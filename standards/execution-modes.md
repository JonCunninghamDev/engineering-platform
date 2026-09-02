# Execution Modes Standard

Status: Proposed
Version: 0.1.0

## Purpose

Projects and substantial workflows should be designed so their decision logic can be exercised safely, demonstrated clearly, and promoted progressively before production side effects are enabled.

The standard execution modes are `active`, `observe`, `demo`, and `test`.

A consumer MAY mark a mode not applicable, but the project specification MUST make that decision explicit and explain why.

## Core invariant

Core business, policy, and security decision logic MUST be mode-independent.

Modes MAY change side-effect execution, external adapters, fixtures, narration, persistence destinations, and interaction surfaces. Modes MUST NOT silently weaken or replace the rules used to reach a decision.

The preferred architecture is:

```text
input
  -> normalization
  -> decision / policy logic
  -> planned actions
  -> execution boundary
       active  -> perform authorized side effects
       observe -> suppress side effects and record intent
       demo    -> safe scenario adapters plus evidence/narration
       test    -> deterministic test adapters and assertions
```

Systems SHOULD represent intended actions explicitly before execution so the same decision can be inspected, suppressed, demonstrated, tested, or performed.

## Modes

### Active

`active` is the side-effect-capable operating mode.

- Real authorized external effects MAY occur.
- Production security, policy, validation, authorization, and audit controls MUST remain enabled.
- A mode switch alone MUST NOT bypass an authorization or safety control.

### Observe

`observe` evaluates the same inputs and decision path that active mode would use while suppressing externally consequential side effects.

Observe mode MUST:

- calculate the intended decision and planned actions;
- prevent planned consequential actions from crossing the execution boundary;
- record that execution was suppressed because the system was observing;
- produce structured evidence sufficient to compare observed behavior with expected active behavior.

Where practical, new or materially changed high-risk integrations SHOULD run in observe mode before promotion to active mode.

An example evidence record:

```json
{
  "mode": "observe",
  "decision": "PASS",
  "planned_action": "SIGN_ARTIFACT",
  "executed": false,
  "reason": "side effects suppressed by observe mode"
}
```

Observe mode is not permission to contact production systems that themselves create consequential effects. Consumer specifications MUST identify which reads, calls, writes, notifications, credentials, and destinations are safe in observe mode.

### Demo

`demo` provides deterministic, human-understandable demonstrations of real application behavior using safe inputs and adapters.

Demo mode SHOULD support named scenarios covering meaningful happy paths and failure paths. It MAY provide narration, pauses, prompts, visual output, or controlled user interaction.

Demo mode MUST NOT be a separate fake implementation of the product logic. Demo scenarios MUST exercise the same core decision/policy code used by active mode.

Where practical, demo scenarios SHOULD be executable non-interactively and SHOULD share fixtures, scenario definitions, or assertions with integration tests. This allows the demonstration itself to become reproducible engineering evidence.

### Test

`test` is optimized for automated verification.

- Inputs and dependencies SHOULD be deterministic and isolated.
- External consequential side effects MUST be prevented unless an explicitly scoped integration environment is part of the test contract.
- Tests SHOULD assert decisions, planned actions, executed/suppressed actions, reason codes, and evidence records where relevant.
- A passing test suite SHOULD provide machine-verifiable evidence for the same invariants demonstrated interactively in demo mode.

## Specification requirements

For every new project and every substantial workflow, the specification MUST answer:

1. What happens in active mode?
2. What happens in observe mode?
3. What named scenarios does demo mode prove, including important failure paths?
4. What automated tests back those scenarios and invariants?
5. What structured evidence is produced for decisions, planned actions, executed actions, suppressed actions, and outcomes?
6. Which external interactions are permitted or forbidden in each mode?
7. If a mode is not applicable, why?

If these questions cannot be answered cleanly, the design SHOULD be reviewed for insufficient separation between decision logic and side effects.

## Promotion model

For new or high-risk capabilities, consumers SHOULD prefer progressive validation when practical:

```text
test -> demo -> observe -> active
```

Promotion SHOULD be based on evidence rather than the mode name alone. A consumer specification SHOULD define the acceptance evidence required before moving to a more consequential mode.

## Safety requirements

- The default mode MUST be explicit and SHOULD fail safe when configuration is missing or invalid.
- Mode selection MUST be observable in logs and evidence records.
- Observe and demo modes MUST NOT be described as safe unless their adapters and external interactions actually enforce the claimed side-effect boundary.
- Secrets, signing keys, production credentials, destructive operations, irreversible writes, external notifications, and similar consequential capabilities MUST be explicitly accounted for by the consumer specification.
- AI or agentic components MUST obey the same execution boundary and MUST NOT use a less restrictive mode to bypass deterministic authorization or policy controls.

## Evidence and validation

Consumers SHOULD maintain traceability between:

- specification requirements;
- mode-specific scenarios;
- automated tests;
- structured runtime evidence;
- architecture or security decisions where relevant.

A platform-level executable conformance check MAY be added once multiple consumer repositories provide enough concrete evidence to stabilize a machine-readable contract.

## Compatibility

This standard is additive to the engineering platform 0.1.x contract. Consumers adopting it SHOULD pin an engineering-platform release/commit according to the platform adoption rules. Until this proposed standard is included in a published platform release, consumers MUST identify the exact commit or branch used and MUST NOT represent it as part of the published `v0.1.0` steering baseline.
