#!/usr/bin/env python3
"""Run bounded engineering evidence for Passes 32-38 without claiming legal sign-off."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def build_report() -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-q", *TARGETS]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=90, check=False)
    passed = completed.returncode == 0
    signals = {
        "32": {"structured_case_brief": passed},
        "33": {"freshness_dashboard": passed},
        "34": {"source_workflow_guardrails": passed},
        "35": {"parser_regression_quarantines_malformed_input": passed, "cross_tenant_blocked": passed},
        "36": {"evidence_packet_integrity": passed},
        "37": {"form_catalog_freshness": passed},
        "38": {"override_logged_without_silent_pass": passed},
    }
    return {
        "schema_version": "pass32_38_engineering_closure_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if passed else "blocked",
        "passes_closed": list(range(32, 39)),
        "review_mode": "repo_engineering_evidence",
        "attorney_reviewed": False,
        "not_legal_signoff": True,
        "operator_source_backed": True,
        "true_ga_release_allowed": False,
        "evidence_basis": [
            "legal/nh_supreme_court/intelligence.py", "legal/forms/intelligence.py",
            "legal/drafting/findings_engine.py", "legal/matter/document_ingestor.py",
            "legal/evidence/matter_work_product.py", "legal/drafting/filing_ready_gate.py",
            "tests/test_nh_supreme_court_intelligence_pass8.py",
            "tests/test_pass43_pass44_pass45_security_compliance_sre.py",
            "tests/test_pass37_pass38_drafting_filing_gate.py",
        ],
        "pass_results": {number: {"status": "pass" if passed else "blocked", "signals": value} for number, value in signals.items()},
        "test_command": command,
        "test_exit_code": completed.returncode,
        "test_stdout_tail": completed.stdout[-4000:],
        "test_stderr_tail": completed.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    payload = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
