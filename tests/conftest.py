from __future__ import annotations

import shutil
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
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(project))
    return project


@pytest.fixture(scope="session")
def synthetic_repo_copy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the tracked-style source tree for audits that require a full checkout.

    The real test basetemp must remain under ``dist`` per AGENTS.md, while the
    production guards correctly reject data stores beneath the source root.
    A single session-owned source copy lets those audits exercise their real
    policies with sibling synthetic data roots.  Generated artifacts, Git
    metadata, release evidence, and caches are deliberately not copied.
    """

    parent = tmp_path_factory.mktemp("synthetic-full-source")
    project = parent / "source"
    shutil.copytree(
        ROOT,
        project,
        ignore=shutil.ignore_patterns(
            ".git",
            "dist",
            "artifacts",
            "build",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
            ".venv",
            "*.egg-info",
        ),
    )
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


@pytest.fixture
def synthetic_authority_context(synthetic_repo_copy, monkeypatch, tmp_path):
    """Opted-in API tests keep real service guards and a complete source identity.

    Only fictional data is used. Source files are copied once per session; the
    sibling data store cannot appear inside that synthetic source directory.
    The real process cwd remains unchanged for source/UI contract checks.
    """
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(synthetic_repo_copy))
    monkeypatch.setenv("NH_FAMILY_LAW_DATA_ROOT", str(tmp_path / "authority-data"))
    return synthetic_repo_copy
