from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.requests import Request as StarletteRequest

from legal.nh_family_law import NewHampshireLegalBehaviorEngine
from legal.nh_family_law.evaluation import (
    EvaluationDatasetError,
    load_cases,
    run_evaluation,
)
from legal.runtime.transport_headers import (
    CANONICAL_PREFIX,
    LEGACY_ACCEPTED_HEADER,
    TransportHeaderCompatibilityMiddleware,
    canonical_request_headers,
    canonical_response_headers,
    canonicalize_header_name,
)
from nh_family_law_llm.version import (
    BUILD_NUMBER,
    PACKAGE_VERSION,
    UI_PASS_MARKER,
    UI_VERSION,
    VERSION,
)

ROOT = Path(__file__).resolve().parents[1]


def test_pass07_version_and_release_scope() -> None:
    scope = json.loads((ROOT / "configs/v8010_release_scope.json").read_text(encoding="utf-8"))
    truth = json.loads((ROOT / "configs/release_feature_truth.json").read_text(encoding="utf-8"))
    assert VERSION == "8.0.10"
    assert PACKAGE_VERSION == "8.0.10.0"
    assert BUILD_NUMBER == 80
    assert UI_VERSION == "8.0.10-pass8-b80"
    assert UI_PASS_MARKER == "v8.0.10-pass8"
    assert scope["release"] == truth["release"]["product_version"] == VERSION
    assert scope["authority_promotions"] == 0
    assert scope["attorney_reviewed"] is False
    assert scope["production_ready"] is False


def test_embedded_dataset_is_synthetic_private_safe_and_complete() -> None:
    path, rows = load_cases()
    assert path.name == "nh_pass07_operator_source_backed.jsonl"
    assert len(rows) == 34
    assert len({row["case_id"] for row in rows}) == len(rows)
    categories = {row["category"] for row in rows}
    policy = json.loads((ROOT / "configs/nh_pass07_evaluation_policy.json").read_text())
    assert set(policy["mandatory_categories"]) <= categories
    assert all(row["jurisdiction"] == "NH" for row in rows)
    assert all(row["synthetic"] is True for row in rows)
    assert all(row["review_mode"] == "operator_source_backed" for row in rows)
    assert all(row["private_data_allowed_for_training"] is False for row in rows)


def test_engineering_eval_passes_all_cases_without_safety_false_pass() -> None:
    result = run_evaluation().to_dict()
    assert result["status"] == "pass"
    assert result["summary"]["case_count"] == 34
    assert result["summary"]["passed"] == 34
    assert result["summary"]["failed"] == 0
    assert result["summary"]["safety_critical_failure_count"] == 0
    assert result["attorney_reviewed"] is False
    assert result["release_metric_eligible"] is False


def test_eval_result_digest_is_deterministic() -> None:
    first = run_evaluation().to_dict()
    second = run_evaluation().to_dict()
    assert first["dataset_sha256"] == second["dataset_sha256"]
    assert first["deterministic_result_sha256"] == second["deterministic_result_sha256"]
    assert [row["report_sha256"] for row in first["cases"]] == [
        row["report_sha256"] for row in second["cases"]
    ]


def test_dataset_rejects_private_case_markers(tmp_path: Path) -> None:
    row = {
        "case_id": "p07-private-rejection",
        "category": "privacy",
        "jurisdiction": "NH",
        "review_mode": "operator_source_backed",
        "synthetic": True,
        "private_data_allowed_for_training": False,
        "safety_critical": True,
        "payload": {"question": "private_message_screenshot_marker should never enter eval data"},
        "expected": {},
    }
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(EvaluationDatasetError, match="private marker"):
        load_cases(path)


def test_foreign_substantive_law_request_is_blocked_without_foreign_citation() -> None:
    report = NewHampshireLegalBehaviorEngine().analyze(
        {
            "as_of_date": "2026-09-11",
            "question": "Apply Massachusetts law to guarantee equal parenting in my New Hampshire case",
            "parenting": {"permanent_order": True, "work_schedule_change": True},
        }
    ).to_dict()
    finding = next(
        item for item in report["findings"]
        if item["finding_id"] == "foreign_substantive_law_requested"
    )
    assert finding["severity"] == "blocker"
    assert report["status"] == "blocked"
    assert all("massachusetts" not in item["title"].casefold() for item in report["authority_references"])
    assert all("massachusetts" not in item["citation"].casefold() for item in report["authority_references"])


