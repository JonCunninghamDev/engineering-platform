import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "consumer-adoption" / "consumer-manifest.json"
ADOPTION_DOC = ROOT / "docs" / "adoption.md"


class ConsumerAdoptionContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_manifest_pins_release_and_immutable_commit(self):
        platform = self.manifest["platform"]
        self.assertRegex(platform["version"], r"^v\d+\.\d+\.\d+$")
        self.assertRegex(platform["commit"], r"^[0-9a-f]{40}$")
        self.assertNotIn("JonCunninghamDev", platform["repository"])

    def test_local_steering_does_not_require_runtime_platform_access(self):
        steering = self.manifest["local_steering"]
        self.assertFalse(steering["runtime_platform_access_required"])
        self.assertIn("AGENTS.md", steering["files"])
        self.assertTrue(any("operating-contract" in path for path in steering["files"]))

    def test_reusable_ci_uses_generic_capabilities_and_immutable_pin(self):
        reusable_ci = self.manifest["reusable_ci"]
        self.assertEqual(reusable_ci["workflow"], ".github/workflows/reusable-consumer-ci.yml")
        self.assertRegex(reusable_ci["pin"], r"^[0-9a-f]{40}$")
        self.assertEqual(reusable_ci["capabilities"], ["node", "python"])

    def test_upgrade_evidence_is_explicit_and_reversible(self):
        upgrade = self.manifest["upgrade"]
        self.assertTrue(upgrade["compatibility_impact"])
        self.assertIn("complete-required-suite", upgrade["validation_evidence"])
        self.assertIn("consumer-ci", upgrade["validation_evidence"])
        self.assertIn("previous immutable platform pin", upgrade["rollback"])

    def test_documentation_preserves_failure_isolation(self):
        text = ADOPTION_DOC.read_text(encoding="utf-8")
        self.assertIn("## Failure isolation", text)
        self.assertIn("must not prevent", text)
        self.assertIn("reading local steering", text)
        self.assertIn("running local tests", text)
        self.assertIn("rolling back a platform upgrade", text)


if __name__ == "__main__":
    unittest.main()
