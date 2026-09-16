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

    def _valid_agents(self) -> str:
        lines = ["# Agents", "This is a routing surface."]
        lines.extend(f"## {heading}" for heading in validator.AGENTS_REQUIRED_HEADINGS)
        lines.extend(validator.AGENTS_REQUIRED_POINTERS)
        return "\n".join(lines) + "\n"

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
        self._write("AGENTS.md", self._valid_agents())
        self._write("CHANGELOG.md", "# Changelog\n\n## [0.1.0]\n")
        self._write("docs/releases/v0.1.0.md", "# Engineering Platform v0.1.0\n")
        self._write(
            ".github/workflows/ci.yml",
            "\n".join(
                (
                    "fetch-depth: 0",
                    "validate-pr-policy.py",
                    "validate-protected-paths.py",
                    "run_fast_feedback.py --stage pre_commit",
                    "run_fast_feedback.py --stage completion_gate",
                )
            )
            + "\n",
        )
        self._write(
            ".githooks/pre-commit",
            "python scripts/run_fast_feedback.py --stage pre_commit\n",
        )
        self._write(
            "scripts/install-hooks.sh",
            "git config core.hooksPath .githooks\n",
        )
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

    def test_missing_agents_pointer_heading_is_reported(self) -> None:
        agents = self._valid_agents().replace("## Authoritative pointers", "## Links")
        self._write("AGENTS.md", agents)
        self.assert_has_error("AGENTS.md is missing pointer heading: Authoritative pointers")

    def test_agents_entrypoint_has_line_budget(self) -> None:
        agents = self._valid_agents() + ("extra detail\n" * validator.AGENTS_MAX_LINES)
        self._write("AGENTS.md", agents)
        errors = validator.validate(self.root)
        self.assertTrue(
            any("concise pointer surface" in error for error in errors),
            errors,
        )

    def test_agents_rejects_detailed_operating_heading(self) -> None:
        self._write("AGENTS.md", self._valid_agents() + "## Troubleshooting\nDetailed procedure\n")
        self.assert_has_error(
            "AGENTS.md duplicates detailed operating guidance instead of pointing to its authority: Troubleshooting"
        )

    def test_agents_requires_authoritative_pointer(self) -> None:
        agents = self._valid_agents().replace("`engineering-policy.json`\n", "")
        self._write("AGENTS.md", agents)
        self.assert_has_error("AGENTS.md is missing authoritative pointer: `engineering-policy.json`")

    def test_changelog_version_mismatch_is_reported(self) -> None:
        self._write("CHANGELOG.md", "# Changelog\n\n## [0.0.9]\n")
        self.assert_has_error("CHANGELOG.md is missing version entry: 0.1.0")

    def test_release_notes_heading_mismatch_is_reported(self) -> None:
        self._write("docs/releases/v0.1.0.md", "# Engineering Platform v0.0.9\n")
        self.assert_has_error("release notes heading does not match VERSION: v0.1.0")

    def test_ci_workflow_requires_pr_policy(self) -> None:
        ci = (self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self._write(".github/workflows/ci.yml", ci.replace("validate-pr-policy.py\n", ""))
        self.assert_has_error(
            ".github/workflows/ci.yml does not describe required concept: validate-pr-policy.py"
        )

    def test_ci_workflow_requires_protected_path_enforcement(self) -> None:
        ci = (self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self._write(".github/workflows/ci.yml", ci.replace("validate-protected-paths.py\n", ""))
        self.assert_has_error(
            ".github/workflows/ci.yml does not describe required concept: validate-protected-paths.py"
        )

    def test_ci_workflow_requires_completion_gate(self) -> None:
        ci = (self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self._write(
            ".github/workflows/ci.yml",
            ci.replace("run_fast_feedback.py --stage completion_gate\n", ""),
        )
        self.assert_has_error(
            ".github/workflows/ci.yml does not describe required concept: run_fast_feedback.py --stage completion_gate"
        )

    def test_pre_commit_hook_requirement_is_reported(self) -> None:
        self._write(".githooks/pre-commit", "echo bypass\n")
        self.assert_has_error(
            ".githooks/pre-commit does not describe required concept: run_fast_feedback.py"
        )

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
