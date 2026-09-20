#!/usr/bin/env python3
"""Emit the evidence-based prelaunch status without promoting any authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    revision = completed.stdout.strip() if completed.returncode == 0 else "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return f"{revision}-dirty" if dirty.stdout.strip() else revision


def _resolve_candidate(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("candidate package must be inside the repository") from exc
    return candidate


def _report_path(path: Path) -> str:
    """Render repository-relative paths when possible, without hiding test paths."""

    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _candidate_evidence(package: Path) -> dict[str, Any]:
    """Bind build and WACK receipts to exactly the selected MSIX.

    A release report must not inherit a passing build summary or WACK receipt
    from an earlier package with the same version.  Missing or malformed
    receipts remain explicit blockers; this function never promotes a package.
    """

    package_hash = _sha256(package)
    candidate_root = package.parent.parent
    summary_path = candidate_root / "evidence" / "test-summary.txt"
    wack_path = candidate_root / "evidence" / "wack" / "wack-result.json"
    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    summary_hash = _sha256(summary_path)
    summary_passed = (
        package_hash is not None
        and "MSIX build: PASS" in summary_text
        and f"Package SHA-256: {package_hash}" in summary_text
    )
    wack: dict[str, Any] = {}
    wack_parse_error = ""
    if wack_path.is_file():
        try:
            parsed = json.loads(wack_path.read_text(encoding="utf-8"))
            wack = parsed if isinstance(parsed, dict) else {}
            if not wack:
                wack_parse_error = "wack_receipt_not_object"
        except json.JSONDecodeError:
            wack_parse_error = "wack_receipt_invalid_json"
    else:
        wack_parse_error = "wack_receipt_missing"
    wack_hash = str((wack.get("package") or {}).get("sha256") or "").lower()
    return {
        "candidate_root": _report_path(candidate_root),
        "build_summary": {
            "path": _report_path(summary_path),
            "sha256": summary_hash,
            "status": "pass" if summary_passed else "blocked",
            "reason": "hash_bound_build_summary" if summary_passed else "missing_or_unbound_build_summary",
        },
        "wack": {
            "path": _report_path(wack_path),
            "sha256": _sha256(wack_path),
            "status": str(wack.get("status") or "blocked"),
            "execution_status": str(wack.get("execution_status") or "not_run"),
            "hash_matches_candidate": bool(package_hash and package_hash == wack_hash),
            "parse_error": wack_parse_error,
        },
    }


def build_report(*, package: Path) -> dict[str, Any]:
    ledger_path = ROOT / "docs" / "release" / "RELEASE_BLOCKERS.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    package_state = package
    candidate_evidence = _candidate_evidence(package_state)
    gates = [
        {"gate": "engineering_correctness", "status": "FAIL", "reason": "ENG-001"},
        {"gate": "authority_acquisition_and_integrity", "status": "BLOCKED", "reason": "AUTH-001"},
        {"gate": "authority_currentness_and_coverage", "status": "BLOCKED", "reason": "AUTH-001; AUTH-002"},
        {"gate": "independent_legal_review", "status": "BLOCKED", "reason": "LEGAL-001"},
        {"gate": "privacy_security_ai_behavior", "status": "NOT_RUN", "reason": "Current full qualification receipt required."},
        {"gate": "installed_windows_accessibility", "status": "BLOCKED", "reason": "WIN-001"},
        {"gate": "store_submission_preparation", "status": "BLOCKED", "reason": "STORE-001"},
        {"gate": "microsoft_certification_publication", "status": "NOT_RUN", "reason": "External Microsoft process has not been submitted or completed."},
    ]
    return {
        "schema_version": "nhfl.prelaunch-release-readiness.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": _revision(),
        "overall_status": "NOT_READY",
        "gates": gates,
        "blockers": ledger["blockers"],
        "artifact": {
            "path": package_state.relative_to(ROOT).as_posix(),
            "sha256": _sha256(package_state),
            "exists": package_state.is_file(),
        },
        "candidate_evidence": candidate_evidence,
        "invalidation": "Any relevant source, prompt, model/runtime, calculation, dependency, or package change requires a fresh receipt for affected gates.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the machine-readable status to this path.")
    parser.add_argument(
        "--package",
        required=True,
        help="Repository-relative MSIX candidate to bind to this receipt.",
    )
    args = parser.parse_args()
    try:
        package = _resolve_candidate(args.package)
    except ValueError as exc:
        parser.error(str(exc))
    report = build_report(package=package)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["overall_status"] == "READY_FOR_OWNER_SUBMISSION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
