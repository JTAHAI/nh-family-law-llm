from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.contracts import APICompletionPolicy, EndpointInventory, OpenAPICompletionAuditor
# The frozen desktop dispatches this unified gateway.  Auditing the modular
# enterprise sub-application alone produces false missing-route findings for
# local-workbench routes that deliberately avoid duplicate aliases.
from app.api.production import app
from app.web.ui_contracts import UICompletionAuditor


def _registered_routes() -> set[tuple[str, str]]:
    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method not in {"HEAD", "OPTIONS"} and str(path).startswith("/api"):
                registered.add((method, str(path)))
    return registered


def test_pass39_openapi_documents_required_api_surface():
    inventory_report = EndpointInventory().compare_to_registered(_registered_routes(), surface="production")
    openapi_report = OpenAPICompletionAuditor().audit(app.openapi(), surface="production").as_dict()
    policy = APICompletionPolicy().evidence().as_dict()

    assert inventory_report["status"] == "pass", inventory_report
    assert openapi_report["status"] == "pass", openapi_report
    assert policy["endpoint_count"] == 15
    assert policy["auth_rbac_enforced"] is True
    assert policy["audit_events_required"] is True


def test_pass39_protected_api_routes_require_role_and_tenant_and_emit_audit_headers(
    tmp_path, monkeypatch,
):
    from app.api.routes import deliberation as deliberation_routes

    # Reproduce the hosted qualifier layout: the synthetic user profile lives
    # inside its synthetic checkout. Read-only preset metadata must not create
    # or fall back to a protected run store merely to answer this request.
    project_root = tmp_path / "synthetic-source"
    profile_root = project_root / "profile"
    project_root.mkdir()
    profile_root.mkdir()
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("HOME", str(profile_root))
    monkeypatch.setenv("USERPROFILE", str(profile_root))
    monkeypatch.delenv("NHFL_DELIBERATION_ROOT", raising=False)
    monkeypatch.setattr(deliberation_routes, "HOST", None)
    monkeypatch.setattr(deliberation_routes, "PRESET_CATALOG", None)
    monkeypatch.setattr(deliberation_routes, "TOOL_BROKER", None)

    client = TestClient(app)

    # Exercise a retained, read-only production endpoint, not the retired
    # caller-supplied authority demonstration that previously returned fake cards.
    denied = client.get("/api/deliberation/presets")
    assert denied.status_code == 403
    assert denied.headers["X-NHFL-RBAC"] == "enforced"
    assert denied.headers["X-NHFL-Audit-Event-Id"]

    allowed = client.get(
        "/api/deliberation/presets",
        headers={"X-User-Role": "attorney", "X-Tenant-Id": "tenant-test"},
    )
    body = allowed.json()
    assert allowed.status_code == 200
    assert allowed.headers["X-NHFL-RBAC"] == "enforced"
    assert allowed.headers["X-NHFL-Audit-Event-Id"]
    assert body["review_required"] is True
    assert body["rbac"]["enforced"] is True
    assert body["audit_event"]["audit_status"] == "emitted"
    assert body["presets"]
    assert not (profile_root / ".codex").exists()

    # A route that actually needs persisted run state still fails closed while
    # the default root would live inside the configured source tree.
    run = client.post(
        "/api/deliberation/runs",
        headers={"X-User-Role": "attorney", "X-Tenant-Id": "tenant-test"},
        json={
            "preset_id": "quick_local_second_opinion",
            "matter_id": "synthetic-matter",
            "question": "Synthetic storage-boundary check",
        },
    )
    assert run.status_code == 503
    assert run.json()["detail"] == {
        "error": "deliberation_storage_unavailable",
        "review_required": True,
    }
    assert client.post("/api/query", json={"query": "custody"}).status_code == 404


def test_pass39_deliberation_run_accepts_explicit_safe_external_store(
    tmp_path, monkeypatch,
):
    from app.api.routes import deliberation as deliberation_routes

    project_root = tmp_path / "synthetic-source"
    safe_store = tmp_path / "external-deliberation-store"
    project_root.mkdir()
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("NHFL_DELIBERATION_ROOT", str(safe_store))
    monkeypatch.setattr(deliberation_routes, "HOST", None)

    client = TestClient(app)
    response = client.post(
        "/api/deliberation/runs",
        headers={"X-User-Role": "attorney", "X-Tenant-Id": "tenant-test"},
        json={
            "preset_id": "quick_local_second_opinion",
            "matter_id": "synthetic-matter",
            "question": "Synthetic external-store acceptance check",
            "jurisdiction": "nh",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["review_required"] is True
    assert safe_store.is_dir()
    assert not (project_root / ".codex").exists()


def test_pass39_health_route_remains_unauthenticated_but_audited():
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    # The desktop shell deliberately labels even unauthenticated health calls
    # as local-desktop reviewer context; the route itself remains callable
    # without a tenant or role header and emits a server audit identifier.
    assert response.headers["X-NHFL-RBAC"] == "local-desktop-reviewer"
    assert response.headers["X-NHFL-Audit-Event-Id"]
    assert response.json()["status"] == "ok"


def test_pass40_web_views_have_source_review_blocker_and_drilldown_markers():
    report = UICompletionAuditor("app/web/pages").audit().as_dict()

    assert report["status"] == "pass", report
    assert report["required_view_count"] >= 14
    assert report["drilldown_chain_required"] == [
        "answer",
        "claim",
        "citation",
        "source_text",
        "verifier_result",
    ]
