#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from context_agent import ContextAgentError, render_demo, run_context_agent, to_yaml

DEFAULT_MANIFEST_PATH = "ai/project-context.json"
DEFAULT_PRODUCT_SPEC = "ai/project/product.md"
DEFAULT_ARCHITECTURE_SPEC = "ai/project/architecture.md"
DEFAULT_FEATURE_SPECS_DIR = "ai/specs"
AUTHORITATIVE_STATUSES = {"authoritative", "accepted", "active", "approved"}

SPEC_SECTION_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "product": (
        ("objective", "purpose"),
        ("scope", "non-goals"),
        ("constraints",),
        ("provenance", "sources"),
    ),
    "architecture": (
        ("architecture", "components"),
        ("constraints",),
        ("validation",),
        ("provenance", "sources"),
    ),
    "feature": (
        ("outcome", "goal"),
        ("requirements", "scope"),
        ("acceptance criteria", "acceptance"),
        ("human gates", "human gate"),
        ("provenance", "sources"),
    ),
}


class RepositoryContextError(ContextAgentError):
    """Raised when repository-aware context cannot be inspected safely."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RepositoryContextError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RepositoryContextError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RepositoryContextError(f"top-level JSON must be an object: {path}")
    return data


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise RepositoryContextError("repository paths must be non-empty strings")
    root = root.resolve()
    path = (root / relative.strip()).resolve()
    if path != root and root not in path.parents:
        raise RepositoryContextError(f"repository path escapes root: {relative}")
    return path


def _validate_repository_request(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RepositoryContextError("input.repository must be an object")
    for key in ("provider", "identifier", "ref"):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RepositoryContextError(f"input.repository.{key} must be non-empty")
    manifest_path = raw.get("manifest_path", DEFAULT_MANIFEST_PATH)
    if not isinstance(manifest_path, str) or not manifest_path.strip():
        raise RepositoryContextError("input.repository.manifest_path must be non-empty")
    feature_spec = raw.get("feature_spec")
    if feature_spec is not None and (not isinstance(feature_spec, str) or not feature_spec.strip()):
        raise RepositoryContextError("input.repository.feature_spec must be null or non-empty")
    bootstrap = raw.get("bootstrap", {})
    if not isinstance(bootstrap, dict):
        raise RepositoryContextError("input.repository.bootstrap must be an object")
    allowed = bootstrap.get("allowed", False)
    if not isinstance(allowed, bool):
        raise RepositoryContextError("input.repository.bootstrap.allowed must be boolean")
    return {
        "provider": raw["provider"].strip(),
        "identifier": raw["identifier"].strip(),
        "ref": raw["ref"].strip(),
        "manifest_path": manifest_path.strip(),
        "feature_spec": feature_spec.strip() if isinstance(feature_spec, str) else None,
        "bootstrap": {"allowed": allowed},
    }


def _validate_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema_version") != "repository-context/v1":
        raise RepositoryContextError(
            "repository context manifest schema_version must be 'repository-context/v1'"
        )
    specs = raw.get("specs")
    if not isinstance(specs, dict):
        raise RepositoryContextError("repository context manifest specs must be an object")
    normalized_specs: dict[str, dict[str, Any]] = {}
    for kind in ("product", "architecture"):
        entry = specs.get(kind)
        if not isinstance(entry, dict):
            raise RepositoryContextError(f"repository context manifest specs.{kind} must be an object")
        path = entry.get("path")
        if not isinstance(path, str) or not path.strip():
            raise RepositoryContextError(
                f"repository context manifest specs.{kind}.path must be non-empty"
            )
        required = entry.get("required", True)
        if not isinstance(required, bool):
            raise RepositoryContextError(
                f"repository context manifest specs.{kind}.required must be boolean"
            )
        normalized_specs[kind] = {"path": path.strip(), "required": required}

    feature_specs = raw.get("feature_specs", {})
    if not isinstance(feature_specs, dict):
        raise RepositoryContextError("repository context manifest feature_specs must be an object")
    directory = feature_specs.get("directory", DEFAULT_FEATURE_SPECS_DIR)
    if not isinstance(directory, str) or not directory.strip():
        raise RepositoryContextError("repository context manifest feature_specs.directory must be non-empty")
    required_for_feature_work = feature_specs.get("required_for_feature_work", True)
    if not isinstance(required_for_feature_work, bool):
        raise RepositoryContextError(
            "repository context manifest feature_specs.required_for_feature_work must be boolean"
        )
    return {
        "schema_version": "repository-context/v1",
        "specs": normalized_specs,
        "feature_specs": {
            "directory": directory.strip().rstrip("/"),
            "required_for_feature_work": required_for_feature_work,
        },
    }


def _headings(text: str) -> set[str]:
    headings: set[str] = set()
    for match in re.finditer(r"^#{2,6}\s+(.+?)\s*$", text, re.MULTILINE):
        headings.add(match.group(1).strip().lower())
    return headings


def _declared_status(text: str) -> str:
    match = re.search(r"^Status:\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return "unspecified"
    return match.group(1).strip()


def _missing_sections(kind: str, text: str) -> list[str]:
    headings = _headings(text)
    missing: list[str] = []
    for alternatives in SPEC_SECTION_REQUIREMENTS[kind]:
        if not any(candidate in headings for candidate in alternatives):
            missing.append(" or ".join(alternatives))
    return missing


def _inspect_spec(root: Path, *, kind: str, relative: str, required: bool) -> dict[str, Any]:
    path = _safe_path(root, relative)
    if not path.is_file():
        return {
            "kind": kind,
            "path": relative,
            "required": required,
            "status": "missing",
            "declared_status": None,
            "missing_sections": [],
        }
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {
            "kind": kind,
            "path": relative,
            "required": required,
            "status": "invalid",
            "declared_status": None,
            "missing_sections": ["non-empty content"],
        }
    declared = _declared_status(text)
    missing = _missing_sections(kind, text)
    status_key = declared.lower()
    if "draft" in status_key or "synth" in status_key:
        status = "draft"
    elif status_key not in AUTHORITATIVE_STATUSES:
        status = "invalid"
    elif missing:
        status = "invalid"
    else:
        status = "ready"
    return {
        "kind": kind,
        "path": relative,
        "required": required,
        "status": status,
        "declared_status": declared,
        "missing_sections": missing,
    }


def _context_lines(normalized_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in sorted(normalized_context):
        value = normalized_context[key]
        if isinstance(value, (str, int, float, bool)):
            rendered = str(value).replace("\n", " ").strip()
        elif isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
        else:
            continue
        if len(rendered) > 240:
            rendered = rendered[:237].rstrip() + "..."
        lines.append(f"- `{key}`: {rendered}")
    return lines or ["- No additional normalized context was available; human review is required."]


def _draft_product(goal: str, normalized_context: dict[str, Any]) -> str:
    context = "\n".join(_context_lines(normalized_context))
    return f"""# Product Specification\n\nStatus: DRAFT - SYNTHESIZED\n\n## Objective\n\n{goal}\n\n## Scope\n\n- Drafted only from supplied context. Confirm product scope before marking authoritative.\n\n## Non-goals\n\n- No non-goals are inferred automatically. Add explicit exclusions during review.\n\n## Constraints\n\n{context}\n\n## Provenance\n\n- Synthesized by the Engineering Platform Context remediation path from the active human goal and normalized repository-linked context.\n- This draft is not authoritative until reviewed and changed to `Status: authoritative`.\n"""


