# Architecture decisions

Architecture decisions live in `architecture/decisions/` as versioned `architecture-decision/v1` documents. The machine-readable rule registry is `standards/architecture-rules-v1.json`.

An accepted decision marked `enforcement.required=true` must reference at least one registered executable rule. Each rule must point back to exactly one ADR, identify a real validator/check and automated test, and provide repair guidance.

Use `python scripts/validate_architecture.py` to validate schemas, supersession links, ADR-to-rule and rule-to-ADR references, validator/test paths, and repository-specific architecture checks.

Prose-only rationale is allowed for non-enforceable decisions. An accepted enforceable constraint is incomplete until its executable rule exists.
