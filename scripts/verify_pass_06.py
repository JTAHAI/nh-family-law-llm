#!/usr/bin/env python3
"""Deterministic source gate for the New Hampshire legal-behavior checkpoint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.nh_family_law import InvalidLegalBehaviorInput, NewHampshireLegalBehaviorEngine
from nh_family_law_llm.version import (
    BUILD_NUMBER,
    PACKAGE_VERSION,
    UI_FOOTER_LABEL,
    UI_PASS_MARKER,
    UI_VERSION,
    VERSION,
)



def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    require(VERSION == "8.0.8", f"unexpected VERSION {VERSION}")
    require(PACKAGE_VERSION == "8.0.8.0", f"unexpected PACKAGE_VERSION {PACKAGE_VERSION}")
    require(BUILD_NUMBER == 60, f"unexpected BUILD_NUMBER {BUILD_NUMBER}")
    require(UI_VERSION == "8.0.8-pass6-b60", f"unexpected UI_VERSION {UI_VERSION}")
    require(UI_PASS_MARKER == "v8.0.8-pass6", "unexpected UI pass marker")
    require(UI_FOOTER_LABEL == "v8.0.8 Pass 6", "unexpected UI footer")

    scope = load_json("configs/v808_release_scope.json")
    truth = load_json("configs/release_feature_truth.json")
    require(scope["release"] == VERSION, "v808 scope/version mismatch")
    require(scope["package_version"] == PACKAGE_VERSION, "v808 package mismatch")
    require(scope["authority_promotions"] == 0, "Pass 6 must promote no authority")
    require(scope["new_public_feature_ids"] == [], "Pass 6 must not create a public release claim")
    require(
        truth["release"]["release_scope"] == "configs/v808_release_scope.json",
        "feature truth does not point to v808 scope",
    )

    manifest = load_json("corpus/manifest/nh_authorities.json")
    rows = manifest["authorities"]
    require(len(rows) == 76, f"authority total changed: {len(rows)}")
    require(
        sum(row.get("status") == "current_verified" for row in rows) == 37,
        "current-verified authority count changed",
    )
    require(
        sum(row.get("status") == "future_effective_pending" for row in rows) == 2,
        "future-effective authority count changed",
    )

    example = load_json("examples/pass06_parenting_support_review.json")
    engine = NewHampshireLegalBehaviorEngine()
    report = engine.analyze(example).to_dict()
    require(report["schema"] == "nh_family_law_llm.legal_behavior_report.v1", "report schema mismatch")
    require(report["review_required"] is True, "review-required flag missing")
    require(report["filing_ready"] is False, "engine must not mark filing ready")
    require(report["legal_advice"] is False, "engine must not claim legal advice")
    require(not report["authority_gaps"], f"example authority gaps: {report['authority_gaps']}")

    future = engine.analyze(
        {
            "as_of_date": "2026-09-13",
            "question": "Modify parenting because my work schedule changed",
            "parenting": {"permanent_order": True, "work_schedule_change": True},
        }
    ).to_dict()
    require(
        any("known amendment is now effective" in gap for gap in future["authority_gaps"]),
        "future-effective stale-law gate did not block",
    )

    try:
        engine.analyze({"as_of_date": "not-a-date", "question": "support"})
    except InvalidLegalBehaviorInput:
        pass
    else:
        raise SystemExit("FAIL: invalid as_of_date did not fail closed")

    openapi = load_json("openapi.json")
    require(
        "/api/legal-behavior/analyze" in openapi.get("paths", {}),
        "legal-behavior API route missing from OpenAPI",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "version": VERSION,
                "package_version": PACKAGE_VERSION,
                "build_number": BUILD_NUMBER,
                "authority_total": len(rows),
                "current_verified": 37,
                "future_effective_pending": 2,
                "authority_promotions": 0,
                "example_status": report["status"],
                "example_routes": len(report["routes"]),
                "future_effective_gate": "pass",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
