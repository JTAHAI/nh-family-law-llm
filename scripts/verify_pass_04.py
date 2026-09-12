#!/usr/bin/env python3
"""Verify the Pass 4 reviewed NH authority snapshot and its package copies."""
from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpus" / "manifest" / "nh_authorities.json"
OFFICIAL_HOSTS = {"gc.nh.gov", "www.gc.nh.gov"}
REQUIRED_CITATIONS = {
    "RSA 458-C:2",
    "RSA 458-C:5",
    "RSA 458-C:7",
    "RSA 461-A:2",
    "RSA 461-A:6",
    "RSA 461-A:11",
    "RSA 461-A:14",
    "RSA 161-C:8",
    "RSA 161-C:9",
    "RSA 458-A:12",
    "RSA 458-A:15",
}
REQUIRED_PROPOSITIONS = {
    "greater than 40 percent",
    "rebuttable presumption that a $0",
    "three years after the last support order",
    "approximately equal parenting time",
    "moving party bears the burden",
    "subsequent legal support order supersedes",
    "home state",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_embedded_snapshot(
    package_root: Path,
    current_ids: set[str],
    future_ids: set[str],
    errors: list[str],
) -> None:
    snapshot_root = package_root / "data" / "authority_snapshot"
    manifest_path = snapshot_root / "manifest" / "nh_authorities.json"
    if not manifest_path.is_file():
        errors.append(f"missing embedded manifest: {manifest_path.relative_to(ROOT)}")
        return
    embedded = json.loads(manifest_path.read_text(encoding="utf-8"))
    embedded_records = embedded.get("authorities", [])
    embedded_ids = {str(record.get("authority_id")) for record in embedded_records}
    if embedded_ids != current_ids | future_ids:
        errors.append(
            f"embedded ids differ in {package_root.relative_to(ROOT)}: "
            f"expected {len(current_ids | future_ids)}, got {len(embedded_ids)}"
        )
    for record in embedded_records:
        local_filename = str(record.get("local_filename") or "")
        local = snapshot_root / local_filename
        if not local.is_file():
            errors.append(f"embedded file missing: {local.relative_to(ROOT)}")
        elif sha256(local) != record.get("sha256"):
            errors.append(f"embedded checksum mismatch: {local.relative_to(ROOT)}")


def main() -> int:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = payload["authorities"]
    errors: list[str] = []
    seen: set[str] = set()
    current: list[dict[str, object]] = []
    future: list[dict[str, object]] = []

    for record in records:
        authority_id = str(record.get("authority_id") or "")
        if authority_id in seen:
            errors.append(f"duplicate id {authority_id}")
        seen.add(authority_id)
        status = record.get("status")
        if status == "current_verified":
            current.append(record)
        elif status == "future_effective_pending":
            future.append(record)

        eligible = record.get("retrieval_eligible") is True
        if eligible and status != "current_verified":
            errors.append(f"{authority_id}: eligible without current_verified")
        if eligible and str(record.get("effective_date") or "9999-12-31") > payload["as_of_date"]:
            errors.append(f"{authority_id}: future effective date is retrieval eligible")
        if status == "future_effective_pending" and eligible:
            errors.append(f"{authority_id}: future overlay must remain ineligible")

        local_filename = str(record.get("local_filename") or "")
        local = ROOT / local_filename if local_filename else None
        source_url = str(record.get("source_url") or "")
        if record.get("snapshot_kind") == "normalized_authority_capsule":
            if urlparse(source_url).hostname not in OFFICIAL_HOSTS:
                errors.append(f"{authority_id}: capsule source is not an official General Court host")
            if record.get("raw_source_bytes_preserved") is not False:
                errors.append(f"{authority_id}: capsule raw-source flag invalid")
            if record.get("extract_is_verbatim") is not False:
                errors.append(f"{authority_id}: extract must be marked non-verbatim")
            source_text = (
                local.read_text(encoding="utf-8")
                if local is not None and local.is_file()
                else ""
            )
            extract_match = re.search(
                r"## Source-grounded extract \((\d+) words\)\n\n(.*?)(?=\n\n## )",
                source_text,
                re.DOTALL,
            )
            declared_count = int(record.get("source_derived_word_count", 9999))
            if declared_count > 190:
                errors.append(f"{authority_id}: source-grounded extract is over 190 words")
            if extract_match:
                extract_body = extract_match.group(2).strip()
                heading_count = int(extract_match.group(1))
                actual_count = len(
                    re.findall(r"\b[\w\u2019'-]+\b", extract_body)
                )
                if heading_count != declared_count or actual_count != declared_count:
                    errors.append(
                        f"{authority_id}: extract word-count metadata differs "
                        f"(manifest={declared_count}, heading={heading_count}, actual={actual_count})"
                    )
                if record.get("extract_is_verbatim") is False and (
                    extract_body.startswith(("\"", "\u201c", "\u201d"))
                    or extract_body.endswith(("\"", "\u201c", "\u201d"))
                ):
                    errors.append(
                        f"{authority_id}: non-verbatim extract is visually presented as a quotation"
                    )
            else:
                errors.append(f"{authority_id}: source-grounded extract section missing")
            if record.get("snapshot_completeness") != (
                "source_grounded_extract_and_structured_summary"
            ):
                errors.append(f"{authority_id}: snapshot completeness marker is missing")

        if local_filename and local is not None:
            if not local.is_file():
                errors.append(f"{authority_id}: missing {local}")
            elif sha256(local) != record.get("sha256"):
                errors.append(f"{authority_id}: checksum mismatch")

    current_citations = {str(record["citation"]) for record in current}
    missing = REQUIRED_CITATIONS - current_citations
    if missing:
        errors.append(f"missing core capsules: {sorted(missing)}")
    if len(current) < 35:
        errors.append(f"expected at least 35 current capsules, got {len(current)}")
    if len(future) < 2:
        errors.append("future-effective overlays missing")

    current_text = "\n".join(
        (ROOT / str(record["local_filename"])).read_text(encoding="utf-8")
        for record in current
        if record.get("local_filename")
    ).lower()
    for phrase in REQUIRED_PROPOSITIONS:
        if phrase.lower() not in current_text:
            errors.append(f"missing proposition text: {phrase}")

    blockers = payload.get("acquisition_blockers", [])
    if len(blockers) < 3:
        errors.append(f"expected at least 3 acquisition blocker receipts, got {len(blockers)}")
    for blocker in blockers:
        blocker_id = str(blocker.get("blocker_id") or "<missing>")
        if blocker.get("retrieval_eligible") is not False:
            errors.append(f"{blocker_id}: blocker cannot be retrieval eligible")
        receipt_name = str(blocker.get("receipt_filename") or "")
        receipt = ROOT / receipt_name
        if not receipt.is_file():
            errors.append(f"{blocker_id}: blocker receipt missing")
        elif sha256(receipt) != blocker.get("receipt_sha256"):
            errors.append(f"{blocker_id}: blocker receipt checksum mismatch")

    current_ids = {str(record["authority_id"]) for record in current}
    future_ids = {str(record["authority_id"]) for record in future}
    for package_root in (
        ROOT / "nh_family_law_llm",
        ROOT / "src" / "nh_family_law_llm",
    ):
        verify_embedded_snapshot(package_root, current_ids, future_ids, errors)

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if path.suffix.lower() in {".jpg", ".jpeg"} and (
            "message" in lowered or "private" in lowered
        ):
            errors.append(f"private screenshot present: {path}")

    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "current_verified": len(current),
                "future_pending": len(future),
                "total": len(records),
                "embedded_package_copies": 2,
                "as_of": payload["as_of_date"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
