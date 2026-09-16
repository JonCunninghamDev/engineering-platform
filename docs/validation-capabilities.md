# Observable validation capabilities

The Engineering Platform defines reusable validation **interfaces**, not product test architecture. Consumers opt into only the capabilities they own and provide the concrete command, fixtures, environment, endpoints, credentials, and lifecycle behavior locally.

## Capability registry

`standards/validation-capabilities-v1.json` defines three independent v1 capabilities:

- `test.browser_e2e` for a real-browser user-interface check;
- `test.http_contract` for request/response contract validation;
- `test.container_integration` for integration checks against disposable containerized dependencies.

The registry includes implementation guidance such as Playwright, Hurl, and Testcontainers, but those are examples rather than required dependencies. Selenium/WebDriver, schema-driven HTTP tools, Docker Compose, or another repository-owned command may satisfy the same interface.

Consumers select the corresponding profile primitives independently:

- `capability.browser-e2e`
- `capability.http-contract`
- `capability.container-integration`

Do not add a capability merely because another consumer uses it.

## Budgeted execution

A repository-owned command can be executed through:

```bash
python scripts/run_validation_capability.py \
  --capability test.http_contract \
  --policy engineering-policy.json \
  --implementation hurl \
  --evidence .validation/http-contract.json \
  -- hurl --test tests/http/*.hurl
```

The runner reads `execution_budgets` from the supplied `engineering-policy/v1` document. Each command attempt consumes one step. Elapsed-time budgets become a hard subprocess timeout. Retries occur only when `--retry-on-failure` is explicitly requested and `max_retries` is configured, preventing an unbounded retry loop. `max_cost_usd` can be enforced when the caller supplies `--cost-per-attempt-usd`.

Evidence uses `validation-capability-evidence/v1` and records capability identity, implementation label, total duration, attempts, retry count, command, configured limits, consumed steps/time/retries/cost, the exhausted dimension when applicable, and per-attempt process output.

## Result semantics

The runner deliberately distinguishes:

- `passed`: the repository-owned validation command succeeded;
- `test_failed`: the command failed and no budget boundary caused termination;
- `budget_exhausted`: execution stopped because a configured step, elapsed-time, retry, or cost limit was reached;
- `configuration_error`: the capability, registry, policy, or invocation is not safe to execute.

A budget exhaustion is not evidence that the product test itself failed. Conversely, a normal test failure must not be mislabeled as budget exhaustion merely because a policy contains limits.

## CI integration

The reusable consumer CI remains tool-neutral. Consumers can invoke their repository-owned browser, HTTP, or container validation command through the appropriate existing test/build command surface or a repository-local job while using the same capability/profile identity and evidence contract.

Do not bake product URLs, database choices, selectors, ports, credentials, container images, or service topology into the Engineering Platform. Those remain consumer-owned configuration.