def _draft_architecture(normalized_context: dict[str, Any]) -> str:
    context = "\n".join(_context_lines(normalized_context))
    return f"""# Architecture Specification\n\nStatus: DRAFT - SYNTHESIZED\n\n## Architecture\n\n- TODO: describe the current repository architecture using verified repository evidence.\n\n## Constraints\n\n{context}\n\n## Validation\n\n- Reconcile this draft with the existing code, tests, ADRs, and repository-local steering before marking authoritative.\n\n## Provenance\n\n- Synthesized by the Engineering Platform Context remediation path.\n- No architecture not present in repository evidence should be promoted to authoritative truth.\n"""


def _draft_feature(goal: str, normalized_context: dict[str, Any]) -> str:
    context = "\n".join(_context_lines(normalized_context))
    return f"""# Feature Specification\n\nStatus: DRAFT - SYNTHESIZED\n\n## Outcome\n\n{goal}\n\n## Requirements\n\n{context}\n\n## Acceptance criteria\n\n- TODO: convert the accepted human goal and repository evidence into deterministic acceptance criteria.\n\n## Human gates\n\n- Human review is required before this synthesized draft can become authoritative.\n\n## Provenance\n\n- Synthesized by the Engineering Platform Context remediation path from supplied context and repository linkage.\n- Unstated product decisions are intentionally left unresolved.\n"""


def _default_manifest(feature_spec: str | None) -> dict[str, Any]:
    return {
        "schema_version": "repository-context/v1",
        "specs": {
            "product": {"path": DEFAULT_PRODUCT_SPEC, "required": True},
            "architecture": {"path": DEFAULT_ARCHITECTURE_SPEC, "required": True},
        },
        "feature_specs": {
            "directory": DEFAULT_FEATURE_SPECS_DIR,
            "required_for_feature_work": feature_spec is not None,
        },
    }


def _draft_entry(path: str, content: str, kind: str) -> dict[str, str]:
    return {"path": path, "kind": kind, "content": content}


