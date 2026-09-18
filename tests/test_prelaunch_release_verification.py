from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_prelaunch_release_verifier_fails_closed_and_writes_a_machine_readable_receipt(tmp_path: Path) -> None:
    output = tmp_path / "release-readiness.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify-prelaunch-release.py"), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["overall_status"] == "NOT_READY"
    assert payload["revision"].endswith("-dirty")
    assert {gate["gate"] for gate in payload["gates"]} == {
        "engineering_correctness", "authority_acquisition_and_integrity", "authority_currentness_and_coverage",
        "independent_legal_review", "privacy_security_ai_behavior", "installed_windows_accessibility",
        "store_submission_preparation", "microsoft_certification_publication",
    }
    assert json.loads(output.read_text(encoding="utf-8"))["blockers"] == payload["blockers"]
