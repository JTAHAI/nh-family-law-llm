"""Installed model management must not depend on a checkout or invent admission."""
from __future__ import annotations

import shutil
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.release_boundary import production_request_active
from app.api.routes import models
from legal.model_orchestration import store

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "synthetic-pass04"}


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "fictional-project"
    root.mkdir()
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(root))
    monkeypatch.setenv("NHFL_MODEL_STORE_ROOT", str(tmp_path / "model-state"))
    monkeypatch.setenv("NHFL_RUNTIME_MODE", "source")
    return root


def client():
    app = FastAPI()
    app.include_router(models.router, prefix="/api")
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345))


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_default_model_root_inside_project_is_refused_without_creation(project, monkeypatch, configured):
    home = project / "fictional-private-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(store.ModelStoreRootError) as caught:
        store.resolve_external_model_root(configured, project_root=project, create=True)
    assert caught.value.code == "external_root_inside_source_repo"
    assert not home.exists()


@pytest.mark.parametrize("segment", sorted(store.FORBIDDEN_SEGMENTS))
def test_protected_model_roots_are_refused_before_mkdir(project, tmp_path, segment):
    path = tmp_path / segment / "new-models"
    with pytest.raises(store.ModelStoreRootError):
        store.resolve_external_model_root(path, project_root=project, create=True)
    assert not path.parent.exists()


@pytest.mark.parametrize("segment", ["a", "data", "win", "system", "normal-profile"])
def test_harmless_ancestors_are_not_reverse_substring_matches(project, tmp_path, segment):
    path = tmp_path / segment / "models"
    assert store.resolve_external_model_root(path, project_root=project) == path
    assert not path.exists()


@pytest.mark.parametrize("configured", [None, "explicit"])
def test_valid_model_root_and_layout(project, tmp_path, monkeypatch, configured):
    home = tmp_path / "safe-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    expected = home / ".codex/model_store" / project.name
    path = expected if configured else None
    layout = store.external_model_store_layout(path, project_root=project)
    assert layout.root == expected
    assert {p.name for p in expected.iterdir()} == {
        "registry", "artifacts", "runtime_profiles", "benchmark_runs", "health",
        "logs", "cache", "quarantine", "routing",
    }


@pytest.mark.parametrize("kind", ["root", "ancestor", "dangling", "child"])
def test_linked_model_paths_are_rejected_without_touching_target(project, tmp_path, kind):
    target = tmp_path / "target"
    if kind != "dangling":
        target.mkdir()
    path = tmp_path / "model-state"
    if kind == "child":
        path.mkdir()
    link = path / "artifacts" if kind == "child" else path
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    requested = path / "new" if kind == "ancestor" else path
    with pytest.raises(store.ModelStoreRootError):
        store.external_model_store_layout(requested, project_root=project)
    if kind == "dangling":
        assert not target.exists()
    else:
        assert not list(target.iterdir())
    if kind == "child":
        assert not (path / "registry").exists()


def test_model_reparse_ancestor_is_rejected_before_resolve(project, tmp_path, monkeypatch):
    ancestor = tmp_path / "junction"
    real = Path.lstat

    def metadata(path, *args, **kwargs):
        if path == ancestor:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(store.ModelStoreRootError):
        store.resolve_external_model_root(ancestor / "new", project_root=project, create=True)
    assert not ancestor.exists()


def test_model_root_cannot_contain_the_project(project):
    with pytest.raises(store.ModelStoreRootError) as caught:
        store.resolve_external_model_root(project.parent, project_root=project)
    assert caught.value.code == "external_root_contains_forbidden_root"


