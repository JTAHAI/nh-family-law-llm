from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_tracker import GAPassTracker

ROOT = Path(__file__).resolve().parents[1]


def test_true_ga_pass_tracker_refuses_unverified_ga_completion_claims() -> None:
    report = GAPassTracker(project_root=ROOT).report().as_dict()
    assert report["status"] == "blocked"
    assert report["total_true_ga_passes"] == 33
    assert report["true_ga_completed"] == 0
    assert report["true_ga_remaining"] == 33
    assert report["completed_passes"] == []
    assert report["remaining_passes"][0] == 19
    assert report["remaining_passes"][-1] == 51
    assert report["next_true_ga_pass"] == 19
    assert "configured exit evidence" in report["counting_rule"]
    assert any(item.startswith("completed_passes_status_mismatch:") for item in report["warnings"])


def test_tracker_config_marks_only_repo_evidence_backed_passes_complete() -> None:
    payload = json.loads((ROOT / "configs" / "nh_true_ga_pass_tracker.json").read_text(encoding="utf-8"))
    assert payload["current_true_ga_completed_passes"] == []
    complete = [row["pass"] for row in payload["passes"] if row["status"] == "complete"]
    assert complete
    # Historical planning row statuses cannot override the audited completion
    # list. Their discrepancy is surfaced as an explicit release blocker.


def test_report_ga_pass_count_script_summary() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "report-ga-pass-count.py"), "--summary"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 1, completed.stderr
    assert "true_ga_remaining=33" in completed.stdout
    assert "true_ga_completed=0" in completed.stdout
    assert "next_pass=19" in completed.stdout
    assert "internal_conversation_pilot_readiness=missing" in completed.stdout


def test_report_ga_pass_count_script_json_includes_internal_conversation_status_without_changing_true_ga_counts() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "report-ga-pass-count.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 1, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["true_ga_remaining"] == 33
    assert payload["next_true_ga_pass"] == 19
    assert payload["internal_conversation_pilot_readiness"]["status"] == "missing"
    assert payload["internal_conversation_pilot_readiness"]["does_not_reduce_true_ga_count"] is True
