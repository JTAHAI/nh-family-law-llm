from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.nh_family_law import (
    InvalidLegalBehaviorInput,
    NewHampshireLegalBehaviorEngine,
)

ROOT = Path(__file__).resolve().parents[1]


def analyze(payload: dict):
    return NewHampshireLegalBehaviorEngine().analyze(payload).to_dict()


def by_id(report: dict, finding_id: str) -> dict:
    return next(row for row in report["findings"] if row["finding_id"] == finding_id)


def test_major_parenting_change_requires_statutory_gate():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Change every other weekend to 50/50 parenting time",
        "parenting": {
            "permanent_order": True,
            "requested_change_scope": "eow_to_equal",
            "agreement": False,
            "repeated_interference": False,
            "detrimental_environment": False,
            "substantially_equal_not_working": False,
            "mature_child_preference": False,
            "minimal_change": False,
            "travel_change": False,
            "work_schedule_change": False,
            "young_age_after_five_years": False,
        },
    })
    finding = by_id(report, "no_parenting_modification_gate_identified")
    assert finding["severity"] == "blocker"
    assert by_id(report, "major_schedule_change")["status"] == "supported_by_reported_facts"


def test_work_schedule_gate_is_issue_spotted_not_promised():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Modify parenting because my work schedule changed",
        "parenting": {
            "permanent_order": True,
            "requested_change_scope": "major",
            "work_schedule_change": True,
        },
    })
    finding = by_id(report, "parenting_gate_work_schedule_change")
    assert finding["status"] == "supported_by_reported_facts"
    assert "not a prediction" in finding["caveats"][0]


def test_equal_schedule_zero_support_path_is_rebuttable_and_separate():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Review 50/50 parenting and lower child support",
        "support": {
            "order_issuer": "court",
            "last_support_order_date": "2023-01-01",
            "parenting_percent_obligor": 50,
            "parenting_percent_obligee": 50,
            "substantially_similar_incomes": True,
            "each_pays_half_eligible_childcare": True,
            "each_pays_half_uninsured_medical": True,
            "each_pays_half_agreed_extracurricular": True,
            "extraordinary_circumstances": False,
        },
    })
    finding = by_id(report, "support_parenting_schedule_deviation")
    assert "rebuttable presumption" in finding["explanation"]
    assert "$0" in finding["explanation"]
    assert by_id(report, "support_no_automatic_reduction")["severity"] == "warning"


def test_shared_schedule_without_preconditions_does_not_create_deviation():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Does 40 percent parenting lower child support?",
        "support": {
            "last_support_order_date": "2022-01-01",
            "parenting_percent_obligor": 40,
            "parenting_percent_obligee": 60,
        },
    })
    assert by_id(report, "support_parenting_schedule_deviation_missing_preconditions")


def test_ordinary_living_expenses_are_not_automatic_deductions():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Can rent and a car payment lower child support?",
        "support": {"last_support_order_date": "2022-01-01"},
    })
    assert any("rent, car payments" in notice for notice in report["notices"])


def test_court_order_and_dhhs_collection_routes_to_court_order():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "DHHS collects my court child support",
        "support_order": {
            "has_signed_court_support_order": True,
            "dhhs_only_collects_or_withholds": True,
        },
    })
    assert any(row["route_id"] == "court_support_order_controls" for row in report["routes"])


def test_rsa_161_c_decision_routes_to_administrative_process():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "I received an RSA 161-C administrative support decision",
        "support_order": {"has_rsa_161_c_hearing_decision": True},
    })
    assert any(row["route_id"] == "rsa_161_c_administrative_order" for row in report["routes"])


def test_uifsa_fails_closed_until_section_authority_is_promoted():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Register a support order from another state under UIFSA",
        "interstate": {"support_order_state": "MA"},
    })
    assert any("RSA 546-B" in gap for gap in report["authority_gaps"])
    assert by_id(report, "required_authority_unavailable")["severity"] == "blocker"


def test_other_state_parenting_order_requires_jurisdiction_review():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "NH should modify an out-of-state parenting order",
        "interstate": {"parenting_order_state": "MA", "child_present_in_nh": True},
    })
    route = next(row for row in report["routes"] if row["route_id"] == "uccjea_modify_other_state_order")
    assert "may not ordinarily modify" in route["explanation"]