def test_hardware_profile_does_not_initialize_model_storage(project, monkeypatch):
    def forbidden():
        raise AssertionError("Hardware inventory must not initialize model storage")
    monkeypatch.setattr(models, "_center", forbidden)
    with client() as c:
        response = c.get("/api/hardware/profile", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["logical_cpu_count"] >= 1
    assert response.json()["review_required"] is True
    assert not (project.parent / "model-state").exists()


def test_model_routes_use_packaged_policies_not_project_configs(project):
    assert not (project / "configs").exists()
    with client() as c:
        response = c.get("/api/models", headers=HEADERS)
        routing = c.get("/api/model-routing/status", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["model_count"] == 0
    assert routing.status_code == 200
    assert routing.json()["selected_model_id"] is None
    assert routing.json()["status"] == "fallback_review_required"
    assert not (project / "configs").exists()


def test_production_model_center_does_not_bootstrap_development_admissions(project):
    config = project / "configs"
    config.mkdir()
    for name in ("nh_model_roles.json", "nh_model_admission_policy.json", "nh_model_registry.seed.json"):
        shutil.copyfile(ROOT / "configs" / name, config / name)
    token = production_request_active.set(True)
    try:
        with client() as c:
            response = c.get("/api/models", headers=HEADERS)
    finally:
        production_request_active.reset(token)
    assert response.status_code == 200, response.text
    assert response.json()["models"] == []
    assert not (project.parent / "model-state/registry/registry.json").exists()


def test_denied_model_store_is_sanitized_and_retryable(project, monkeypatch):
    monkeypatch.setenv("NHFL_MODEL_STORE_ROOT", str(project / "private-location/models"))
    with client() as c:
        for _ in range(2):
            r = c.get("/api/models", headers=HEADERS)
            assert r.status_code == 503
            assert r.json()["detail"] == {"error": "model_control_unavailable", "review_required": True}
            assert "private-location" not in r.text
        monkeypatch.setenv("NHFL_MODEL_STORE_ROOT", str(project.parent / "safe-models"))
        assert c.get("/api/models", headers=HEADERS).status_code == 200
    assert not (project / "private-location").exists()


def test_missing_shipped_policy_has_no_project_fallback(project, monkeypatch):
    config = project / "configs"
    config.mkdir()
    for name in ("nh_model_roles.json", "nh_model_admission_policy.json"):
        shutil.copyfile(ROOT / "configs" / name, config / name)
    monkeypatch.setattr(models, "runtime_config_path", lambda name: project / "private-missing" / name, raising=False)
    with client() as c:
        r = c.get("/api/models", headers=HEADERS)
    assert r.status_code == 503
    assert "private-missing" not in r.text
    assert not (project.parent / "model-state").exists()


def test_rejected_requests_do_not_touch_hardware_or_model_stores(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("guard must run first")
    monkeypatch.setattr(models, "_center", forbidden)
    monkeypatch.setattr(models, "profile_hardware", forbidden, raising=False)
    with client() as c:
        for path in ("/api/hardware/profile", "/api/models", "/api/model-routing/status"):
            assert c.get(path).status_code == 403
            assert c.get(path, headers={**HEADERS, "Origin": "https://untrusted.example"}).status_code == 403


@pytest.mark.parametrize("mode", ["context", "store"])
def test_production_routing_cannot_be_downgraded_by_request(project, monkeypatch, mode):
    calls = []
    stub = SimpleNamespace(routing_status=lambda **kwargs: calls.append(kwargs) or {"review_required": True})
    monkeypatch.setattr(models, "_center", lambda: stub)
    monkeypatch.setenv("NHFL_RUNTIME_MODE", "store" if mode == "store" else "source")
    token = production_request_active.set(mode == "context")
    try:
        with client() as c:
            assert c.get("/api/model-routing/status?require_production=false", headers=HEADERS).status_code == 200
    finally:
        production_request_active.reset(token)
    assert calls[0]["require_production"] is True


def test_model_policy_resources_are_exact_source_copies():
    from nh_family_law_llm.runtime_resources import runtime_config_path
    folder = ROOT / "src/nh_family_law_llm/resources/runtime/configs"
    for name in ("nh_model_roles.json", "nh_model_admission_policy.json"):
        assert (folder / name).read_bytes() == (ROOT / "configs" / name).read_bytes()
        assert runtime_config_path(name) == ROOT / "configs" / name
    assert not (folder / "nh_model_registry.seed.json").exists()


@pytest.mark.parametrize("mode", ["context", "store"])
def test_production_runtime_plan_cannot_be_downgraded(project, monkeypatch, mode):
    calls = []
    stub = SimpleNamespace(hardware_profile=object(), registry=SimpleNamespace(list_records=lambda: []))
    monkeypatch.setattr(models, "_center", lambda: stub)
    monkeypatch.setattr(models, "get_runtime_kernel", lambda: SimpleNamespace(list_jobs=lambda **kwargs: []))
    monkeypatch.setattr(models, "AdaptiveRuntimePlanner", lambda profile: SimpleNamespace(
        plan=lambda **kwargs: calls.append(kwargs) or {"status": "fallback_review_required"}))
    monkeypatch.setenv("NHFL_RUNTIME_MODE", "store" if mode == "store" else "source")
    token = production_request_active.set(mode == "context")
    try:
        with client() as c:
            r = c.post("/api/model-runtime/plan", headers=HEADERS, json={"require_production": False})
            assert r.status_code == 200, r.text
    finally:
        production_request_active.reset(token)
    assert calls[0]["require_production"] is True


def test_production_registry_preserves_existing_records_without_seeding(project):
    import json
    registry = project.parent / "model-state/registry/registry.json"
    registry.parent.mkdir(parents=True)
    raw = json.dumps({"records": [{"model_id": "fictional-existing-record", "admission_status": "candidate"}]}).encode()
    registry.write_bytes(raw)
    token = production_request_active.set(True)
    try:
        with client() as c:
            r = c.get("/api/models", headers=HEADERS)
    finally:
        production_request_active.reset(token)
    assert r.status_code == 200
    assert [row["model_id"] for row in r.json()["models"]] == ["fictional-existing-record"]
    assert registry.read_bytes() == raw