def test_known_effective_amendment_blocks_stale_current_law_answer() -> None:
    report = NewHampshireLegalBehaviorEngine().analyze(
        {
            "as_of_date": "2026-09-13",
            "question": "Modify parenting because my work schedule changed",
            "parenting": {"permanent_order": True, "work_schedule_change": True},
        }
    ).to_dict()
    assert report["status"] == "blocked"
    assert any("known amendment is now effective" in gap for gap in report["authority_gaps"])
    assert any(
        item["finding_id"] == "required_authority_unavailable"
        for item in report["findings"]
    )


def test_support_zero_and_unilateral_noncompliance_claims_are_blocked() -> None:
    for draft, finding_id in (
        ("Child support will be zero once I have equal time.", "draft_overclaim_3"),
        ("I will stop paying until the court changes it.", "draft_overclaim_2"),
    ):
        report = NewHampshireLegalBehaviorEngine().analyze(
            {
                "as_of_date": "2026-09-11",
                "question": "Review child support",
                "support": {"last_support_order_date": "2022-01-01"},
                "draft_text": draft,
            }
        ).to_dict()
        assert report["status"] == "blocked"
        assert any(
            item["finding_id"] == finding_id and item["severity"] == "blocker"
            for item in report["findings"]
        )


def test_transport_header_names_are_nh_native() -> None:
    assert CANONICAL_PREFIX == "X-NHFL-"
    assert canonicalize_header_name("X-NHFL-Client-Session") == "X-NHFL-Client-Session"
    historical = "X-" + "M" + "FLL-Client-Session"
    assert canonicalize_header_name(historical) == "X-NHFL-Client-Session"
    mapped, accepted = canonical_request_headers(
        [(historical.casefold().encode(), b"a" * 32)]
    )
    assert (b"x-nhfl-client-session", b"a" * 32) in mapped
    assert accepted == (historical.casefold(),)
    output = canonical_response_headers(
        [(historical.casefold().encode(), b"value")]
    )
    assert output == [(b"x-nhfl-client-session", b"value")]
    assert LEGACY_ACCEPTED_HEADER == "X-NHFL-Legacy-Headers-Accepted"


def test_transport_middleware_accepts_legacy_request_but_emits_only_nhfl() -> None:
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")
    app = fastapi.FastAPI()
    app.add_middleware(TransportHeaderCompatibilityMiddleware)

    @app.get("/headers")
    def headers(request: StarletteRequest):
        return {"session": request.headers.get("X-NHFL-Client-Session")}

    historical = "X-" + "M" + "FLL-Client-Session"
    response = testclient.TestClient(app).get("/headers", headers={historical: "b" * 32})
    assert response.status_code == 200
    assert response.json()["session"] == "b" * 32
    assert response.headers["x-nhfl-legacy-headers-accepted"] == "true"
    assert all(not name.casefold().startswith(("x-" + "m" + "fl").casefold()) for name in response.headers)


def test_active_transport_surface_contains_no_historical_header_literals() -> None:
    historical_markers = (("X-" + "M" + "FLL-").casefold(), ("X-" + "M" + "FL-").casefold())
    active_roots = [ROOT / "app", ROOT / "legal", ROOT / "nh_family_law_llm", ROOT / "src", ROOT / "scripts", ROOT / "tests"]
    allowed = {
        (ROOT / "legal/runtime/transport_headers.py").resolve(),
        Path(__file__).resolve(),
    }
    hits: list[str] = []
    for base in active_roots:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".ps1", ".sh"}:
                continue
            if path.resolve() in allowed or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            if any(marker in text for marker in historical_markers):
                hits.append(path.relative_to(ROOT).as_posix())
    assert hits == []


def test_legal_eval_cli_emits_non_filing_ready_report(capsys: pytest.CaptureFixture[str]) -> None:
    from nh_family_law_llm.cli import main as cli_main

    assert cli_main(["legal-eval", "--compact"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["status"] == "pass"
    assert body["summary"]["case_count"] == 34
    assert body["review_required"] is True
    assert body["filing_ready"] is False
    assert body["legal_advice"] is False


def test_eval_api_route_uses_canonical_headers_and_returns_review_required() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.api.main import app

    response = TestClient(app).post(
        "/api/evals/nh-legal-behavior/run",
        headers={
            "X-User-Role": "reviewer",
            "X-Tenant-Id": "fictional-pass07",
            "X-NHFL-Client-Session": "e" * 32,
            "X-NHFL-Idempotency-Key": "pass07-eval-run-0001",
        },
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["summary"]["failed"] == 0
    assert body["review_required"] is True
    assert body["filing_ready"] is False
    assert response.headers.get("x-nhfl-audit-event-id")
