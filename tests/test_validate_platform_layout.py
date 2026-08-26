from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate-platform-layout.py"
SPEC = importlib.util.spec_from_file_location("validate_platform_layout", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class PlatformLayoutValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self._write_valid_fixture()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write(self, relative: str, content: str = "placeholder\n") -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_valid_fixture(self) -> None:
        for relative in validator.REQUIRED_DIRECTORIES:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

        for relative in validator.REQUIRED_FILES:
            self._write(relative)

        self._write("VERSION", "0.1.0\n")
        self._write(
            "README.md",
            "\n".join(
                (
                    "# Engineering Platform",
                    "This repository is the authoring source of truth.",
                    "## Agent startup and release verification",
                    "Use the latest non-draft, non-prerelease GitHub release.",
                    "main develop pin v0.1.0",
                )
            )
            + "\n",
        )

        headings = (
            "Repository authority",
            "Instruction precedence",
            "Startup contract",
            "Branch and pull-request contract",
            "Implementation authority",
            "Human acceptance testing",
            "Compatibility and versioning",
            "Troubleshooting",
            "Definition of done",
        )
        agents = ["# Agents"]
        agents.extend(f"## {heading}" for heading in headings)
        agents.extend(
            (
                "Read `README.md` from `main` first.",
                "Verify the latest non-draft, non-prerelease release.",
            )
        )
        self._write("AGENTS.md", "\n".join(agents) + "\n")
        self._write("CHANGELOG.md", "# Changelog\n\n## [0.1.0]\n")
        self._write("docs/releases/v0.1.0.md", "# Engineering Platform v0.1.0\n")
        self._write(
            ".github/workflows/release.yml",
            "workflow_run\nPlatform CI\ncontents: write\ngh release create\n",
        )

    def assert_has_error(self, expected: str) -> None:
        errors = validator.validate(self.root)
        self.assertIn(expected, errors, msg=f"expected {expected!r} in {errors!r}")

    def test_valid_fixture_passes(self) -> None:
        self.assertEqual([], validator.validate(self.root))

    def test_missing_required_directory_is_reported(self) -> None:
        shutil.rmtree(self.root / "actions")
        self.assert_has_error("missing required directory: actions")

    def test_missing_required_file_is_reported(self) -> None:
        (self.root / "templates" / "README.md").unlink()
        self.assert_has_error("missing required file: templates/README.md")

    def test_empty_required_file_is_reported(self) -> None:
        self._write("docs/adoption.md", "")
        self.assert_has_error("required file is empty: docs/adoption.md")

    def test_invalid_semantic_version_is_reported(self) -> None:
        self._write("VERSION", "release-one\n")
        self.assert_has_error("VERSION is not semantic versioning: 'release-one'")

    def test_missing_readme_concept_is_reported(self) -> None:
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self._write("README.md", readme.replace("authoring source of truth", "shared source"))
        self.assert_has_error("README.md does not describe required concept: authoring source of truth")

    def test_missing_agents_heading_is_reported(self) -> None:
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self._write("AGENTS.md", agents.replace("## Definition of done", "## Completion"))
        self.assert_has_error("AGENTS.md is missing heading: Definition of done")

    def test_changelog_version_mismatch_is_reported(self) -> None:
        self._write("CHANGELOG.md", "# Changelog\n\n## [0.0.9]\n")
        self.assert_has_error("CHANGELOG.md is missing version entry: 0.1.0")

    def test_release_notes_heading_mismatch_is_reported(self) -> None:
        self._write("docs/releases/v0.1.0.md", "# Engineering Platform v0.0.9\n")
        self.assert_has_error("release notes heading does not match VERSION: v0.1.0")

    def test_release_workflow_requirement_is_reported(self) -> None:
        self._write(
            ".github/workflows/release.yml",
            "workflow_run\nPlatform CI\ncontents: write\nrelease command\n",
        )
        self.assert_has_error(
            ".github/workflows/release.yml does not describe required concept: gh release create"
        )


if __name__ == "__main__":
    unittest.main()
