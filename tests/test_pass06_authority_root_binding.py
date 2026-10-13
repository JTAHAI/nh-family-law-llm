"""Explicit source identity must control authority-store validation.

These tests use fictional paths only.  They prove that a caller-supplied source
root is honored without creating a bypass for stores inside that source tree.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.authority_library_service import AuthorityLibraryService

ROOT = Path(__file__).resolve().parents[1]


def test_explicit_repo_root_allows_only_its_external_sibling(tmp_path: Path) -> None:
    project = tmp_path / "synthetic-source"
    project.mkdir()
    data_root = tmp_path / "synthetic-authority-data"

    service = AuthorityLibraryService(data_root=data_root, repo_root=project)

    assert service.repo_root == project.resolve()
    assert service.data_root == data_root.resolve()
    assert not data_root.exists()


def test_explicit_repo_root_still_rejects_store_inside_source(tmp_path: Path) -> None:
    project = tmp_path / "synthetic-source"
    project.mkdir()
    forbidden = project / "authority-data"

    with pytest.raises(ValueError, match="outside the source repository"):
        AuthorityLibraryService(data_root=forbidden, repo_root=project)

    assert not forbidden.exists()


def test_fixture_directory_defaults_from_explicit_source_identity(tmp_path: Path) -> None:
    project = tmp_path / "synthetic-source"
    project.mkdir()
    service = AuthorityLibraryService(
        data_root=tmp_path / "synthetic-authority-data",
        repo_root=project,
    )
    assert service.fixture_dir == project.resolve() / "data" / "fixtures"


def test_default_source_identity_does_not_accept_checkout_data_root() -> None:
    forbidden = ROOT / "dist" / "pass06" / "must-remain-external"
    with pytest.raises(ValueError, match="outside the source repository"):
        AuthorityLibraryService(data_root=forbidden)
    assert not forbidden.exists()


def test_default_constructor_honors_explicit_project_identity(
    monkeypatch, synthetic_source_project: Path
) -> None:
    external = synthetic_source_project.parent / "authority-data"
    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(synthetic_source_project))
    monkeypatch.setenv("NHFL_AUTHORITY_DATA_ROOT", str(external))
    service = AuthorityLibraryService()
    assert service.repo_root == synthetic_source_project.resolve()
    assert service.data_root == external.resolve()
    assert not external.exists()
