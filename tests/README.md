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
- `test_builder_agent.py` verifies Basic Builder explicit assignment, execution-plan linkage, scope/protected-path enforcement, traversal and delete rejection, deterministic diff/hash evidence, strict service-tier boundaries, zero-write demo behavior, and change-set artifact generation using `fixtures/builder/`.
- `test_engineering_policy.py` validates `engineering-policy/v1` examples and invalid fixtures, independent Node/Python/Blender profile composition, permission fail-closed behavior, protected paths, required budget dimensions, explicit exceptions, and the policy CLI.
- `test_reusable_consumer_ci.py` validates the reusable workflow contract, stable job name, independent capability switches, fast/full semantics, bounded artifact retention, immutable pin templates, and generic consumer identity boundaries.
- `test_compatibility.py` validates the public compatibility manifest, VERSION alignment, surface paths, profile identifiers, reusable-workflow input inventory, stable job names, and deprecation/removal rules.
- `test_validate_consumer_agnostic.py` verifies that shared platform surfaces may reference the platform itself but reject references to sibling product repositories.

`Reusable CI Self-Test` additionally calls the reusable workflow in GitHub Actions with both Node/Python and Node/Python/Blender compositions so the workflow is exercised rather than only parsed.

Install development validation dependencies with:

```bash
python -m pip install -r requirements-dev.txt
```

Run the full Python test suite with:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Run the public-surface validator directly with:

```bash
python scripts/validate_compatibility.py
```

Run the consumer-agnostic boundary validator directly with:

```bash
python scripts/validate_consumer_agnostic.py
```

For implementation branches, add or update the relevant automated tests with the change and run the full suite before committing. Platform CI reruns the same suite for pull requests into `develop` and `main`.

CI also validates the public compatibility manifest, consumer-agnostic boundary, pull-request route/test evidence, repository layout, Python compilation, shell syntax, and every JSON/YAML file.

## Later suites

Later suites will cover policy enforcement adapters, observable execution budgets, and generic consumer-adoption validation.
