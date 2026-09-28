"""The publication candidate is exact; ignored fixtures are never deleted."""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal.release import index_preflight as gate

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args, data=None):
    return subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True, check=True).stdout


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "synthetic-checkout"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    spec = importlib.util.spec_from_file_location("index_test_doctor", ROOT / "scripts/doctor-local-repo.py")
    doctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doctor)
    for name in doctor.REQUIRED_PUBLIC_REPO_FILES:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("# synthetic public file\n", encoding="utf-8")
    (root / ".gitignore").write_text("dist/\n*.egg-info/\n", encoding="utf-8")
    (root / "source.py").write_text("# staged-public-source\n", encoding="utf-8")
    git(root, "add", ".")

    def inspect(snapshot):
        report = doctor.scan(snapshot)
        return SimpleNamespace(as_dict=lambda: {
            "status": report["status"], "checks": [{"name": "real_local_doctor", "status": report["status"]}],
            "blockers": report["forbidden_paths"],
        })

    monkeypatch.setattr(gate, "run_pre_push_gate", inspect)
    return root


def test_ignored_artifacts_are_preserved_but_never_exported(source, monkeypatch):
    sentinel = source / "dist" / "models" / "keep.safetensors"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"fictional-ignored-artifact")
    index_before = (source / ".git/index").read_bytes()
    inspect = gate.run_pre_push_gate

    def no_artifact_in_candidate(snapshot):
        assert not (snapshot / "dist").exists()
        return inspect(snapshot)

    monkeypatch.setattr(gate, "run_pre_push_gate", no_artifact_in_candidate)
    result = gate.audit_index_source(source)
    assert result["status"] == "pass", result
    assert result["safe_to_push"] and result["index_unchanged"]
    assert not result["production_legal_ready"] and not result["worktree_audited"]
    assert sentinel.read_bytes() == b"fictional-ignored-artifact"
    assert (source / ".git/index").read_bytes() == index_before
    assert not list((source / "dist/index-preflight").iterdir())


def test_forced_ignored_dist_content_remains_a_blocker(source):
    sentinel = source / "dist" / "forced.txt"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"fictional-force-staged")
    git(source, "add", "-f", "dist/forced.txt")
    result = gate.audit_index_source(source)
    assert result["status"] == "fail" and not result["safe_to_push"]
    assert "dist" in result["blockers"]
    assert sentinel.read_bytes() == b"fictional-force-staged"


def test_export_ignore_cannot_hide_staged_artifacts(source):
    (source / ".gitattributes").write_text("private.pdf export-ignore\n", encoding="utf-8")
    (source / "private.pdf").write_bytes(b"%PDF-fictional-not-real-records")
    git(source, "add", ".gitattributes", "private.pdf")
    result = gate.audit_index_source(source)
    assert result["status"] == "fail"
    assert "private.pdf" in result["blockers"]


def test_staged_bytes_not_unstaged_worktree_bytes_are_audited(source, monkeypatch):
    inspect = gate.run_pre_push_gate
    (source / "source.py").write_text("# unstaged-other-source\n", encoding="utf-8")

    def exact(snapshot):
        assert (snapshot / "source.py").read_text() == "# staged-public-source\n"
        return inspect(snapshot)

    monkeypatch.setattr(gate, "run_pre_push_gate", exact)
    result = gate.audit_index_source(source)
    assert result["status"] == "pass"
    assert (source / "source.py").read_text() == "# unstaged-other-source\n"


def test_index_changes_during_audit_invalidate_receipt(source, monkeypatch):
    inspect = gate.run_pre_push_gate

    def changes(snapshot):
        report = inspect(snapshot)
        (source / "later.py").write_text("# staged-during-audit\n", encoding="utf-8")
        git(source, "add", "later.py")
        return report

    monkeypatch.setattr(gate, "run_pre_push_gate", changes)
    result = gate.audit_index_source(source)
    assert not result["index_unchanged"] and not result["safe_to_push"]
    assert "index_changed_during_audit" in result["blockers"]


@pytest.mark.parametrize("mode", ["120000", "160000"])
def test_symlinks_and_submodules_are_never_materialized(source, mode):
    oid = git(source, "hash-object", "-w", "--stdin", data=b"../fictional-target").decode().strip()
    if mode == "160000":
        tree = git(source, "write-tree").decode().strip()
        env = dict(os.environ, GIT_AUTHOR_NAME="Synthetic", GIT_AUTHOR_EMAIL="test@example.invalid",
                   GIT_COMMITTER_NAME="Synthetic", GIT_COMMITTER_EMAIL="test@example.invalid")
        oid = subprocess.check_output(["git", "-C", str(source), "commit-tree", tree, "-m", "synthetic"], env=env).decode().strip()
    git(source, "update-index", "--add", "--cacheinfo", f"{mode},{oid},linked")
    result = gate.audit_index_source(source)
    assert result["status"] == "fail"
    assert not (source / "dist/index-preflight").exists()


