# Changelog

All notable platform changes are recorded here. Versions follow semantic versioning and correspond to verified GitHub releases.

## [1.0.0] - 2026-09-16

### Added

- first stable consumer-ready Engineering Platform contract;
- governed Context -> Orchestrator -> Builder -> Verifier agent pipeline with deterministic handoff evidence;
- tier-aware agent behavior and explicit locked-capability reporting;
- machine-readable capability and policy contracts for consumer-agnostic adoption;
- reusable consumer CI composition and compatibility/upgrade contracts;
- protected-path governance and fail-closed delivery-policy validation;
- governed release-preparation route distinct from production promotion;
- two-long-lived-branch delivery model using `main` and `develop` with temporary work branches.

### Changed

- promoted the platform from the initial shared steering baseline to the first stable contract intended for external consumer-adoption validation;
- release governance now distinguishes ordinary implementation, metadata-only release preparation, and human-approved `develop -> main` production promotion.

## [0.1.0] - 2026-07-31

### Added

- initial shared engineering-platform repository structure;
- published agent steering with instruction precedence, deterministic task selection, branch policy, validation, troubleshooting, and human acceptance gates;
- pinned-consumer adoption model with local product-specific overrides and failure isolation;
- startup release verification through `README.md`, `VERSION`, and GitHub release metadata;
- self-validation CI and automated release publication after successful Platform CI on `main`.
