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


def build_report(*, package: Path | None = None) -> dict[str, Any]:
    ledger_path = ROOT / "docs" / "release" / "RELEASE_BLOCKERS.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    package_state = package or ROOT / "dist" / "store-submission-v8.0.10-partner-identity-r6" / "msix" / "NHFamilyLawLLM_8.0.10.0_x64.msix"
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
        "invalidation": "Any relevant source, prompt, model/runtime, calculation, dependency, or package change requires a fresh receipt for affected gates.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the machine-readable status to this path.")
    parser.add_argument(
        "--package",
        default="dist/store-submission-v8.0.10-partner-identity-r6/msix/NHFamilyLawLLM_8.0.10.0_x64.msix",
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
