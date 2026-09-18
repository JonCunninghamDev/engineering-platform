import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "demo_full_basic_pipeline.py"


def test_full_basic_pipeline_is_deterministic_and_zero_execution(tmp_path):
    out = tmp_path / "demo"
    result = subprocess.run([sys.executable, str(SCRIPT), "--output-dir", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "run-summary.json").read_text())
    assert summary["status"] == "verified"
    assert summary["stages"] == ["context", "orchestrator", "builder_assignment", "builder", "verifier"]
    assert summary["boundaries"]["repository_writes"] == 0
    assert summary["boundaries"]["candidate_code_executions"] == 0
    assert summary["boundaries"]["orchestrator_dispatches"] == 0
    assert json.loads((out / "verification-report.json").read_text())["status"] == "verified"
    assert json.loads((out / "change-set.json").read_text())["summary"]["actual_write_count"] == 0
    run = json.loads((out / "engineering-run.json").read_text())
    assert run["schema_version"] == "engineering-run/v1"
    assert run["safety"]["safe"] is True
    assert run["reliability"]["first_pass_verification"] is True
    assert run["derived_metrics"]["intent_to_verified_ms"] == 6000
    assert run["autonomy"]["human_interventions"] == 1


def test_full_basic_pipeline_fails_closed_on_corrupted_handoff(tmp_path):
    out = tmp_path / "corrupt"
    result = subprocess.run([sys.executable, str(SCRIPT), "--output-dir", str(out), "--corrupt-handoff"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2
    assert "does not match execution plan" in result.stderr
    assert not (out / "run-summary.json").exists()
