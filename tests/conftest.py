from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


@pytest.fixture(autouse=True)
def isolated_replay_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tests use different fictional encryption keys, never one shared registry.

    An inherited NHFL_IDEMPOTENCY_STATE_ROOT takes priority over the runtime root
    that individual tests configure. Keeping replay state test-owned prevents
    cross-test key collisions and accidental access to a developer's profile.
    A test may still explicitly override this root to exercise persistence.
    """
    monkeypatch.setenv("NHFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "replay-state"))


@pytest.fixture
def synthetic_source_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Give opted-in unit tests a source identity distinct from their data.

    Both directories remain test-owned under pytest's explicit basetemp. Only
    these tests change their current directory; production root validators are
    never replaced, disabled, or made permissive. This is a simulated layout,
    not evidence that real authority data may be stored in the source checkout.
    """
    project = tmp_path / "synthetic-source"
    project.mkdir()
    monkeypatch.chdir(project)
    return project


@pytest.fixture
def synthetic_authority_services(synthetic_source_project, monkeypatch):
    """Bind API service construction to the opted-in synthetic source tree."""
    from functools import partial
    from nh_family_law_llm import api

    constructor = api.AuthorityLibraryService
    monkeypatch.setattr(
        api, "AuthorityLibraryService",
        partial(constructor, repo_root=synthetic_source_project),
    )
    monkeypatch.setenv(
        "NH_FAMILY_LAW_DATA_ROOT",
        str(synthetic_source_project.parent / "synthetic-authority-data"),
    )
    return synthetic_source_project
