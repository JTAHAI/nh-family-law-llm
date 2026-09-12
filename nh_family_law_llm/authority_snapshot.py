"""Load and enforce the promoted New Hampshire authority snapshot manifest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from typing import Any, Iterable

CURRENT_STATUS = "current_verified"
MANIFEST_ENVIRONMENT_VARIABLE = "NHFL_AUTHORITY_MANIFEST"


@dataclass(frozen=True, slots=True)
class AuthorityRecord:
    authority_id: str
    citation: str
    status: str
    effective_date: str | None
    retrieval_eligible: bool
    local_filename: str | None
    sha256: str | None
    retrieval_scope: str
    answer_scope: str
    raw_source_bytes_preserved: bool
    extract_is_verbatim: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuthorityRecord":
        return cls(
            authority_id=str(payload.get("authority_id", "")),
            citation=str(payload.get("citation", "")),
            status=str(payload.get("status", "")),
            effective_date=payload.get("effective_date"),
            retrieval_eligible=payload.get("retrieval_eligible") is True,
            local_filename=payload.get("local_filename"),
            sha256=payload.get("sha256"),
            retrieval_scope=str(payload.get("retrieval_scope", "")),
            answer_scope=str(payload.get("answer_scope", "substantive_section_scope")),
            raw_source_bytes_preserved=payload.get("raw_source_bytes_preserved") is True,
            extract_is_verbatim=payload.get("extract_is_verbatim") is True,
        )

    def is_active(self, as_of: date) -> bool:
        """Return whether this record is explicitly reviewed and active as of a date."""
        if self.status != CURRENT_STATUS or not self.retrieval_eligible:
            return False
        if not self.effective_date:
            return False
        try:
            return date.fromisoformat(self.effective_date) <= as_of
        except (TypeError, ValueError):
            return False


def _candidate_manifest_paths() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get(MANIFEST_ENVIRONMENT_VARIABLE)
    if explicit:
        candidates.append(Path(explicit).expanduser())

    module = Path(__file__).resolve()
    # Recognize only the direct source checkout, never arbitrary ancestors.
    # A wheel installed under repo/dist must not borrow its parent checkout's law.
    package_parent = module.parent.parent
    checkout = package_parent.parent if package_parent.name == "src" else package_parent
    if (checkout / "pyproject.toml").is_file() and (checkout / "src" / "nh_family_law_llm").is_dir():
        candidates.append(checkout / "corpus" / "manifest" / "nh_authorities.json")

    candidates.append(
        module.parent
        / "data"
        / "authority_snapshot"
        / "manifest"
        / "nh_authorities.json"
    )
    # Preserve order while removing duplicate paths.
    return list(dict.fromkeys(path.resolve() for path in candidates))


def default_manifest_path() -> Path:
    """Find a repository manifest or the packaged embedded snapshot.

    ``NHFL_AUTHORITY_MANIFEST`` has first priority. A configured but missing
    path fails closed rather than silently using a different corpus.
    """
    explicit = os.environ.get(MANIFEST_ENVIRONMENT_VARIABLE)
    if explicit:
        configured = Path(explicit).expanduser().resolve()
        if not configured.is_file():
            raise FileNotFoundError(
                f"{MANIFEST_ENVIRONMENT_VARIABLE} does not identify a file: {configured}"
            )
        return configured

    candidates = _candidate_manifest_paths()
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    attempted = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"No NH authority manifest was found. Tried:\n{attempted}")


def load_payload(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path).resolve() if path else default_manifest_path()
    if target.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("NH authority manifest exceeds the size limit")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("NH authority manifest must be an object")
    if payload.get("as_of_date") is None or not isinstance(payload.get("authorities"), list):
        raise ValueError(f"invalid NH authority manifest: {target}")
    return payload


def active_records(*, as_of: date, path: str | Path | None = None) -> list[AuthorityRecord]:
    payload = load_payload(path)
    return [
        record
        for item in payload.get("authorities", [])
        if (record := AuthorityRecord.from_dict(item)).is_active(as_of)
    ]


def snapshot_root_for_manifest(path: str | Path) -> Path:
    """Return the root against which a manifest's local filenames resolve."""
    manifest = Path(path).resolve()
    if manifest.parent.name != "manifest":
        raise ValueError(f"manifest must be inside a manifest directory: {manifest}")
    return manifest.parent.parent


def read_verified_record(
    record: AuthorityRecord,
    *,
    repository_root: Path | None = None,
    manifest_path: str | Path | None = None,
    max_bytes: int = 2 * 1024 * 1024,
) -> bytes | None:
    """Read a bounded, confined capsule once and verify precisely the returned bytes.

    Paths from a manifest are data, not permission to traverse the filesystem.
    Reject Windows path escapes even on a POSIX build host. Do not follow
    symlinks or return bytes from a hash-mismatched or oversized capsule.
    """
    name = record.local_filename
    digest = record.sha256
    if not isinstance(name, str) or not name or not isinstance(digest, str):
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        return None
    if "\\" in name or "\x00" in name or ":" in name:
        return None
    relative = Path(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or ".." in relative.parts:
        return None
    try:
        if repository_root is not None:
            base = repository_root.resolve(strict=True)
        else:
            target = Path(manifest_path) if manifest_path else default_manifest_path()
            base = snapshot_root_for_manifest(target).resolve(strict=True)
        candidate = base / relative
        if not candidate.resolve(strict=True).is_relative_to(base):
            return None
        part = base
        for component in relative.parts:
            part = part / component
            if part.is_symlink():
                return None
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(candidate, flags), "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > max_bytes:
                return None
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes or hashlib.sha256(raw).hexdigest() != digest.lower():
            return None
        return raw
    except (OSError, ValueError, RuntimeError):
        return None


def verify_record_file(
    record: AuthorityRecord,
    *,
    repository_root: Path | None = None,
    manifest_path: str | Path | None = None,
) -> bool:
    return read_verified_record(
        record, repository_root=repository_root, manifest_path=manifest_path
    ) is not None


def substantive_records(records: Iterable[AuthorityRecord]) -> list[AuthorityRecord]:
    """Exclude source-governance records from substantive legal propositions."""
    return [record for record in records if record.answer_scope != "source_currentness_only"]