def inspect_repository_context(
    repository_root: Path,
    repository_request: dict[str, Any],
    *,
    goal: str,
    normalized_context: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    root = repository_root.resolve()
    if not root.is_dir():
        raise RepositoryContextError(f"repository root is not a directory: {repository_root}")
    request = _validate_repository_request(repository_request)
    manifest_path = _safe_path(root, request["manifest_path"])
    drafts: list[dict[str, str]] = []
    questions: list[dict[str, str]] = []

    manifest_status = "ready"
    try:
        manifest = _validate_manifest(_load_json(manifest_path))
    except RepositoryContextError as exc:
        if not manifest_path.exists():
            manifest_status = "missing"
            manifest = _default_manifest(request["feature_spec"])
            if request["bootstrap"]["allowed"]:
                drafts.append(
                    _draft_entry(
                        request["manifest_path"],
                        json.dumps(manifest, indent=2) + "\n",
                        "repository_manifest",
                    )
                )
        else:
            manifest_status = "invalid"
            manifest = _default_manifest(request["feature_spec"])
        questions.append(
            {
                "key": "repository_manifest",
                "question": f"Review repository context manifest {request['manifest_path']}: {exc}",
            }
        )

    specs: list[dict[str, Any]] = []
    for kind in ("product", "architecture"):
        spec = manifest["specs"][kind]
        result = _inspect_spec(root, kind=kind, relative=spec["path"], required=spec["required"])
        specs.append(result)
        if result["status"] == "missing" and result["required"] and request["bootstrap"]["allowed"]:
            content = (
                _draft_product(goal, normalized_context)
                if kind == "product"
                else _draft_architecture(normalized_context)
            )
            drafts.append(_draft_entry(result["path"], content, kind))

    feature_required = manifest["feature_specs"]["required_for_feature_work"]
    feature_spec = request["feature_spec"]
    if feature_required and feature_spec is None:
        specs.append(
            {
                "kind": "feature",
                "path": None,
                "required": True,
                "status": "missing",
                "declared_status": None,
                "missing_sections": ["feature spec reference"],
            }
        )
        questions.append(
            {
                "key": "feature_spec",
                "question": "Provide input.repository.feature_spec for feature work before orchestration.",
            }
        )
    elif feature_spec is not None:
        feature_dir = manifest["feature_specs"]["directory"]
        normalized_feature = feature_spec.strip().lstrip("./")
        normalized_dir = feature_dir.strip().lstrip("./").rstrip("/")
        if normalized_dir and not (
            normalized_feature == normalized_dir or normalized_feature.startswith(normalized_dir + "/")
        ):
            raise RepositoryContextError(
                f"feature spec {feature_spec!r} is outside declared feature_specs.directory {feature_dir!r}"
            )
        result = _inspect_spec(
            root,
            kind="feature",
            relative=feature_spec,
            required=feature_required,
        )
        specs.append(result)
        if result["status"] == "missing" and feature_required and request["bootstrap"]["allowed"]:
            drafts.append(_draft_entry(feature_spec, _draft_feature(goal, normalized_context), "feature"))

    blocking_specs = [
        item
        for item in specs
        if item["required"] and item["status"] in {"missing", "invalid", "draft"}
    ]
    missing = [item["kind"] for item in blocking_specs if item["status"] == "missing"]
    invalid = [item["kind"] for item in blocking_specs if item["status"] == "invalid"]
    draft_kinds = [item["kind"] for item in blocking_specs if item["status"] == "draft"]
    ready = manifest_status == "ready" and not blocking_specs

    for item in blocking_specs:
        if item["status"] == "draft":
            questions.append(
                {
                    "key": f"{item['kind']}_spec",
                    "question": f"Review draft spec {item['path']} and mark it authoritative only after its contents are accepted.",
                }
            )
        elif item["status"] == "invalid":
            detail = ", ".join(item["missing_sections"]) or "authoritative status"
            questions.append(
                {
                    "key": f"{item['kind']}_spec",
                    "question": f"Repair {item['path']} so it satisfies repository spec requirements: {detail}.",
                }
            )

    if ready:
        action = "none"
    elif drafts:
        action = "review_and_apply_generated_drafts"
    elif feature_required and feature_spec is None:
        action = "provide_feature_spec_reference"
    else:
        action = "complete_repository_specs"

    inspection = {
        "repository": {
            "provider": request["provider"],
            "identifier": request["identifier"],
            "ref": request["ref"],
        },
        "manifest": {
            "path": request["manifest_path"],
            "status": manifest_status,
            "schema_version": manifest.get("schema_version"),
        },
        "specs": specs,
        "spec_readiness": {
            "ready": ready,
            "missing": missing,
            "invalid": invalid,
            "draft": draft_kinds,
        },
        "remediation": {
            "required": not ready,
            "action": action,
            "draft_artifacts": [item["path"] for item in drafts],
            "assumptions": [
                "Generated drafts are non-authoritative run artifacts.",
                "Repository product truth must be reviewed before a draft is marked authoritative.",
            ] if drafts else [],
        },
        "questions_for_human": questions,
    }
    return inspection, drafts


def run_repository_aware_context(
    contract: dict[str, Any],
    payload: dict[str, Any],
    *,
    repository_root: Path | None = None,
    tier: str = "basic",
    autonomy: str = "advisory",
    mode: str = "demo",
    run_id: str | None = None,
    created_at: str | None = None,
    output_name: str = "context.yaml",
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    manifest, report = run_context_agent(
        contract,
        payload,
        tier=tier,
        autonomy=autonomy,
        mode=mode,
        run_id=run_id,
        created_at=created_at,
        output_name=output_name,
    )
    repository_request = payload.get("repository")
    if repository_request is None:
        return manifest, report, []
    if repository_root is None:
        raise RepositoryContextError(
            "repository-aware context requires repository_root or a host adapter that supplies equivalent evidence"
        )

    inspection, drafts = inspect_repository_context(
        repository_root,
        repository_request,
        goal=manifest["goal"],
        normalized_context=manifest["normalized_context"],
    )
    manifest["repository_context"] = inspection
    repository_ready = inspection["spec_readiness"]["ready"]
    manifest["readiness"]["repository_specs_ready"] = repository_ready

    capabilities = manifest["capabilities"]
    for name in ("inspect_repository_context", "evaluate_spec_readiness"):
        if name not in capabilities["used"]:
            capabilities["used"].append(name)
    if drafts and "draft_spec_remediation" not in capabilities["used"]:
        capabilities["used"].append("draft_spec_remediation")

    if not repository_ready:
        if "repository_specs" not in manifest["readiness"]["missing_required"]:
            manifest["readiness"]["missing_required"].append("repository_specs")
        manifest["readiness"]["ready_for_orchestration"] = False
        manifest["handoff"]["allowed"] = False
        existing_questions = {(q.get("key"), q.get("question")) for q in manifest["questions_for_human"]}
        for question in inspection["questions_for_human"]:
            marker = (question.get("key"), question.get("question"))
            if marker not in existing_questions:
                manifest["questions_for_human"].append(question)
                existing_questions.add(marker)

    report["capabilities"] = manifest["capabilities"]
    report["handoff"] = manifest["handoff"]
    report["status"] = (
        "complete" if manifest["readiness"]["ready_for_orchestration"] else "needs_context"
    )
    report["decisions"].append(
        {
            "decision": "repository_specs_ready" if repository_ready else "repository_specs_not_ready",
            "reason": (
                "Repository-local authoritative specs satisfy the declared repository context contract."
                if repository_ready
                else "Repository-linked context is missing, invalid, or still draft; orchestration remains blocked."
            ),
        }
    )
    report["metrics"].update(
        {
            "repository_specs_ready": repository_ready,
            "repository_spec_count": len(inspection["specs"]),
            "generated_draft_count": len(drafts),
        }
    )
    report["repository_context"] = inspection
    return manifest, report, drafts


def _write_drafts(output_dir: Path, drafts: list[dict[str, str]]) -> list[str]:
    written: list[str] = []
    for draft in drafts:
        relative = draft["path"]
        target = _safe_path(output_dir, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(draft["content"], encoding="utf-8")
        written.append(str(target))
    return written


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run repository-aware Engineering Platform Basic Context preparation"
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("context.yaml"))
    parser.add_argument("--run-report", type=Path, default=Path("context-run.json"))
    parser.add_argument("--draft-output-dir", type=Path, default=Path("repository-context-drafts"))
    parser.add_argument("--tier", default="basic")
    parser.add_argument("--autonomy", default="advisory")
    parser.add_argument("--mode", default="demo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        contract = _load_json(args.contract)
        payload = _load_json(args.input)
        manifest, report, drafts = run_repository_aware_context(
            contract,
            payload,
            repository_root=args.repository_root,
            tier=args.tier,
            autonomy=args.autonomy,
            mode=args.mode,
            output_name=args.output.name,
        )
        written = _write_drafts(args.draft_output_dir, drafts) if drafts else []
    except (ContextAgentError, RepositoryContextError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.run_report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(to_yaml(manifest) + "\n", encoding="utf-8")
    if written:
        report["outputs"].extend(written)
    args.run_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.mode == "demo":
        print(render_demo(report))
        if "repository_context" in report:
            repo = report["repository_context"]
            print("")
            print("REPOSITORY CONTEXT")
            print(f"Repository: {repo['repository']['identifier']} @ {repo['repository']['ref']}")
            print(f"Specs ready: {'YES' if repo['spec_readiness']['ready'] else 'NO'}")
            print(f"Remediation: {repo['remediation']['action']}")
    else:
        print(
            f"Repository-aware Context completed: status={report['status']} "
            f"handoff_allowed={report['handoff']['allowed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
