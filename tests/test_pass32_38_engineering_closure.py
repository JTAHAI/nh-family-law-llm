from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pass32_38_engineering_evidence_runner_closes_repo_gates(tmp_path: Path) -> None:
    output = tmp_path / "pass32_38_engineering_evidence.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-pass32-38-engineering-evidence.py"),
            "--output",
            str(output),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["passes_closed"] == [32, 33, 34, 35, 36, 37, 38]
    assert payload["attorney_reviewed"] is False
    assert payload["not_legal_signoff"] is True
    assert payload["pass_results"]["32"]["signals"]["structured_case_brief"] is True
    assert payload["pass_results"]["35"]["signals"]["cross_tenant_blocked"] is True
    assert payload["pass_results"]["38"]["signals"]["override_logged_without_silent_pass"] is True


def test_engineering_closure_rows_do_not_mark_true_ga_passes_complete() -> None:
    tracker = json.loads((ROOT / "configs" / "nh_true_ga_pass_tracker.json").read_text(encoding="utf-8"))
    completed = tracker["current_true_ga_completed_passes"]
    assert completed == []
    rows = {row["pass"]: row for row in tracker["passes"]}
    # Engineering work remains recorded, but cannot stand in for true-GA
    # legal, pilot, currentness, or external-release evidence.
    assert all(rows[pass_number]["status"] == "complete" for pass_number in range(32, 39))
    assert rows[19]["next"] is True
