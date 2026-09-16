from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_consumer_agnostic.py"
SPEC = importlib.util.spec_from_file_location("validate_consumer_agnostic", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ConsumerAgnosticValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_generic_consumer_guidance_passes(self) -> None:
        self._write("docs/adoption.md", "Consumers pin a verified platform release.\n")
        self.assertEqual([], validator.validate(self.root))

    def test_platform_self_reference_is_allowed(self) -> None:
        self._write(
            "docs/adoption.md",
            "Pin JonCunninghamDev/engineering-platform by immutable release commit.\n",
        )
        self.assertEqual([], validator.validate(self.root))

    def test_sibling_repository_reference_is_rejected(self) -> None:
        self._write(
            "docs/adoption.md",
            "The first consumer is JonCunninghamDev/example-product.\n",
        )
        errors = validator.validate(self.root)
        self.assertEqual(1, len(errors))
        self.assertIn("JonCunninghamDev/example-product", errors[0])
        self.assertIn("docs/adoption.md:1", errors[0])

    def test_sibling_reference_in_workflow_is_rejected(self) -> None:
        self._write(
            ".github/workflows/example.yml",
            "uses: JonCunninghamDev/example-consumer/.github/workflows/ci.yml@main\n",
        )
        errors = validator.validate(self.root)
        self.assertEqual(1, len(errors))
        self.assertIn(".github/workflows/example.yml:1", errors[0])

    def test_external_actions_are_not_treated_as_consumer_coupling(self) -> None:
        self._write(
            ".github/workflows/example.yml",
            "uses: actions/checkout@v4\nuses: docker/setup-buildx-action@v3\n",
        )
        self.assertEqual([], validator.validate(self.root))

    def test_test_fixtures_are_outside_shared_surface_scan(self) -> None:
        self._write(
            "tests/fixture.txt",
            "JonCunninghamDev/example-product\n",
        )
        self.assertEqual([], validator.validate(self.root))

    def test_current_repository_shared_surfaces_are_consumer_agnostic(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        self.assertEqual([], validator.validate(repository_root))


if __name__ == "__main__":
    unittest.main()
