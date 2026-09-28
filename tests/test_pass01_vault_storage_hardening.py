"""Synthetic regressions for cross-process key creation and default-root validation.

Exercise the real repository modules and real OS lock/encryption operations.
All paths are owned by pytest; synthetic project identities keep boundary tests
inside the authorized dist workspace without relaxing production policy.
"""
from __future__ import annotations

import multiprocessing
import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from legal.deliberation import external_root as roots
from legal.security import durable_io, local_encryption as vault


def _key_path(root: Path) -> Path:
    return root / ("master-key.dpapi" if os.name == "nt" else "master-key.local")


def _key_worker(root, role, first_entered, second_boundary, release_first, first_done, results):
    """Force the former overwrite ordering without sleeps or copied source code."""
    os.environ["NHFL_VAULT_KEY_ROOT"] = root
    vault._VAULT_KEY_CACHE.clear()
    protect = vault._protect
    lock = durable_io.exclusive_file_lock

    def scheduled_protect(secret):
        if role == "first":
            first_entered.set()
            if not release_first.wait(20):
                raise TimeoutError("first writer was not released")
        else:
            # The old routine reaches this with the key still absent. The
            # repaired routine instead waits at the actual cross-process lock.
            second_boundary.set()
            if not first_done.wait(20):
                raise TimeoutError("first writer did not finish")
        return protect(secret)

    @contextmanager
    def observed_lock(path):
        if role == "second":
            second_boundary.set()
        with lock(path):
            yield

    vault._protect = scheduled_protect
    vault.exclusive_file_lock = observed_lock
    try:
        key = vault.default_matter_passphrase()
        if role == "first":
            first_done.set()
        blob = vault.LocalEnvelopeEncryptor(key).encrypt_json({"fictional_writer": role})
        results.put({"role": role, "key": key, "blob": blob})
    except Exception as exc:
        results.put({"role": role, "error": type(exc).__name__})
    finally:
        if role == "first":
            first_done.set()


@pytest.fixture
def vault_root(monkeypatch, tmp_path):
    root = tmp_path / "fictional-vault"
    monkeypatch.setenv("NHFL_VAULT_KEY_ROOT", str(root))
    monkeypatch.setattr(vault, "_VAULT_KEY_CACHE", {})
    return root


@pytest.mark.parametrize("iteration", range(3))
def test_concurrent_processes_share_key_and_decrypt_after_restart(vault_root, iteration):
    ctx = multiprocessing.get_context("spawn")
    first_entered, second_boundary = ctx.Event(), ctx.Event()
    release_first, first_done = ctx.Event(), ctx.Event()
    results = ctx.Queue()
    processes = [
        ctx.Process(target=_key_worker, args=(str(vault_root), role, first_entered,
                    second_boundary, release_first, first_done, results))
        for role in ("first", "second")
    ]
    try:
        processes[0].start()
        assert first_entered.wait(20), "first process did not reach key creation"
        processes[1].start()
        assert second_boundary.wait(20), "second process did not reach the race boundary"
        release_first.set()
        replies = [results.get(timeout=25), results.get(timeout=25)]
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        assert all("error" not in reply for reply in replies), replies
        # Parent has never loaded the key: this exercises an uncached restart
        # read with real DPAPI on Windows, file protection on other platforms.
        persisted_before = _key_path(vault_root).read_bytes()
        restarted_key = vault.default_matter_passphrase()
        assert all(reply["key"] == restarted_key for reply in replies)
        reader = vault.LocalEnvelopeEncryptor(restarted_key)
        for reply in replies:
            assert reader.decrypt_json(reply["blob"]) == {"fictional_writer": reply["role"]}
        assert _key_path(vault_root).read_bytes() == persisted_before
    finally:
        release_first.set()
        first_done.set()
        for process in processes:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=5)
                process.close()
        results.close()
        results.join_thread()


def test_vault_lock_failure_never_creates_key(monkeypatch, vault_root):
    @contextmanager
    def unavailable(_path):
        raise durable_io.DurableIOError("lock_timeout")
        yield  # pragma: no cover

    monkeypatch.setattr(vault, "exclusive_file_lock", unavailable, raising=False)
    with pytest.raises(durable_io.DurableIOError, match="lock_timeout"):
        vault.default_matter_passphrase()
    assert not _key_path(vault_root).exists()
    assert not vault._VAULT_KEY_CACHE


