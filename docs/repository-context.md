# Repository-Aware Context

Repository-aware Context preparation connects an incoming engineering goal to the consumer repository that owns the product truth. It keeps product specification and remediation in the Context layer and preserves the Orchestrator boundary: the Orchestrator plans only after Context is ready.

## Flow

```text
human/system goal + repository reference
                 |
                 v
          Context Agent
                 |
        inspect repository
                 |
       spec readiness check
          /             \
       ready          not ready
        |                 |
        v                 v
 context manifest   remediation evidence
        |           + synthesized drafts
        v                 |
  Orchestrator       human/repo review
                          |
                    apply accepted specs
                          |
                    rerun Context
```

A synthesized draft is never proof of product authority. Basic Context may produce draft artifacts as evidence, but it does not write them into the consumer repository and does not unlock Orchestrator until repository-local authoritative specs are present.

## Context input

`context-input/v1` keeps repository linkage optional so existing non-repository workflows remain compatible. When repository context is supplied, the host provides a checked-out repository root or equivalent verified repository evidence.

Example:

```json
{
  "schema_version": "context-input/v1",
  "goal": "Implement the accepted feature",
  "context": [
    {
      "key": "product_objective",
      "value": "Deliver the accepted product outcome",
      "source": "human",
      "confidence": "high"
    }
  ],
  "repository": {
    "provider": "github",
    "identifier": "example/consumer",
    "ref": "develop",
    "manifest_path": "ai/project-context.json",
    "feature_spec": "ai/specs/example-feature.md",
    "bootstrap": {"allowed": true}
  }
}
```

Repository identity is provenance. The Basic implementation does not fetch a remote repository itself; a host adapter is responsible for making the referenced repository state available locally or supplying equivalent verified evidence.

## Repository context manifest

Consumers can declare their authoritative spec locations with `repository-context/v1`:

```json
{
  "schema_version": "repository-context/v1",
  "specs": {
    "product": {
      "path": "ai/project/product.md",
      "required": true
    },
    "architecture": {
      "path": "ai/project/architecture.md",
      "required": true
    }
  },
  "feature_specs": {
    "directory": "ai/specs",
    "required_for_feature_work": true
  }
}
```

The default manifest location is `ai/project-context.json`. Defaults used only for remediation are:

- product: `ai/project/product.md`;
- architecture: `ai/project/architecture.md`;
- feature specs: `ai/specs/`.

A consumer may choose different paths by declaring them in its manifest. Product-specific content remains in the consumer repository.

## Spec readiness

A spec is ready only when it exists, declares an authoritative/accepted/active/approved status, and contains the minimum structural sections for its kind.

Product specs require equivalent headings for:

- Objective or Purpose;
- Scope or Non-goals;
- Constraints;
- Provenance or Sources.

Architecture specs require:

- Architecture or Components;
- Constraints;
- Validation;
- Provenance or Sources.

Feature specs require:

- Outcome or Goal;
- Requirements or Scope;
- Acceptance criteria or Acceptance;
- Human gates or Human gate;
- Provenance or Sources.

These are structural readiness checks, not a claim that the platform can determine whether a human product decision is correct.

## Remediation and bootstrap

If required specs are missing and `repository.bootstrap.allowed=true`, Basic Context may emit synthesized draft artifacts. Drafts are explicitly marked:

```text
Status: DRAFT - SYNTHESIZED
```

Drafts must preserve provenance and leave unknown product or architecture decisions unresolved. They are written only to the configured run-output directory. Basic Context does not apply them to the consumer repository.

The resulting context manifest remains:

```text
ready_for_orchestration: false
handoff.allowed: false
```

The expected remediation loop is:

1. inspect the generated draft;
2. reconcile it with repository evidence and human intent;
3. commit the accepted spec through the consumer repository's normal governed route;
4. mark it authoritative only when accepted;
5. rerun Context;
6. allow Orchestrator only after the rerun proves spec readiness.

If a material product decision cannot be derived from accepted human context or repository evidence, Context asks a human question instead of inventing authority.

## Precedence

Repository-aware Context follows the shared source-of-truth precedence:

1. safety, security, platform, and tool constraints;
2. direct human instructions for the active task;
3. accepted issue outcome and acceptance criteria;
4. repository-local product, architecture, feature, and steering documents;
5. the consumer's synchronized platform contract;
6. general platform standards and profiles.

A synthesized draft never outranks the sources from which it was derived.

## Orchestrator boundary

The Orchestrator remains unchanged. It requires both:

- `readiness.ready_for_orchestration=true`;
- `handoff.allowed=true`.

Repository-linked Context forces both false when required specs are missing, invalid, or still draft. This keeps remediation separate from execution planning and prevents the Orchestrator from silently creating product truth.

## Basic-tier authority

The Basic repository-aware Context path may:

- inspect a local repository tree supplied by the host;
- validate the repository context manifest;
- inspect declared product, architecture, and feature specs;
- report missing/invalid/draft state;
- emit non-authoritative remediation drafts;
- produce a Context manifest and run evidence.

It may not:

- mutate the consumer repository;
- promote a draft to authoritative status;
- resolve material product ambiguity without accepted evidence;
- bypass Context readiness and dispatch the Orchestrator.
