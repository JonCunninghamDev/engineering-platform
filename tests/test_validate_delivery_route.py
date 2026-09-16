from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-delivery-route.py"
FIXTURES = Path(__file__).parent / "fixtures" / "delivery-routes.json"

spec = importlib.util.spec_from_file_location("validate_delivery_route", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class DeliveryRouteMatrixTests(unittest.TestCase):
    def test_route_matrix(self) -> None:
        scenarios = json.loads(FIXTURES.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(scenarios), 10)
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                result = module.validate_route(
                    base=scenario["base"],
                    head=scenario["head"],
                    title=scenario["title"],
                    default_branch=scenario.get("default_branch", "main"),
                    integration_branch=scenario.get("integration_branch", "develop"),
                )
                self.assertEqual(result.valid, scenario["valid"], result.errors)
                if scenario["valid"]:
                    self.assertEqual(result.route, scenario["route"])
                    self.assertEqual(result.errors, ())
                else:
                    self.assertTrue(result.errors)
                    self.assertIn(
                        scenario["error_contains"].lower(),
                        " ".join(result.errors).lower(),
                    )

    def test_cli_success_and_failure_are_actionable(self) -> None:
        valid = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--base",
                "develop",
                "--head",
                "agent/issue-2-example",
                "--title",
                "Issue #2: example",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertIn("delivery route valid: feature", valid.stdout)

        invalid = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--base",
                "main",
                "--head",
                "agent/issue-2-example",
                "--title",
                "Issue #2: example",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("direct-main route rejected", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
