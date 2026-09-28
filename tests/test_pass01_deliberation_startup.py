"""Keep a refused deliberation store from taking down unrelated local routes."""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def test_router_import_does_not_open_default_deliberation_store(tmp_path):
    home = tmp_path / "fictional-home"
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    code = (
        "from app.api.routes import deliberation; "
        "assert deliberation.HOST is None; "
        "from pathlib import Path; "
        "assert not (Path.home() / '.codex' / 'deliberation_store').exists()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env,
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_rejected_default_returns_safe_503_without_breaking_unrelated_route(monkeypatch, tmp_path):
    from app.api.routes import deliberation

    home = tmp_path / "fictional-private-home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(deliberation, "HOST", None)
    app = FastAPI()
    app.include_router(deliberation.router, prefix="/api")

    @app.get("/synthetic-health")
    def health():
        return {"status": "ok"}

    with TestClient(app) as client:
        assert client.get("/synthetic-health").status_code == 200
        for _ in range(2):
            response = client.get("/api/deliberation/presets")
            assert response.status_code == 503
            assert response.json()["detail"] == {
                "error": "deliberation_storage_unavailable", "review_required": True,
            }
            assert str(tmp_path) not in response.text
        assert client.get("/synthetic-health").status_code == 200
    assert deliberation.HOST is None
    assert not (home / ".codex" / "deliberation_store").exists()


def test_lazy_host_serializes_first_use_and_preserves_injected_host(monkeypatch, tmp_path):
    from app.api.routes import deliberation
    from legal.deliberation.host import DeliberationHost

    project = tmp_path / "synthetic-project"
    project.mkdir()
    made = []

    def build(*, project_root):
        host = DeliberationHost(project_root=project, root=tmp_path / "safe-store")
        made.append(host)
        return host

    monkeypatch.setattr(deliberation, "HOST", None)
    monkeypatch.setattr(deliberation, "DeliberationHost", build)
    with ThreadPoolExecutor(max_workers=8) as pool:
        hosts = list(pool.map(lambda _: deliberation._get_host(), range(8)))
    assert len(made) == 1
    assert all(host is made[0] for host in hosts)
    assert deliberation._get_host() is made[0]
    assert made[0].list_presets()


def test_failed_initialization_remains_retryable_and_does_not_leak_paths(monkeypatch):
    from app.api.routes import deliberation
    from fastapi import HTTPException

    monkeypatch.setattr(deliberation, "HOST", None)
    calls = []

    def unavailable(*, project_root):
        calls.append(project_root)
        raise OSError("synthetic secret filesystem path")

    monkeypatch.setattr(deliberation, "DeliberationHost", unavailable)
    for _ in range(2):
        with pytest.raises(HTTPException) as caught:
            deliberation._get_host()
        assert caught.value.status_code == 503
        assert "secret" not in str(caught.value.detail)
        assert deliberation.HOST is None
    assert len(calls) == 2
