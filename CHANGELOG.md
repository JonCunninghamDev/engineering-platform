# Changelog

All notable platform changes are recorded here. Versions follow semantic versioning and correspond to verified GitHub releases.

## [1.0.0] - 2026-09-16

### Added

- first complete consumer-ready Engineering Platform release;
- Basic Context, Orchestrator, Builder, and Verifier agent vertical slices with explicit versioned handoffs;
- tier-aware demo behavior with visible capability and execution boundaries;
- deterministic Builder change-set evidence and Verifier validation evidence;
- machine-readable capability registry, execution plans, assignments, run reports, and policy contracts;
- reusable consumer CI with capability/profile-driven composition validation;
- protected-path governance and deterministic route-policy enforcement;
- two-long-lived-branch delivery model using `main` for released production state and `develop` for integration;
- release governance requiring validated `develop` to `main` promotion and explicit human approval;
- consumer-agnostic adoption, compatibility, rollback, and release-verification contracts.

### Changed

- promoted the platform from the initial shared steering baseline to a stable 1.0 consumer contract suitable for external adoption validation.

## [0.1.0] - 2026-07-31

### Added

- initial shared engineering-platform repository structure;
- published agent steering with instruction precedence, deterministic task selection, branch policy, validation, troubleshooting, and human acceptance gates;
- pinned-consumer adoption model with local product-specific overrides and failure isolation;
- startup release verification through `README.md`, `VERSION`, and GitHub release metadata;
- self-validation CI and automated release publication after successful Platform CI on `main`.
