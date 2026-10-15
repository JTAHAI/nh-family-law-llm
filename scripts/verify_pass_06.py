#!/usr/bin/env python3
"""Deterministic source gate for the New Hampshire legal-behavior checkpoint."""
from __future__ import annotations

import json
import re
import sys
import tomllib
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
    # This workflow runs on the current branch, not a historical Pass 6 tag.
    # Bind the retained behavior contract to the independently recorded active
    # scope instead of requiring the retired 8.0.8 executable forever.
    truth = load_json("configs/release_feature_truth.json")
    release = truth["release"]
    scope_path = release.get("release_scope", "")
    require(isinstance(scope_path, str) and
            re.fullmatch(r"configs/v[0-9]+_release_scope\.json", scope_path) is not None,
            "active release scope path invalid")
    scope = load_json(scope_path)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    require(VERSION == scope["release"] == release["product_version"] == project["version"],
            "active product version mismatch")
    require(PACKAGE_VERSION == scope["package_version"] == release["package_version"]
            == f"{VERSION}.0", "active package version mismatch")
    require(type(scope["build_number"]) is int and BUILD_NUMBER == scope["build_number"],
            "active build number mismatch")
    require(UI_VERSION == scope["ui_version"], "active UI version mismatch")
    require(UI_PASS_MARKER == scope["ui_pass_marker"], "active UI pass marker mismatch")
    require(type(scope["pass"]) is int and UI_FOOTER_LABEL == f"v{VERSION} Pass {scope['pass']}",
            "active UI footer mismatch")
    require(scope["authority_promotions"] == 0, "behavior gate must promote no authority")
    require(scope["new_public_feature_ids"] == [], "behavior gate must create no release claim")
    for field in ("production_ready", "attorney_reviewed", "filing_ready",
                  "windows_package_validation_claimed"):
        require(scope.get(field) is False, "unearned active scope claim: " + field)

    # Preserve the historical checkpoint rather than rewriting its records.
    historical = load_json("configs/v808_release_scope.json")
    require(historical["release"] == "8.0.8" and historical["package_version"] == "8.0.8.0",
            "historical behavior checkpoint identity changed")
    require(historical["authority_promotions"] == 0 and historical["new_public_feature_ids"] == [],
            "historical behavior checkpoint claims changed")

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
                "scope": "engineering_behavior_contract_only",
                "production_ready": False,
                "legal_review_verified": False,
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
