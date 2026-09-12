#!/usr/bin/env python3
"""Build the small, reviewed authority snapshot shipped inside Python packages.

The repository manifest retains source seeds and acquisition bookkeeping.  The
embedded snapshot contains only current-reviewed capsules and deliberately
inactive future-effective overlays, with paths rewritten relative to the
embedded snapshot root.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "corpus" / "manifest" / "nh_authorities.json"
PACKAGE_ROOTS = [
    ROOT / "nh_family_law_llm",
    ROOT / "src" / "nh_family_law_llm",
]
INCLUDED_STATUSES = {"current_verified", "future_effective_pending"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    selected: list[dict[str, object]] = []
    for source_record in payload.get("authorities", []):
        if source_record.get("status") not in INCLUDED_STATUSES:
            continue
        record = dict(source_record)
        local = str(record.get("local_filename") or "")
        if not local.startswith("corpus/"):
            raise ValueError(f"unexpected canonical capsule path: {local!r}")
        record["local_filename"] = local.removeprefix("corpus/")
        selected.append(record)

    embedded_payload = {
        "schema_version": payload.get("schema_version", "1.1"),
        "generated_at": payload.get("generated_at"),
        "as_of_date": payload.get("as_of_date"),
        "authority_count": len(selected),
        "coverage_claim": (
            "embedded section-scoped core snapshot; exhaustive statewide "
            "coverage is not asserted"
        ),
        "currentness_policy": payload.get("currentness_policy", {}),
        "authorities": selected,
    }

    for package_root in PACKAGE_ROOTS:
        if not (package_root / "__init__.py").is_file():
            continue
        target_root = package_root / "data" / "authority_snapshot"
        if target_root.exists():
            shutil.rmtree(target_root)
        (target_root / "manifest").mkdir(parents=True)
        for record in selected:
            canonical_path = ROOT / "corpus" / str(record["local_filename"])
            target_path = target_root / str(record["local_filename"])
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canonical_path, target_path)
            if sha256(target_path) != record.get("sha256"):
                raise ValueError(f"embedded checksum mismatch: {target_path}")
        (target_root / "manifest" / "nh_authorities.json").write_text(
            json.dumps(embedded_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (target_root / "README.md").write_text(
            "# Embedded NH authority snapshot\n\n"
            "Generated from the canonical corpus manifest. It contains only "
            "reviewed current capsules and inactive future-effective overlays. "
            "The files are condensed source-grounded research aids, not "
            "byte-for-byte reproductions of remote pages.\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps({"embedded_records": len(selected), "package_roots": [str(p) for p in PACKAGE_ROOTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
