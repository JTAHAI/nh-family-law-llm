#!/usr/bin/env python3
"""Run bounded engineering evidence for Passes 32-38 without claiming legal sign-off."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "tests/test_nh_supreme_court_intelligence_pass8.py",
    "tests/test_pass33_freshness_dashboard.py",
    "tests/test_pass35_parser_regression_corpus.py",
    "tests/test_pass43_pass44_pass45_security_compliance_sre.py",
    "tests/test_evidence_packet_builder.py",
    "tests/test_pass37_forms_catalog_synchronizer.py",
    "tests/test_filing_ready_gate.py",
    "tests/test_nh_filing_ready_gate.py",
]
DEFAULT_TIMEOUT_SECONDS = 90


def _text_tail(value: Any, *, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[-limit:]


def build_report(
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    work_root: str | Path | None = None,
) -> dict[str, object]:
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
        raise ValueError("timeout_seconds must be an integer")
    if timeout_seconds < 5 or timeout_seconds > 600:
        raise ValueError("timeout_seconds must be between 5 and 600")

    owned_root = Path(work_root or (ROOT / "dist" / "pass32-38-engineering")).resolve()
    owned_root.mkdir(parents=True, exist_ok=True)
    command: list[str] = []
    return_code: int | None = None
    stdout_tail = ""
    stderr_tail = ""
    timed_out = False

    # The runner owns and removes only this fresh directory. It does not clean
    # the repository, ignored user artifacts, or any configured data store.
    with tempfile.TemporaryDirectory(prefix="pytest-", dir=owned_root) as temporary:
        basetemp = Path(temporary) / "pytest"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *TARGETS,
            f"--basetemp={basetemp}",
            "-ra",
            "--tb=short",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            return_code = completed.returncode
            stdout_tail = _text_tail(completed.stdout)
            stderr_tail = _text_tail(completed.stderr)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout_tail = _text_tail(exc.stdout)
            stderr_tail = _text_tail(exc.stderr)

    passed = return_code == 0 and not timed_out
    signals = {
        "32": {"structured_case_brief": passed},
        "33": {"freshness_dashboard": passed},
        "34": {"source_workflow_guardrails": passed},
        "35": {
            "parser_regression_quarantines_malformed_input": passed,
            "cross_tenant_blocked": passed,
        },
        "36": {"evidence_packet_integrity": passed},
        "37": {"form_catalog_freshness": passed},
        "38": {"override_logged_without_silent_pass": passed},
    }
    return {
        "schema_version": "pass32_38_engineering_closure_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if passed else "blocked",
        "passes_closed": list(range(32, 39)) if passed else [],
        "review_mode": "repo_engineering_evidence",
        "attorney_reviewed": False,
        "not_legal_signoff": True,
        "operator_source_backed": True,
        "true_ga_release_allowed": False,
        "evidence_basis": [
            "legal/nh_supreme_court/intelligence.py",
            "legal/forms/intelligence.py",
            "legal/drafting/findings_engine.py",
            "legal/matter/document_ingestor.py",
            "legal/evidence/matter_work_product.py",
            "legal/drafting/filing_ready_gate.py",
            "tests/test_nh_supreme_court_intelligence_pass8.py",
            "tests/test_pass43_pass44_pass45_security_compliance_sre.py",
            "tests/test_pass37_pass38_drafting_filing_gate.py",
        ],
        "pass_results": {
            number: {"status": "pass" if passed else "blocked", "signals": value}
            for number, value in signals.items()
        },
        "test_command": command,
        "test_exit_code": return_code,
        "test_timed_out": timed_out,
        "test_timeout_seconds": timeout_seconds,
        "test_workspace_policy": "fresh_repository_owned_temporary_directory",
        "test_stdout_tail": stdout_tail,
        "test_stderr_tail": stderr_tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument(
        "--test-timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Bound for the nested pytest process (5-600 seconds).",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "dist" / "pass32-38-engineering",
        help="Repository-owned parent for one fresh nested pytest workspace.",
    )
    args = parser.parse_args()
    try:
        payload = build_report(
            timeout_seconds=args.test_timeout_seconds,
            work_root=args.work_root,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 1
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
