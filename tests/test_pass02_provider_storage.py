"""Provider stores obey external-data boundaries, including default selection."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from legal.provider_connections import store


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "fictional-project"
    root.mkdir()
    return root


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_default_inside_checkout_is_rejected_without_creation(project, monkeypatch, configured):
    home = project / "fictional-private-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(store.ProviderStoreRootError) as caught:
        store.resolve_external_provider_root(configured, project_root=project, create=True)
    assert caught.value.code == "external_root_inside_source_repo"
    assert not home.exists()


def test_explicit_inside_checkout_is_rejected_without_creation(project):
    path = project / "provider-state"
    with pytest.raises(store.ProviderStoreRootError) as caught:
        store.resolve_external_provider_root(path, project_root=project, create=True)
    assert caught.value.code == "external_root_inside_source_repo"
    assert not path.exists()


@pytest.mark.parametrize("segment", ["matter", "matter_store", "model_store", "msix", "stage",
                                      "staging", "Windows", "WindowsApps", "Program Files",
                                      "Program Files (x86)", "ProgramData", "system32"])
def test_forbidden_root_is_rejected_before_mkdir(project, tmp_path, segment):
    path = tmp_path / segment / "provider-state"
    with pytest.raises(store.ProviderStoreRootError):
        store.resolve_external_provider_root(path, project_root=project, create=True)
    assert not path.parent.exists()


@pytest.mark.parametrize("leaf", ["data", "a", "win", "system", "normal-profile"])
def test_harmless_partial_segments_are_not_reversed_matches(project, tmp_path, leaf):
    path = tmp_path / leaf / "providers"
    assert store.resolve_external_provider_root(path, project_root=project, create=False) == path
    assert not path.exists()


@pytest.mark.parametrize("configured", [None, "", "explicit"])
def test_valid_default_and_explicit_roots_share_validation(project, tmp_path, monkeypatch, configured):
    home = tmp_path / "safe-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    expected = home / ".codex" / "provider_store" / project.name
    supplied = expected if configured == "explicit" else configured
    assert store.resolve_external_provider_root(supplied, project_root=project, create=False) == expected
    assert not expected.exists()
    layout = store.external_provider_store_layout(supplied, project_root=project)
    assert layout.root == expected
    assert {p.name for p in expected.iterdir()} == {"connections", "manifests", "sessions", "audit", "usage"}


@pytest.mark.parametrize("link_kind", ["root", "ancestor", "dangling"])
def test_link_paths_are_refused_without_touching_targets(project, tmp_path, link_kind):
    target = tmp_path / "target"
    if link_kind != "dangling":
        target.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    path = link / "new-store" if link_kind == "ancestor" else link
    with pytest.raises(store.ProviderStoreRootError) as caught:
        store.resolve_external_provider_root(path, project_root=project, create=True)
    assert caught.value.code == "provider_store_symlink_refused"
    assert not (target / "new-store").exists()
    if link_kind == "dangling":
        assert not target.exists()


def test_reparse_point_is_rejected_before_resolve(project, tmp_path, monkeypatch):
    ancestor = tmp_path / "junction"
    real = Path.lstat

    def metadata(path, *args, **kwargs):
        if path == ancestor:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(store.ProviderStoreRootError) as caught:
        store.resolve_external_provider_root(ancestor / "new", project_root=project, create=True)
    assert caught.value.code == "provider_store_symlink_refused"
    assert not ancestor.exists()


def test_rejected_default_provider_route_is_sanitized_and_retryable(project, monkeypatch):
    from app.api.routes import providers

    home = project / "fictional-private-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(project))
    monkeypatch.delenv("NHFL_PROVIDER_STORE_ROOT", raising=False)
    app = FastAPI()
    app.include_router(providers.router, prefix="/api")

    @app.get("/synthetic-health")
    def health():
        return {"ok": True}

    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        for _ in range(2):
            response = client.get("/api/providers", headers={"X-User-Role": "reviewer"})
            assert response.status_code == 503
            assert response.json()["detail"] == {"error": "provider_storage_unavailable", "review_required": True}
            assert "fictional-private-profile" not in response.text
            assert client.get("/synthetic-health").status_code == 200
        # Recovery requires an actual safe external root, never a fallback.
        monkeypatch.setenv("NHFL_PROVIDER_STORE_ROOT", str(project.parent / "safe-providers"))
        response = client.get("/api/providers", headers={"X-User-Role": "reviewer"})
        assert response.status_code == 200, response.text
    assert not home.exists()


def test_storage_failure_does_not_bypass_request_guards(project, monkeypatch):
    from app.api.routes import providers

    def must_not_construct():
        raise AssertionError("request guards must run before provider store access")

    monkeypatch.setattr(providers, "_service", must_not_construct)
    app = FastAPI()
    app.include_router(providers.router, prefix="/api")
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as client:
        assert client.get("/api/providers").status_code == 403
        assert client.get("/api/providers", headers={"X-User-Role": "reviewer", "Origin": "https://untrusted.example"}).status_code == 403


def test_provider_router_import_never_creates_any_store(tmp_path):
    import subprocess
    import sys

    home = tmp_path / "private-profile"
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    env.pop("NHFL_PROVIDER_STORE_ROOT", None)
    result = subprocess.run(
        [sys.executable, "-B", "-c", "from app.api.routes import deliberation; "
         "assert deliberation.PROVIDER_SERVICE is None; "
         "from pathlib import Path; assert not (Path.home() / '.codex').exists()"],
        env=env, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not home.exists()


def test_lazy_provider_service_is_serialized_and_retryable(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.api.routes import deliberation
    from fastapi import HTTPException

    monkeypatch.setattr(deliberation, "PROVIDER_SERVICE", None)
    calls = []

    def rejected(**_kwargs):
        calls.append("rejected")
        raise store.ProviderStoreRootError("synthetic_denial", "private-path-not-for-browser")

    monkeypatch.setattr(deliberation, "ProviderConnectionService", rejected)
    for _ in range(2):
        with pytest.raises(HTTPException) as caught:
            deliberation._get_provider_service()
        assert caught.value.status_code == 503
        assert "private-path" not in str(caught.value.detail)
        assert deliberation.PROVIDER_SERVICE is None

    sentinel = object()

    def approved(**_kwargs):
        calls.append("approved")
        return sentinel

    monkeypatch.setattr(deliberation, "ProviderConnectionService", approved)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: deliberation._get_provider_service(), range(8)))
    assert all(result is sentinel for result in results)
    assert calls == ["rejected", "rejected", "approved"]


def test_existing_linked_store_child_is_refused(project, tmp_path):
    root = tmp_path / "safe-root"
    target = tmp_path / "separate-private-state"
    root.mkdir()
    target.mkdir()
    try:
        (root / "manifests").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(store.ProviderStoreRootError):
        store.external_provider_store_layout(root, project_root=project)
    assert not (root / "connections").exists()
    assert not list(target.iterdir())
