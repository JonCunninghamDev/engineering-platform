# Platform Tests

Executable policy fixtures and steering scenarios belong here.

Tests should cover both accepted and rejected behavior. A prose rule is incomplete when the same decision can be represented deterministically in code or data.

## Current suites

- `test_validate_platform_layout.py` exercises the platform layout and release-metadata validator against temporary valid and invalid repository fixtures.

Run the current Python test suite with:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Planned suites

Planned suites include delivery routing, policy schema fixtures, reusable workflow interface checks, and agent authority scenarios.
