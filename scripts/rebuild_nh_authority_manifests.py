#!/usr/bin/env python3
"""Synchronize capsule metadata and rebuild every NH authority manifest projection.

The canonical JSON manifest is authoritative. For reviewed local capsules this
script normalizes the non-verbatim extract presentation, recalculates its word
count, refreshes the local-file SHA-256, then rebuilds JSONL, CSV, and the two
embedded Python-package snapshots.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "corpus" / "manifest" / "nh_authorities.json"
LOCAL_CAPSULE_STATUSES = {"current_verified", "future_effective_pending"}
EXTRACT_PATTERN = re.compile(
    r"(?P<header>^## Source-grounded extract \()(?P<count>\d+)(?P<suffix> words\)\n\n)"
    r"(?P<body>.*?)(?=\n\n## )",
    re.MULTILINE | re.DOTALL,
)
WORD_PATTERN = re.compile(r"\b[\w\u2019'-]+\b", re.UNICODE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_capsule(record: dict[str, object]) -> None:
    if record.get("status") not in LOCAL_CAPSULE_STATUSES:
        return
    local_name = str(record.get("local_filename") or "")
    if not local_name:
        raise ValueError(f"{record.get('authority_id')}: reviewed capsule lacks local_filename")
    local = ROOT / local_name
    if not local.is_file():
        raise FileNotFoundError(local)

    text = local.read_text(encoding="utf-8")
    match = EXTRACT_PATTERN.search(text)
    if not match:
        raise ValueError(f"{record.get('authority_id')}: source-grounded extract section missing")

    body = match.group("body").strip()
    if record.get("extract_is_verbatim") is False:
        # A condensed/paraphrased extract must not be visually presented as a quotation.
        body = body.lstrip("\"\u201c\u201d").rstrip("\"\u201c\u201d").strip()
    count = len(WORD_PATTERN.findall(body))
    replacement = f"{match.group('header')}{count}{match.group('suffix')}{body}"
    text = text[: match.start()] + replacement + text[match.end() :]

    frontmatter_pattern = re.compile(
        r"^source_derived_word_count:\s*\d+\s*$", re.MULTILINE
    )
    if not frontmatter_pattern.search(text):
        raise ValueError(f"{record.get('authority_id')}: frontmatter word count missing")
    text = frontmatter_pattern.sub(
        f"source_derived_word_count: {count}", text, count=1
    )
    local.write_text(text, encoding="utf-8", newline="\n")

    record["source_derived_word_count"] = count
    record["sha256"] = sha256(local)


def main() -> int:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = payload["authorities"]
    for record in records:
        normalize_capsule(record)

    payload["authority_count"] = len(records)
    SOURCE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    (ROOT / "corpus/manifest/nh_authorities.jsonl").write_text(
        "\n".join(json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    base = [
        "authority_id",
        "jurisdiction",
        "authority_type",
        "issuing_body",
        "citation",
        "title",
        "chapter",
        "topic_tags",
        "effective_date",
        "amendment_date",
        "status",
        "precedential_status",
        "source_url",
        "local_filename",
        "retrieval_date",
        "sha256",
        "retrieval_priority",
        "retrieval_eligible",
        "verification_required",
        "notes",
    ]
    extra: list[str] = []
    for record in records:
        for key in record:
            if key not in base and key not in extra:
                extra.append(key)
    fields = base + extra
    with (ROOT / "corpus/manifest/nh_authorities.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for record in records:
            row: dict[str, object] = {}
            for key in fields:
                value = record.get(key)
                row[key] = (
                    json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (list, dict))
                    else ("" if value is None else value)
                )
            writer.writerow(row)

    from build_embedded_authority_snapshot import main as build_embedded_authority_snapshot

    build_embedded_authority_snapshot()
    print(f"wrote {len(records)} authority records and rebuilt embedded snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
