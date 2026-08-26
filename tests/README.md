# Platform Tests

Executable policy fixtures and steering scenarios belong here.

Tests should cover both accepted and rejected behavior. A prose rule is incomplete when the same decision can be represented deterministically in code or data.

## Current suites

- `test_validate_platform_layout.py` exercises the platform layout and release-metadata validator against temporary valid and invalid repository fixtures.
- `test_validate_delivery_route.py` executes the reusable feature, promotion, synchronization, hotfix, direct-main rejection, and ambiguity matrix in `fixtures/delivery-routes.json`.
- `test_agent_steering_scenarios.py` verifies the required autonomous, recovery, and human-gate decisions in `fixtures/agent-steering-scenarios-v1.json`.

Run the Python test suite with:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

CI also compiles `scripts` and `tests`, validates shell syntax, and parses every JSON and YAML file.

## Later suites

Later suites will cover policy schema fixtures and reusable workflow interface checks.