def test_drafting_control_blocks_unilateral_noncompliance():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Review a support modification",
        "support": {"last_support_order_date": "2022-01-01"},
        "draft_text": "I will stop paying until the court changes it.",
    })
    assert by_id(report, "draft_overclaim_2")["severity"] == "blocker"


def test_authority_references_are_hash_valid_and_active():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Modify parenting because work schedule changed",
        "parenting": {"permanent_order": True, "work_schedule_change": True},
    })
    assert report["authority_references"]
    assert not report["authority_gaps"]
    assert all(row["retrieval_eligible"] for row in report["authority_references"])


def test_example_is_generalized_and_runnable():
    payload = json.loads((ROOT / "examples/pass06_parenting_support_review.json").read_text())
    report = analyze(payload)
    assert report["review_required"] is True
    assert report["filing_ready"] is False
    serialized = json.dumps(payload).casefold()
    assert "private_case_person" not in serialized and "private_message_screenshot_marker" not in serialized


def test_known_future_amendment_blocks_stale_capsule_after_effective_date():
    report = analyze({
        "as_of_date": "2026-09-13",
        "question": "Modify parenting because my work schedule changed",
        "parenting": {"permanent_order": True, "work_schedule_change": True},
    })
    assert any(
        "known amendment is now effective" in gap and "RSA 461-A:6" in gap
        for gap in report["authority_gaps"]
    )
    assert by_id(report, "required_authority_unavailable")["severity"] == "blocker"


def test_signed_court_order_infers_support_issuer():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Review child support",
        "support": {"last_support_order_date": "2022-01-01"},
        "support_order": {"has_signed_court_support_order": True},
    })
    route = next(row for row in report["routes"] if row["route_id"] == "child_support_modification")
    assert "Family Division/court" in route["explanation"]


def test_income_similarity_can_be_computed_from_reported_gross_monthly_income():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Review equal parenting child support",
        "support": {
            "last_support_order_date": "2022-01-01",
            "parenting_percent_obligor": 50,
            "parenting_percent_obligee": 50,
            "gross_monthly_income_obligor": 6000,
            "gross_monthly_income_obligee": 5500,
            "each_pays_half_eligible_childcare": True,
            "each_pays_half_uninsured_medical": True,
            "each_pays_half_agreed_extracurricular": True,
            "extraordinary_circumstances": False,
        },
    })
    assert "$0" in by_id(report, "support_parenting_schedule_deviation")["explanation"]


def test_parenting_percentages_must_reconcile_to_full_annual_schedule():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Review shared parenting child support",
        "support": {
            "last_support_order_date": "2022-01-01",
            "parenting_percent_obligor": 45,
            "parenting_percent_obligee": 45,
        },
    })
    assert by_id(report, "support_parenting_percent_total")["severity"] == "blocker"


def test_support_only_interstate_facts_do_not_trigger_uccjea_route():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Register support order from another state",
        "interstate": {"support_order_state": "MA"},
    })
    assert "uifsa" in report["issues"]
    assert "uccjea" not in report["issues"]


def test_api_route_is_registered_and_review_required():
    from app.api.main import app
    from app.api.routes.nh_legal_behavior import LegalBehaviorRequest, analyze_legal_behavior

    assert any(
        getattr(route, "path", None) == "/api/legal-behavior/analyze"
        for route in app.routes
    )
    result = analyze_legal_behavior(
        LegalBehaviorRequest(
            as_of_date="2026-09-11",
            question="Modify parenting because work schedule changed",
            parenting={"permanent_order": True, "work_schedule_change": True},
        )
    )
    assert result["review_required"] is True
    assert result["filing_ready"] is False
    assert result["rbac"]["enforced"] is True


def test_report_has_deterministic_blocker_summary():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "Change parenting to 50/50",
        "parenting": {
            "permanent_order": True,
            "agreement": False,
            "repeated_interference": False,
            "detrimental_environment": False,
            "substantially_equal_not_working": False,
            "mature_child_preference": False,
            "minimal_change": False,
            "travel_change": False,
            "work_schedule_change": False,
            "young_age_after_five_years": False,
        },
    })
    assert report["status"] == "blocked"
    assert report["summary"]["blocker_count"] >= 1


