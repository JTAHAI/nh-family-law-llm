from __future__ import annotations

import json
import importlib.util
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
        # The nested evidence runner has its own 90-second fail-closed bound.
        # The outer acceptance deadline must exceed that contract plus process
        # startup and receipt serialization overhead.
        timeout=120,
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
    assert payload["test_timed_out"] is False


def test_pass32_38_runner_turns_nested_timeout_into_blocked_receipt(
    tmp_path: Path, monkeypatch,
) -> None:
    script = ROOT / "scripts" / "run-pass32-38-engineering-evidence.py"
    spec = importlib.util.spec_from_file_location("pass32_38_timeout_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0],
            kwargs.get("timeout", 90),
            output="bounded synthetic stdout",
            stderr="bounded synthetic stderr",
        )

    monkeypatch.setattr(module.subprocess, "run", timed_out)
    report = module.build_report(timeout_seconds=5, work_root=tmp_path / "owned")

    assert report["status"] == "blocked"
    assert report["passes_closed"] == []
    assert report["test_timed_out"] is True
    assert report["test_exit_code"] is None
    assert report["true_ga_release_allowed"] is False
    assert report["test_stdout_tail"] == "bounded synthetic stdout"
    assert report["test_stderr_tail"] == "bounded synthetic stderr"


def test_engineering_closure_rows_do_not_mark_true_ga_passes_complete() -> None:
    tracker = json.loads((ROOT / "configs" / "nh_true_ga_pass_tracker.json").read_text(encoding="utf-8"))
    completed = tracker["current_true_ga_completed_passes"]
    assert completed == []
    rows = {row["pass"]: row for row in tracker["passes"]}
    # Engineering work remains recorded, but cannot stand in for true-GA
    # legal, pilot, currentness, or external-release evidence.
    assert all(rows[pass_number]["status"] == "complete" for pass_number in range(32, 39))
    assert rows[19]["next"] is True
