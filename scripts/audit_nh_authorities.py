#!/usr/bin/env python3
"""Audit the New Hampshire authority manifest and jurisdiction-safety controls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from scan_for_maine_authority import scan as scan_for_maine_authority

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpus" / "manifest" / "nh_authorities.json"
OFFICIAL_NH_HOSTS = {
    "gc.nh.gov",
    "www.gc.nh.gov",
    "courts.nh.gov",
    "www.courts.nh.gov",
    "dhhs.nh.gov",
    "www.dhhs.nh.gov",
    "mjbportal.courts.nh.gov",
}
DIRECTLY_RELEVANT_FEDERAL_HOST_SUFFIXES = {
    ".uscourts.gov",
    ".supremecourt.gov",
    ".congress.gov",
    ".govinfo.gov",
    ".irs.gov",
    ".ssa.gov",
    ".hhs.gov",
}
VERIFIED_STATUSES = {"current_verified", "historical_verified", "superseded_verified"}


def _official_host(host: str) -> bool:
    host = host.lower().strip(".")
    if host in OFFICIAL_NH_HOSTS:
        return True
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in DIRECTLY_RELEVANT_FEDERAL_HOST_SUFFIXES)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-local", action="store_true", help="Require a checked local snapshot for every authority record.")
    parser.add_argument("--skip-legacy-scan", action="store_true", help="Skip the separate active Maine-authority scan.")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    if not MANIFEST.exists():
        print(json.dumps({"ok": False, "errors": [f"manifest missing: {MANIFEST}"]}, indent=2))
        return 1

    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"manifest unreadable: {exc}"]}, indent=2))
        return 1

    authorities = payload.get("authorities")
    if not isinstance(authorities, list):
        errors.append("manifest.authorities must be a list")
        authorities = []

    seen: set[str] = set()
    current_verified = 0
    retrieval_eligible = 0
    locally_snapshotted = 0

    for index, item in enumerate(authorities, start=1):
        if not isinstance(item, dict):
            errors.append(f"authority row {index} is not an object")
            continue
        authority_id = str(item.get("authority_id") or "").strip()
        label = authority_id or f"row-{index}"
        if not authority_id:
            errors.append(f"{label}: missing authority_id")
        elif authority_id in seen:
            errors.append(f"{label}: duplicate authority_id")
        seen.add(authority_id)

        jurisdiction = str(item.get("jurisdiction") or "").strip().upper()
        if jurisdiction not in {"NH", "US"}:
            errors.append(f"{label}: unsupported jurisdiction {jurisdiction!r}; expected NH or directly relevant US overlay")

        citation = str(item.get("citation") or "").strip()
        source_url = str(item.get("source_url") or "").strip()
        if not citation:
            errors.append(f"{label}: missing citation/title identifier")
        if not source_url:
            errors.append(f"{label}: missing source_url")
        else:
            parsed = urlparse(source_url)
            if parsed.scheme != "https":
                errors.append(f"{label}: source_url is not HTTPS")
            host = (parsed.hostname or "").lower()
            if not _official_host(host):
                errors.append(f"{label}: source host is not on the NH/federal official allowlist: {host or '<missing>'}")

        status = str(item.get("status") or "").strip()
        eligible = item.get("retrieval_eligible") is True
        if status == "current_verified":
            current_verified += 1
        if eligible:
            retrieval_eligible += 1
            if status != "current_verified":
                errors.append(f"{label}: retrieval_eligible requires status=current_verified")
            if not item.get("effective_date_checked") and not item.get("reviewed_at"):
                errors.append(f"{label}: retrieval-eligible authority lacks review/effective-date evidence")

        local_filename = str(item.get("local_filename") or "").strip()
        expected_hash = str(item.get("sha256") or "").strip().lower()
        if args.require_local and not local_filename:
            errors.append(f"{label}: no local snapshot")
        if local_filename:
            local_path = ROOT / local_filename
            if not local_path.is_file():
                errors.append(f"{label}: missing local snapshot {local_filename}")
            else:
                locally_snapshotted += 1
                actual_hash = _sha256(local_path)
                if expected_hash and actual_hash != expected_hash:
                    errors.append(f"{label}: local snapshot checksum mismatch")
                elif not expected_hash:
                    warnings.append(f"{label}: local snapshot exists but sha256 is not recorded")
                if eligible and not expected_hash:
                    errors.append(f"{label}: retrieval-eligible local authority must record sha256")
        elif expected_hash:
            errors.append(f"{label}: sha256 recorded without local_filename")

        if status in VERIFIED_STATUSES and not (item.get("reviewed_at") or item.get("retrieved_at")):
            warnings.append(f"{label}: verified status lacks a review/retrieval timestamp")

    expected_count = payload.get("authority_count")
    if isinstance(expected_count, int) and expected_count != len(authorities):
        errors.append(f"authority_count={expected_count} does not match {len(authorities)} rows")

    required_dirs = [
        ROOT / "corpus" / "CURRENT_AUTHORITY",
        ROOT / "corpus" / "PENDING_REVIEW",
        ROOT / "corpus" / "HISTORICAL_SUPERSEDED",
    ]
    for path in required_dirs:
        if not path.is_dir():
            errors.append(f"required corpus lane missing: {path.relative_to(ROOT).as_posix()}")

    legacy_findings = [] if args.skip_legacy_scan else scan_for_maine_authority()
    for finding in legacy_findings:
        errors.append(f"active Maine authority marker: {finding.path}:{finding.line} ({finding.marker})")

    if current_verified == 0:
        warnings.append("No authority record is yet marked current_verified; runtime retrieval must remain fail-closed.")
    if retrieval_eligible == 0:
        warnings.append("No authority record is retrieval eligible; this is acceptable for a seed inventory but not a populated production corpus.")

    result = {
        "ok": not errors,
        "manifest": MANIFEST.relative_to(ROOT).as_posix(),
        "authority_records": len(authorities),
        "current_verified_records": current_verified,
        "retrieval_eligible_records": retrieval_eligible,
        "local_snapshot_records": locally_snapshotted,
        "legacy_authority_findings": len(legacy_findings),
        "errors": errors,
        "warnings": warnings,
        "coverage_claim": payload.get("coverage_claim", "coverage claim not supplied"),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
