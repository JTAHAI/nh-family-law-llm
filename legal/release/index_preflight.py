"""Audit the exact staged source tree without erasing ignored working artifacts.

The ordinary worktree audit remains strict. This separate mode checks every
blob in the Git index, including force-added ignored files. It never stages,
commits, pushes, or cleans the caller's files. A receipt approves one tree ID,
not an arbitrary later working tree, release package, or legal workflow.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from legal.release.pre_push_gate import run_pre_push_gate
from legal.release.public_repo_readiness import SECRET_VALUE_RE

# Worktree walkers prune these directories; an index audit must instead
# reject them when force-staged. Ignoring them here could hide published data.
_INDEX_GENERATED_COMPONENTS = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv",
    "venv", "node_modules", ".eggs", ".proofs", ".nhfl_work", "build",
}
_TEXT_SUFFIXES = {".py", ".ps1", ".sh", ".md", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".txt"}
_WINDOWS_DEVICE = re.compile(r"(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$")

MAX_SOURCE_FILES = 10_000
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_BLOB_BYTES = 32 * 1024 * 1024
_HASH = re.compile(r"[a-f0-9]{40}|[a-f0-9]{64}")


class IndexPreflightError(ValueError):
    """A bounded, non-secret error code suitable for a failed receipt."""


def _git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], input=data, capture_output=True,
            check=False, timeout=60,
            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
                     GIT_NO_LAZY_FETCH="1"),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IndexPreflightError("git_unavailable_or_timed_out") from exc
    if result.returncode != 0:
        # Git stderr can contain private paths and credential-helper output.
        raise IndexPreflightError("git_index_operation_failed")
    return result.stdout


def _tree(root: Path) -> str:
    # write-tree refreshes the caller's index cache even with optional locks
    # disabled. Build tree objects from a read-only index listing instead.
    diff_args = ("diff", "--cached", "--raw", "-z", "--no-ext-diff", "--no-textconv", "--no-renames")
    if _git(root, *diff_args, "--ita-visible-in-index") != _git(root, *diff_args, "--ita-invisible-in-index"):
        raise IndexPreflightError("intent_to_add_index_refused")
    raw = _git(root, "ls-files", "--stage", "-z")
    if len(raw) > 8 * 1024 * 1024:
        raise IndexPreflightError("index_listing_limit_exceeded")
    algorithm = _git(root, "rev-parse", "--show-object-format").decode("ascii").strip()
    if algorithm not in {"sha1", "sha256"}:
        raise IndexPreflightError("git_object_format_unsupported")
    nested: dict = {}
    count = 0
    for row in raw.split(b"\0"):
        if not row:
            continue
        metadata, name = row.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        if stage != b"0":
            raise IndexPreflightError("unmerged_index_refused")
        parts = name.split(b"/")
        if any(part in {b"", b".", b".."} for part in parts):
            raise IndexPreflightError("index_path_or_mode_unsafe")
        node = nested
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = (mode, oid)
        count += 1
        if count > MAX_SOURCE_FILES:
            raise IndexPreflightError("index_snapshot_limit_exceeded")
    batches: list[bytes] = []
    expected: list[str] = []

    def tree_for(node: dict) -> str:
        body = bytearray()
        commands = bytearray()
        for name, value in sorted(node.items(), key=lambda item: item[0] + (b"/" if isinstance(item[1], dict) else b"")):
            if isinstance(value, dict):
                mode, oid, kind = b"40000", tree_for(value).encode("ascii"), b"tree"
            else:
                mode, oid = value
                kind = b"commit" if mode == b"160000" else b"blob"
            body.extend(mode + b" " + name + b"\0" + bytes.fromhex(oid.decode("ascii")))
            commands.extend(mode + b" " + kind + b" " + oid + b"\t" + name + b"\0")
        digest = hashlib.new(algorithm, f"tree {len(body)}\0".encode("ascii") + body).hexdigest()
        batches.append(bytes(commands) + b"\0")
        expected.append(digest)
        return digest

    value = tree_for(nested)
    actual = _git(root, "mktree", "--batch", "-z", data=b"".join(batches)).decode("ascii").splitlines()
    if actual != expected:
        raise IndexPreflightError("git_tree_id_mismatch")
    return value


def _entries(root: Path, tree: str) -> list[tuple[str, str, str, int]]:
    rows = _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", tree).split(b"\0")
    entries: list[tuple[str, str, str, int]] = []
    total = 0
    seen: set[str] = set()
    for row in rows:
        if not row:
            continue
        try:
            metadata, raw_path = row.split(b"\t", 1)
            mode, kind, oid, raw_size = metadata.decode("ascii").split()
            name = raw_path.decode("utf-8")
            size = int(raw_size)
        except (ValueError, UnicodeError) as exc:
            raise IndexPreflightError("index_entry_invalid_or_unsupported") from exc
        path = PurePosixPath(name)
        # Also reject Windows aliases, ADS, dot directories and control bytes
        # when auditing on Linux: the same tree must be safe on either host.
        parts = name.split("/")
        if (mode not in {"100644", "100755"} or kind != "blob"
                or not _HASH.fullmatch(oid) or path.is_absolute()
                or "\\" in name or ":" in name
                or any(ord(char) < 32 or ord(char) == 127 for char in name)
                or any(part in {"", ".", ".."} or part.casefold() == ".git"
                       or part.rstrip(" .") != part for part in parts)):
            raise IndexPreflightError("index_path_or_mode_unsafe")
        if any(_WINDOWS_DEVICE.fullmatch(part) for part in parts):
            raise IndexPreflightError("index_windows_device_path_refused")
        if any(part.casefold() in _INDEX_GENERATED_COMPONENTS or part.casefold().endswith(".egg-info") for part in parts):
            raise IndexPreflightError("index_generated_path_refused")
        if path.suffix.lower() in {".pyc", ".pyo", ".pfx", ".p12", ".pvk", ".snk"}:
            raise IndexPreflightError("index_generated_or_key_file_refused")
        folded = name.casefold()
        if folded in seen:
            raise IndexPreflightError("index_case_collision")
        seen.add(folded)
        total += size
        entries.append((mode, oid, name, size))
        if size < 0 or size > MAX_BLOB_BYTES or total > MAX_SOURCE_BYTES or len(entries) > MAX_SOURCE_FILES:
            raise IndexPreflightError("index_snapshot_limit_exceeded")
    if not entries:
        raise IndexPreflightError("index_source_empty")
    return entries


def _reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise IndexPreflightError("snapshot_workspace_link_refused")


def _materialize(root: Path, destination: Path, entries: list[tuple[str, str, str, int]]) -> None:
    # Batch reads avoid one subprocess per file on Windows. The size budget
    # above bounds the output. No archive/export-ignore rules can hide a blob.
    requested = b"".join(oid.encode("ascii") + b"\n" for _, oid, _, _ in entries)
    raw = _git(root, "cat-file", "--batch", data=requested)
    cursor = 0
    for mode, oid, name, size in entries:
        end = raw.find(b"\n", cursor)
        if end < 0 or raw[cursor:end] != f"{oid} blob {size}".encode("ascii"):
            raise IndexPreflightError("index_blob_header_mismatch")
        cursor = end + 1
        content = raw[cursor:cursor + size]
        if len(content) != size or raw[cursor + size:cursor + size + 1] != b"\n":
            raise IndexPreflightError("index_blob_truncated")
        digest = hashlib.new("sha1" if len(oid) == 40 else "sha256")
        digest.update(f"blob {size}\0".encode("ascii"))
        digest.update(content)
        if digest.hexdigest() != oid:
            raise IndexPreflightError("index_blob_digest_mismatch")
        # Do not exempt previously allowlisted evidence directories from the
        # secret scan merely because worktree walkers ordinarily prune them.
        if PurePosixPath(name).suffix.lower() in _TEXT_SUFFIXES and SECRET_VALUE_RE.search(content.decode("utf-8", errors="ignore")):
            raise IndexPreflightError("index_possible_literal_secret")
        cursor += size + 1
        path = destination.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(content)
        os.chmod(path, 0o755 if mode == "100755" else 0o644)
    if cursor != len(raw):
        raise IndexPreflightError("index_blob_trailing_data")


def audit_index_source(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).absolute()
    result: dict[str, Any] = {
        "schema": "nhfl.index_source_preflight.v1",
        "scope": "exact_git_index_tree",
        "status": "fail", "safe_to_push": False,
        "production_legal_ready": False,
        "index_tree_sha": None, "source_file_count": 0, "source_bytes": 0,
        "worktree_audited": False, "ignored_artifacts_modified": False,
        "index_unchanged": False, "checks": [], "blockers": [],
        "interpretation": "Source-hygiene approval applies only to index_tree_sha. "
                          "It is not full-test, MSIX, authority or legal-review qualification.",
    }
    try:
        _reject_links(root)
        actual = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
        if actual != root.resolve():
            raise IndexPreflightError("exact_repository_root_required")
        tree = _tree(root)
        result["index_tree_sha"] = tree
        entries = _entries(root, tree)
        result["source_file_count"] = len(entries)
        result["source_bytes"] = sum(row[3] for row in entries)
        owned = root / "dist" / "index-preflight"
        _reject_links(owned)
        owned.mkdir(parents=True, exist_ok=True)
        # Only this fresh per-call directory is deleted. Never clean dist or
        # a caller-supplied artifact path to make a hygiene check pass.
        with tempfile.TemporaryDirectory(prefix="candidate-", dir=owned) as directory:
            snapshot = Path(directory)
            _materialize(root, snapshot, entries)
            audited = run_pre_push_gate(snapshot).as_dict()
            result["checks"] = audited["checks"]
            result["blockers"] = list(audited["blockers"])
            result["index_unchanged"] = _tree(root) == tree
            if not result["index_unchanged"]:
                result["blockers"].append("index_changed_during_audit")
            if audited["status"] == "pass" and not result["blockers"]:
                result["status"] = "pass"
                result["safe_to_push"] = True
    except IndexPreflightError as exc:
        result["blockers"].append(str(exc))
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        # Missing policy, invalid JSON and cleanup failures all fail closed.
        result["blockers"].append(f"index_audit_failed:{type(exc).__name__}")
    return result
