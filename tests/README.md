# Platform Tests

Executable policy fixtures and steering scenarios belong here.

Tests should cover both accepted and rejected behavior. A prose rule is incomplete when the same decision can be represented deterministically in code or data.

## Current suites

- `test_validate_platform_layout.py` exercises the platform layout, CI-policy wiring, and release-metadata validator against temporary valid and invalid repository fixtures.
- `test_validate_delivery_route.py` executes the reusable feature, promotion, synchronization, direct-main rejection, urgent-fix, and ambiguity matrix in `fixtures/delivery-routes.json`.
- `test_validate_pr_policy.py` verifies that implementation PRs target `develop` and include new or updated automated tests.
- `test_agent_steering_scenarios.py` verifies the required autonomous, recovery, and human-gate decisions in `fixtures/agent-steering-scenarios-v1.json`.
- `test_context_agent.py` verifies Basic Context Agent readiness, missing required context, explicit contradiction detection, strict service-tier boundaries, demo evidence, and `context.yaml` / run-report artifact generation using `fixtures/context-agent/`.
- `test_orchestrator_agent.py` verifies Basic Orchestrator context validation, minimum capability selection, dependency ordering, cycle rejection, skipped-capability explanations, strict service-tier boundaries, zero dispatch, demo evidence, and execution-plan artifact generation using `fixtures/orchestrator/`.

Run the full Python test suite with:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

For implementation branches, add or update the relevant automated tests with the change and run the full suite before committing. Platform CI reruns the same suite for pull requests into `develop` and `main`.

CI also validates pull-request route/test evidence, compiles `scripts` and `tests`, validates shell syntax, and parses every JSON and YAML file.

## Later suites

Later suites will cover `engineering-policy/v1` schema fixtures and reusable workflow interface checks.
