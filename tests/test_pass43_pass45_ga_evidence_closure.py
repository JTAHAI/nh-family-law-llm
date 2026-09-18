from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_evidence import GAPassEvidenceAuditor
from legal.production.ga_pass_tracker import GAPassTracker

ROOT = Path(__file__).resolve().parents[1]


def test_pass43_pass45_split_reports_are_generated_and_counted(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-security-compliance-sre-evidence.py"),
            str(tmp_path / "sample.json"),
            "--ga-output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    for name in (
        "enterprise-security-test-report.json",
        "governance-compliance-packet-report.json",
        "sre-reliability-report.json",
    ):
        payload = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert payload["status"] == "pass", payload


def test_ga_tracker_does_not_count_pass43_44_45_without_external_true_ga_evidence():
    report = GAPassTracker(project_root=ROOT).report().as_dict()
    assert not {43, 44, 45}.intersection(report["completed_passes"])
    assert report["true_ga_completed"] == 0
    assert report["true_ga_remaining"] == 33
    assert report["next_true_ga_pass"] == 19


def test_ga_evidence_audit_keeps_repo_pass43_44_45_reports_out_of_true_ga_count():
    report = GAPassEvidenceAuditor(project_root=ROOT).run().as_dict()
    assert report["status"] == "blocked", report
    assert report["audited_completed_passes"] == []
    assert report["true_ga_remaining"] == 33