def test_self_represented_route_does_not_invent_form_numbers():
    report = analyze({
        "as_of_date": "2026-09-11",
        "question": "I am self-represented and need forms to modify parenting",
        "parenting": {"permanent_order": True, "work_schedule_change": True},
    })
    route = next(row for row in report["routes"] if row["route_id"] == "self_representation_preparation")
    assert route["status"] == "official_forms_and_rules_must_be_verified"
    assert any("forms and procedural rules" in gap for gap in report["authority_gaps"])


def test_behavior_json_schemas_are_valid_json_and_nh_scoped():
    for name in (
        "nh-legal-behavior-input-v1.schema.json",
        "nh-legal-behavior-report-v1.schema.json",
    ):
        data = json.loads((ROOT / "schemas" / name).read_text())
        assert data["$schema"].endswith("2020-12/schema")
        assert "nh-family-law-llm.local" in data["$id"]


def test_invalid_as_of_date_fails_closed():
    with pytest.raises(InvalidLegalBehaviorInput, match="YYYY-MM-DD"):
        analyze({"as_of_date": "tomorrow", "question": "Review child support"})


def test_non_object_fact_lane_fails_closed():
    with pytest.raises(InvalidLegalBehaviorInput, match="support must be an object"):
        analyze({"as_of_date": "2026-09-11", "support": "not-an-object"})


def test_api_invalid_input_returns_422():
    from fastapi.testclient import TestClient
    from app.api.main import app

    response = TestClient(app).post(
        "/api/legal-behavior/analyze",
        headers={
            "X-User-Role": "reviewer",
            "X-Tenant-Id": "fictional-pass06",
            "X-NHFL-Client-Session": "p" * 32,
            "X-NHFL-Idempotency-Key": "pass06-invalid-input",
        },
        json={"as_of_date": "not-a-date", "question": "Review child support"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_nh_legal_behavior_input"
    assert detail["review_required"] is True


def test_api_valid_input_runs_through_protected_route():
    from fastapi.testclient import TestClient
    from app.api.main import app

    response = TestClient(app).post(
        "/api/legal-behavior/analyze",
        headers={
            "X-User-Role": "reviewer",
            "X-Tenant-Id": "fictional-pass06-valid",
            "X-NHFL-Client-Session": "v" * 32,
            "X-NHFL-Idempotency-Key": "pass06-valid-input",
        },
        json={
            "as_of_date": "2026-09-11",
            "question": "Modify parenting because work schedule changed",
            "parenting": {"permanent_order": True, "work_schedule_change": True},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "nh_family_law_llm.legal_behavior_report.v1"
    assert data["review_required"] is True
    assert data["filing_ready"] is False
    assert data["rbac"]["enforced"] is True


def test_v809_release_scope_advances_without_authority_promotion():
    scope = json.loads((ROOT / "configs/v8010_release_scope.json").read_text())
    truth = json.loads((ROOT / "configs/release_feature_truth.json").read_text())
    assert scope["release"] == truth["release"]["product_version"] == "8.0.10"
    assert scope["package_version"] == truth["release"]["package_version"] == "8.0.10.0"
    assert scope["authority_promotions"] == 0
    assert scope["new_public_feature_ids"] == []
    assert scope["windows_package_validation_claimed"] is False
    assert truth["release"]["release_scope"] == "configs/v8010_release_scope.json"


def test_openapi_includes_legal_behavior_route():
    openapi = json.loads((ROOT / "openapi.json").read_text())
    operation = openapi["paths"]["/api/legal-behavior/analyze"]["post"]
    assert operation["summary"].startswith("Run source-gated New Hampshire")


def test_example_and_report_validate_against_published_schemas():
    jsonschema = pytest.importorskip("jsonschema")
    payload = json.loads((ROOT / "examples/pass06_parenting_support_review.json").read_text())
    input_schema = json.loads((ROOT / "schemas/nh-legal-behavior-input-v1.schema.json").read_text())
    output_schema = json.loads((ROOT / "schemas/nh-legal-behavior-report-v1.schema.json").read_text())
    jsonschema.validate(payload, input_schema)
    jsonschema.validate(analyze(payload), output_schema)
