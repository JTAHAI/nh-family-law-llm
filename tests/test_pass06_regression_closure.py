"""Pass 06 regression closure for executable defects and boundary precedence.

All paths and records are synthetic. These tests do not qualify legal content,
release evidence, an MSIX, or a production environment.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from legal.evals.external_eval_root import ExternalEvalRootError, resolve_external_eval_root
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.productivity import ProductivitySuiteStore
from legal.runtime.warm_model_pool import WarmModelPoolStore

ROOT = Path(__file__).resolve().parents[1]


class _ReleasableWorker:
    supports_explicit_release = True

    def __init__(self) -> None:
        self.warm_calls = 0

    def warm(self):
        self.warm_calls += 1
        return {"provider_id": "synthetic", "model_id": "fictional_local_model"}

    def release(self):
        return {"released": True}


class _UnreleasableWorker:
    supports_explicit_release = False


def _admitted_model() -> dict[str, str]:
    return {
        "model_id": "fictional_local_model",
        "installation_status": "admitted_for_task_review_required",
    }


def test_warm_pool_reports_structural_prerequisites_before_transient_pressure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from legal.runtime import warm_model_pool as module

    monkeypatch.setattr(
        module,
        "profile_hardware",
        lambda _root: type(
            "Hardware",
            (),
            {"as_dict": lambda self: {"available_memory_bytes": 1024, "available_vram_bytes": 0}},
        )(),
    )
    root = tmp_path / "matter"
    root.mkdir()
    store = WarmModelPoolStore(root, encryption_key="fictional-test-key")

    no_model = store.warm(
        {"task": "summarization", "user_confirmed": True}, model=None, worker=None
    )
    assert no_model["status"] == "not_warmed_no_task_admission_review_required"

    no_release = store.warm(
        {"task": "summarization", "user_confirmed": True},
        model=_admitted_model(),
        worker=_UnreleasableWorker(),
    )
    assert no_release["status"] == "not_warmed_release_capability_missing_review_required"

    worker = _ReleasableWorker()
    pressured = store.warm(
        {"task": "summarization", "user_confirmed": True},
        model=_admitted_model(),
        worker=worker,
    )
    assert pressured["status"] == "not_warmed_pressure_review_required"
    assert pressured["pressure"]["release_required"] is True
    assert worker.warm_calls == 0


def test_warm_pool_still_validates_thermal_input_before_admission(tmp_path: Path) -> None:
    root = tmp_path / "matter"
    root.mkdir()
    store = WarmModelPoolStore(root, encryption_key="fictional-test-key")
    with pytest.raises(IntakeWorkbenchError, match="warm_model_pool_thermal_state_invalid"):
        store.warm(
            {"task": "summarization", "thermal_state": "fictional", "user_confirmed": True},
            model=None,
            worker=None,
        )


def test_incremental_backup_accepts_and_restores_zero_byte_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matter = tmp_path / "matter"
    matter.mkdir()
    (matter / "empty.txt").write_bytes(b"")
    (matter / "record.txt").write_text("fictional backup content", encoding="utf-8")
    backup_root = tmp_path / "backups"
    monkeypatch.setenv("NH_MATTER_STORE_KEY", "fictional-backup-key")
    monkeypatch.setenv("NHFL_BACKUP_ROOT", str(backup_root))

    store = ProductivitySuiteStore(matter)
    store.save_backup_schedule(
        {"schedule_id": "daily_backup", "enabled": True, "retention_count": 2}
    )
    receipt = store.run_backup({"schedule_id": "daily_backup"})
    assert receipt["verified"] is True
    assert store.verify_backup(receipt["backup_id"])["status"] == "pass"

    restored = store.restore_backup(receipt["backup_id"], {"confirmed": True})
    assert restored["status"] == "restored_to_separate_recovery_directory"
    assert (backup_root / "recovery" / receipt["backup_id"] / "empty.txt").read_bytes() == b""


def test_incremental_backup_rejects_boolean_or_text_file_sizes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matter = tmp_path / "matter"
    matter.mkdir()
    backup_root = tmp_path / "backups"
    monkeypatch.setenv("NH_MATTER_STORE_KEY", "fictional-backup-key")
    monkeypatch.setenv("NHFL_BACKUP_ROOT", str(backup_root))
    store = ProductivitySuiteStore(matter)
    digest, _ = store._store_backup_chunk(backup_root, b"")
    base = {
        "schema_version": "encrypted_matter_backup_v2",
        "matter_scope": store.scope,
        "file_count": 1,
        "files": [{"path": "empty.txt", "sha256": digest, "size": 0, "chunks": [digest]}],
    }
    assert store._verify_incremental_package(backup_root, base)["status"] == "pass"
    for invalid in (True, "0"):
        payload = {**base, "files": [{**base["files"][0], "size": invalid}]}
        report = store._verify_incremental_package(backup_root, payload)
        assert report["status"] == "blocked"
        assert "backup_manifest_file_size_invalid" in report["blockers"]


def test_external_eval_root_does_not_reverse_match_harmless_path_components(
    synthetic_source_project: Path
) -> None:
    # The enclosing environment deliberately contains a component named
    # "data". It must not be treated as Windows ProgramData.
    candidate = synthetic_source_project.parent / "data" / "external-evals"
    resolved = resolve_external_eval_root(
        candidate, project_root=synthetic_source_project, create=False
    )
    assert resolved == candidate.resolve()
    assert not candidate.exists()


def test_external_eval_root_still_rejects_source_and_protected_directories(
    synthetic_source_project: Path
) -> None:
    with pytest.raises(ExternalEvalRootError) as source_error:
        resolve_external_eval_root(
            synthetic_source_project / "evals",
            project_root=synthetic_source_project,
            create=False,
        )
    assert source_error.value.code == "external_root_inside_source_repo"
    with pytest.raises(ExternalEvalRootError) as caught:
        resolve_external_eval_root(
            synthetic_source_project.parent / "ProgramData" / "evals",
            project_root=synthetic_source_project,
            create=False,
        )
    assert caught.value.code == "external_eval_root_inside_forbidden_root"


def test_production_release_controls_honor_explicit_project_identity(
    monkeypatch: pytest.MonkeyPatch, synthetic_repo_copy: Path
) -> None:
    from app.api import production

    monkeypatch.setenv("NHFL_PROJECT_ROOT", str(synthetic_repo_copy))
    assert production._project_root() == synthetic_repo_copy.resolve()


def test_real_source_tree_boundary_remains_fail_closed() -> None:
    candidate = ROOT / "dist" / "pass06" / "must-not-be-eval-data"
    with pytest.raises(ExternalEvalRootError) as caught:
        resolve_external_eval_root(candidate, project_root=ROOT, create=False)
    assert caught.value.code == "external_root_inside_source_repo"
    assert not candidate.exists()
