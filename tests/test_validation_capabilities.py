from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_validation_capability.py"
SPEC = importlib.util.spec_from_file_location("run_validation_capability", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(module)


class ValidationCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = module.load_registry()
        cls.evidence_schema = json.loads(
            (ROOT / "schemas" / "validation-capability-evidence-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def _capability(self, capability_id: str) -> dict[str, object]:
        return module.select_capabilities(self.registry, [capability_id])[0]

    def _limits(self, **overrides: int | float | None) -> dict[str, int | float | None]:
        limits: dict[str, int | float | None] = {
            "max_steps": None,
            "max_elapsed_minutes": None,
            "max_retries": None,
            "max_cost_usd": None,
        }
        limits.update(overrides)
        return limits

    def test_registry_exposes_three_independent_capabilities(self) -> None:
        selected = module.select_capabilities(
            self.registry,
            ["test.browser_e2e", "test.container_integration"],
        )
        self.assertEqual(
            ["test.browser_e2e", "test.container_integration"],
            [capability["id"] for capability in selected],
        )
        self.assertNotIn("test.http_contract", [capability["id"] for capability in selected])

    def test_unknown_capability_fails_closed(self) -> None:
        with self.assertRaises(module.CapabilityExecutionError):
            module.select_capabilities(self.registry, ["test.product_specific"])

    def test_registry_guidance_is_tool_swappable(self) -> None:
        browser = self._capability("test.browser_e2e")
        http = self._capability("test.http_contract")
        container = self._capability("test.container_integration")
        self.assertGreaterEqual(len(browser["implementations"]), 2)
        self.assertGreaterEqual(len(http["implementations"]), 2)
        self.assertGreaterEqual(len(container["implementations"]), 2)
        self.assertIn("Playwright", {item["name"] for item in browser["implementations"]})
        self.assertIn("Hurl", {item["name"] for item in http["implementations"]})
        self.assertIn("Testcontainers", {item["name"] for item in container["implementations"]})

    def test_passing_command_emits_schema_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_capability(
                capability=self._capability("test.http_contract"),
                command=[sys.executable, "-c", "print('contract ok')"],
                implementation="fixture",
                limits=self._limits(max_steps=3, max_elapsed_minutes=1, max_retries=1),
                working_directory=Path(temp),
            )
        self.assertEqual("passed", evidence["status"])
        self.assertEqual(1, evidence["attempts"])
        self.assertEqual(0, evidence["retry_count"])
        self.assertIsNone(evidence["budget"]["exhausted_dimension"])
        self.assertEqual([], list(Draft202012Validator(self.evidence_schema).iter_errors(evidence)))

    def test_ordinary_command_failure_is_not_budget_exhaustion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_capability(
                capability=self._capability("test.browser_e2e"),
                command=[sys.executable, "-c", "raise SystemExit(4)"],
                implementation="fixture",
                limits=self._limits(max_steps=3, max_elapsed_minutes=1, max_retries=2),
                working_directory=Path(temp),
                retry_on_failure=False,
            )
        self.assertEqual("test_failed", evidence["status"])
        self.assertIsNone(evidence["budget"]["exhausted_dimension"])
        self.assertEqual(4, evidence["attempt_results"][-1]["return_code"])

    def test_step_budget_exhaustion_is_distinct_from_test_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_capability(
                capability=self._capability("test.container_integration"),
                command=[sys.executable, "-c", "raise SystemExit(1)"],
                implementation="fixture",
                limits=self._limits(max_steps=1, max_elapsed_minutes=1, max_retries=5),
                working_directory=Path(temp),
                retry_on_failure=True,
            )
        self.assertEqual("budget_exhausted", evidence["status"])
        self.assertEqual("max_steps", evidence["budget"]["exhausted_dimension"])
        self.assertEqual(1, evidence["attempts"])

    def test_retry_budget_exhaustion_is_distinct_from_test_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_capability(
                capability=self._capability("test.http_contract"),
                command=[sys.executable, "-c", "raise SystemExit(1)"],
                implementation="fixture",
                limits=self._limits(max_steps=5, max_elapsed_minutes=1, max_retries=1),
                working_directory=Path(temp),
                retry_on_failure=True,
            )
        self.assertEqual("budget_exhausted", evidence["status"])
        self.assertEqual("max_retries", evidence["budget"]["exhausted_dimension"])
        self.assertEqual(2, evidence["attempts"])
        self.assertEqual(1, evidence["retry_count"])

    def test_retry_requires_an_explicit_retry_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(module.CapabilityExecutionError):
                module.run_capability(
                    capability=self._capability("test.http_contract"),
                    command=[sys.executable, "-c", "raise SystemExit(1)"],
                    implementation="fixture",
                    limits=self._limits(max_steps=5),
                    working_directory=Path(temp),
                    retry_on_failure=True,
                )

    def test_elapsed_time_budget_is_evaluated_independently(self) -> None:
        dimension = module.budget_exhaustion_dimension(
            self._limits(max_steps=10, max_elapsed_minutes=0.5, max_retries=3),
            steps=1,
            retries=0,
            elapsed_minutes=0.5,
            cost_usd=0.0,
            retrying=False,
        )
        self.assertEqual("max_elapsed_minutes", dimension)

    def test_cost_budget_prevents_next_attempt(self) -> None:
        dimension = module.budget_exhaustion_dimension(
            self._limits(max_cost_usd=0.25),
            steps=0,
            retries=0,
            elapsed_minutes=0.0,
            cost_usd=0.2,
            next_cost_usd=0.1,
            retrying=False,
        )
        self.assertEqual("max_cost_usd", dimension)

    def test_policy_required_budget_dimension_must_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            policy = Path(temp) / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "execution_budgets": {
                            "max_steps": 5,
                            "required_dimensions": ["max_steps", "max_retries"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(module.CapabilityExecutionError):
                module.load_budget_limits(policy)


if __name__ == "__main__":
    unittest.main()