def test_no_git_repository_has_no_worktree_fallback(tmp_path):
    root = tmp_path / "not-a-checkout"
    root.mkdir()
    result = gate.audit_index_source(root)
    assert result["status"] == "fail" and not result["safe_to_push"]
    assert not (root / "dist").exists()


def test_subdirectory_cannot_accidentally_audit_ancestor_repository(source):
    child = source / "child"
    child.mkdir()
    result = gate.audit_index_source(child)
    assert result["blockers"] == ["exact_repository_root_required"]
    assert not (child / "dist").exists()


def test_snapshot_limit_fails_without_creating_workspace(source, monkeypatch):
    monkeypatch.setattr(gate, "MAX_SOURCE_BYTES", 1)
    result = gate.audit_index_source(source)
    assert result["blockers"] == ["index_snapshot_limit_exceeded"]
    assert not (source / "dist").exists()


def test_linked_snapshot_workspace_is_refused(source, tmp_path):
    target = tmp_path / "outside-ignored-data"
    target.mkdir()
    try:
        (source / "dist").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    result = gate.audit_index_source(source)
    assert result["blockers"] == ["snapshot_workspace_link_refused"]
    assert not list(target.iterdir())


def test_failed_audit_cleans_only_its_fresh_snapshot(source, monkeypatch):
    sentinel = source / "dist" / "keep.bin"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"synthetic-preserved")

    def fails(_snapshot):
        raise ValueError("fictional-secret-location")

    monkeypatch.setattr(gate, "run_pre_push_gate", fails)
    result = gate.audit_index_source(source)
    assert result["status"] == "fail"
    assert "fictional-secret-location" not in str(result)
    assert sentinel.read_bytes() == b"synthetic-preserved"
    assert not list((source / "dist/index-preflight").iterdir())


def test_corrupted_batch_response_never_gets_a_receipt(source, monkeypatch):
    real = gate._git

    def corrupt(root, *args, **kwargs):
        data = real(root, *args, **kwargs)
        if "cat-file" in args:
            data = data.replace(b"staged-public-source", b"staged-tamper-source")
        return data

    monkeypatch.setattr(gate, "_git", corrupt)
    result = gate.audit_index_source(source)
    assert result["status"] == "fail"
    assert "index_blob_digest_mismatch" in result["blockers"]


@pytest.mark.parametrize("folder", ["__pycache__", ".pytest_cache", ".ruff_cache", "sample.egg-info", "node_modules"])
def test_force_added_pruned_directories_cannot_hide_content(source, folder):
    path = source / folder / "synthetic.json"
    path.parent.mkdir()
    path.write_text("{}", encoding="utf-8")
    git(source, "add", "-f", str(path.relative_to(source)))
    result = gate.audit_index_source(source)
    assert result["blockers"] == ["index_generated_path_refused"]
    assert path.exists()


def test_allowed_evidence_directory_is_not_exempt_from_secret_scan(source):
    path = source / "artifacts/pass-08/fictional.json"
    path.parent.mkdir(parents=True)
    # Build the synthetic credential literal dynamically, not in public source.
    path.write_text('password = "' + "fictional" * 3 + '"', encoding="utf-8")
    git(source, "add", "artifacts")
    result = gate.audit_index_source(source)
    assert result["blockers"] == ["index_possible_literal_secret"]
    assert "fictionalfictional" not in str(result)


def test_receipt_tree_matches_git_write_tree_without_modifying_original_index(source):
    before = (source / ".git/index").read_bytes()
    result = gate.audit_index_source(source)
    assert (source / ".git/index").read_bytes() == before
    expected = git(source, "write-tree").decode().strip()
    assert result["index_tree_sha"] == expected


def test_intent_to_add_has_no_misleading_tree_receipt(source):
    path = source / "not-staged.py"
    path.write_text("# synthetic intent to add\n", encoding="utf-8")
    git(source, "add", "-N", "not-staged.py")
    before = (source / ".git/index").read_bytes()
    result = gate.audit_index_source(source)
    assert result["blockers"] == ["intent_to_add_index_refused"]
    assert not result["safe_to_push"]
    assert (source / ".git/index").read_bytes() == before


def test_tree_identity_matches_for_unicode_executable_and_prefix_names(source):
    for name in ["folder.py", "folder/a.py", "unicod\u00e9/nh.py", "prefix-name/child.py"]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic public source\n", encoding="utf-8")
        git(source, "add", name)
    git(source, "update-index", "--chmod=+x", "folder.py")
    before = (source / ".git/index").read_bytes()
    result = gate.audit_index_source(source)
    assert result["status"] == "pass", result
    assert (source / ".git/index").read_bytes() == before
    assert result["index_tree_sha"] == git(source, "write-tree").decode().strip()