def test_invalid_unprotected_key_is_not_cached_or_replaced(monkeypatch, vault_root):
    vault_root.mkdir()
    path = _key_path(vault_root)
    original = b"fictional-protected-key-fixture"
    path.write_bytes(original)
    monkeypatch.setattr(vault, "_unprotect", lambda _raw: b"short")
    with pytest.raises(ValueError, match="master key is invalid"):
        vault.default_matter_passphrase()
    assert path.read_bytes() == original
    assert path not in vault._VAULT_KEY_CACHE


def test_failed_unlock_does_not_generate_or_replace_existing_key(monkeypatch, vault_root):
    vault.default_matter_passphrase()
    path = _key_path(vault_root)
    original = path.read_bytes()
    vault._VAULT_KEY_CACHE.clear()

    def unavailable(_raw):
        raise ValueError("synthetic unlock failure")

    def no_new_key(_length):
        raise AssertionError("an unreadable existing key must never be regenerated")

    monkeypatch.setattr(vault, "_unprotect", unavailable)
    monkeypatch.setattr(vault.secrets, "token_bytes", no_new_key)
    with pytest.raises(ValueError, match="synthetic unlock failure"):
        vault.default_matter_passphrase()
    assert path.read_bytes() == original
    assert not vault._VAULT_KEY_CACHE


def _symlink_or_skip(link: Path, target: Path, *, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable on this host: {exc.errno}")


def test_dangling_key_symlink_is_not_replaced(vault_root, tmp_path):
    vault_root.mkdir()
    path = _key_path(vault_root)
    _symlink_or_skip(path, tmp_path / "missing-key-target")
    with pytest.raises((durable_io.DurableIOError, ValueError)):
        vault.default_matter_passphrase()
    assert path.is_symlink()
    assert not path.exists()
    assert not vault._VAULT_KEY_CACHE


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "synthetic-project"
    root.mkdir()
    return root


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_default_inside_project_rejected_before_creation(monkeypatch, project, configured):
    home = project / "relocated-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(roots.DeliberationRootError) as error:
        roots.resolve_external_deliberation_root(configured, project_root=project, create=True)
    assert error.value.code == "external_root_inside_source_repo"
    assert not home.exists()


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_valid_default_uses_shared_validation(monkeypatch, tmp_path, project, configured):
    home = tmp_path / "synthetic-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    calls = []
    validate = roots._safe_external_root

    def observed(candidate, **kwargs):
        calls.append(kwargs)
        return validate(candidate, **kwargs)

    monkeypatch.setattr(roots, "_safe_external_root", observed)
    result = roots.resolve_external_deliberation_root(
        configured, project_root=project, create=True
    )
    assert result == home / ".codex" / "deliberation_store" / project.name
    assert result.is_dir()
    assert len(calls) == 1 and calls[0]["create"] is False
    assert calls[0]["repo_root"] == project.resolve()


@pytest.mark.parametrize("folder", ["ProgramData", "WindowsApps", "model_store", "staging"])
@pytest.mark.parametrize("use_default", [False, True])
def test_forbidden_roots_rejected_before_any_creation(
    monkeypatch, tmp_path, project, folder, use_default
):
    home = tmp_path / folder / "synthetic-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    configured = None if use_default else home / "deliberation"
    with pytest.raises(roots.DeliberationRootError) as error:
        roots.resolve_external_deliberation_root(configured, project_root=project, create=True)
    assert error.value.code == "deliberation_root_inside_forbidden_root"
    assert not (tmp_path / folder).exists()


@pytest.mark.parametrize("use_default", [False, True])
def test_linked_parent_is_rejected_before_creation(monkeypatch, tmp_path, project, use_default):
    target = tmp_path / "real-profile"
    target.mkdir()
    link = tmp_path / "linked-profile"
    _symlink_or_skip(link, target, directory=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: link))
    configured = None if use_default else link / "deliberation"
    with pytest.raises(roots.DeliberationRootError) as error:
        roots.resolve_external_deliberation_root(configured, project_root=project, create=True)
    assert error.value.code == "deliberation_root_symlink_refused"
    assert list(target.iterdir()) == []


def test_explicit_dangling_root_symlink_is_refused(tmp_path, project):
    link = tmp_path / "dangling-root"
    target = tmp_path / "missing-root"
    _symlink_or_skip(link, target, directory=True)
    with pytest.raises(roots.DeliberationRootError) as error:
        roots.resolve_external_deliberation_root(link, project_root=project, create=True)
    assert error.value.code == "deliberation_root_symlink_refused"
    assert link.is_symlink() and not target.exists()


def test_valid_explicit_root_without_create_is_read_only(tmp_path, project):
    root = tmp_path / "synthetic-output"
    assert roots.resolve_external_deliberation_root(root, project_root=project) == root
    assert not root.exists()
