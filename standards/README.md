# Engineering Standards

Shared Git, testing, dependency, security, delivery, observability, and documentation standards belong here.

Standards describe preferred golden paths, required guardrails, recovery safety nets, and human checkpoints. Every normative standard should identify its version, compatibility expectations, and executable validation where practical.

## Current standards

- `platform-compatibility-v1.json` inventories public contracts, schemas, profiles, workflows, templates, and deprecations.
- `fast-feedback-v1.json` maps host-neutral validation stages to this repository's executable commands.
- `architecture-rules-v1.json` couples enforceable architecture decisions to validators, tests, and repair guidance.
- `validation-capabilities-v1.json` defines repository-agnostic browser E2E, HTTP contract, and container integration interfaces with tool-swappable implementation guidance.

Validation capability commands remain consumer-owned. The standard may name example tools such as Playwright, Hurl, and Testcontainers, but it must not encode product URLs, selectors, database choices, container images, credentials, or service topology.
