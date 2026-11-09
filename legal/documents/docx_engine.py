"""Safe adapters for creating and editing Word documents.

Tracked-change editing uses the MIT-licensed ``docx-editor`` package by Pablo
Speciale when installed. The adapter deliberately exposes only a bounded subset
of its API and always writes a new artifact; it never overwrites an imported
source document.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import io
import os
import re
import stat
import tempfile
import zipfile
from itertools import islice
from pathlib import Path
from typing import Any, Iterable

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from .workspace import DocumentWorkspaceError

MAX_DOCX_BYTES = 50 * 1024 * 1024
MAX_DOCX_MEMBERS = 4096
MAX_DOCX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_DOCX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_EDIT_OPERATIONS = 100
MAX_EDIT_TEXT_CHARS = 50_000
_PARAGRAPH_REF_RE = re.compile(r"^P[1-9][0-9]*#[a-f0-9]{4,64}$")
_ALLOWED_ACTIONS = {"replace", "delete", "insert_after", "rewrite_paragraph", "add_comment"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise DocumentWorkspaceError("docx_path_unavailable", "The DOCX path cannot be inspected.", status_code=409) from exc
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise DocumentWorkspaceError("docx_symlink_refused", "A DOCX path contains a link or reparse point.", status_code=409)


def _inside(path: Path, root: Path) -> Path:
    _reject_links(path.absolute())
    _reject_links(root.absolute())
    try:
        resolved = path.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        resolved.relative_to(resolved_root)
        if not resolved_root.is_dir() or not stat.S_ISREG(resolved.stat().st_mode):
            raise ValueError("regular source required")
    except (ValueError, OSError, RuntimeError) as exc:
        raise DocumentWorkspaceError("docx_path_outside_workspace", "The DOCX path is outside the local workspace or unavailable.", status_code=409) from exc
    return resolved


def _read_source(path: Path) -> bytes:
    # Read a bounded regular file, not an unbounded read_bytes() after stat().
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_DOCX_BYTES:
                raise DocumentWorkspaceError("invalid_docx_source", "The DOCX source exceeds the safety limits or is not a regular file.", status_code=409)
            data = stream.read(MAX_DOCX_BYTES + 1)
        if path.suffix.lower() != ".docx" or len(data) > MAX_DOCX_BYTES:
            raise DocumentWorkspaceError("invalid_docx_source", "The preserved source is not an allowed DOCX.", status_code=409)
        return data
    except OSError as exc:
        raise DocumentWorkspaceError("invalid_docx_source", "The preserved DOCX source cannot be read.", status_code=409) from exc


def _validate_docx(data: bytes) -> None:
    """Bound expansion and reject aliases/entities before a third-party parser.

    This is a package-safety check, not Word visual validation or legal review.
    No part is extracted and no external relationship target is retrieved here.
    """
    def unsafe() -> None:
        raise DocumentWorkspaceError("unsafe_docx_archive", "The DOCX package is malformed or contains unsafe entries.", status_code=409)

    def oversized() -> None:
        raise DocumentWorkspaceError("docx_archive_too_large", "The expanded DOCX package exceeds the safety limits.", status_code=413)

    if len(data) > MAX_DOCX_BYTES:
        oversized()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_DOCX_MEMBERS:
                oversized()
            if sum(info.file_size for info in entries) > MAX_DOCX_EXPANDED_BYTES:
                oversized()
            seen: dict[str, bool] = {}
            documents: set[str] = set()
            for info in entries:
                name = info.orig_filename
                directory = info.is_dir()
                parts = (name[:-1] if directory else name).split("/")
                if (name != info.filename or not name or "\\" in name or ":" in name
                        or any(ord(char) < 32 or ord(char) == 127 for char in name)
                        or any(part in {"", ".", ".."} or part.rstrip(" .") != part
                               or re.fullmatch(r"(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                               for part in parts)):
                    unsafe()
                folded = "/".join(parts).casefold()
                if folded in seen:
                    unsafe()
                seen[folded] = directory
                mode = stat.S_IFMT(info.external_attr >> 16)
                if mode not in ({0, stat.S_IFDIR} if directory else {0, stat.S_IFREG}) or info.flag_bits & 1:
                    unsafe()
                if info.file_size > MAX_DOCX_MEMBER_BYTES:
                    oversized()
                if directory:
                    if info.file_size:
                        unsafe()
                    continue
                documents.add(name)
            # Reject file/directory collisions regardless of archive order.
            for name in seen:
                parts = name.split("/")
                if any("/".join(parts[:i]) in seen and not seen["/".join(parts[:i])]
                       for i in range(1, len(parts))):
                    unsafe()
            if not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}.issubset(documents):
                unsafe()
            actual_total = 0
            for info in entries:
                if info.is_dir():
                    continue
                with archive.open(info) as stream:
                    part = stream.read(MAX_DOCX_MEMBER_BYTES + 1)
                actual_total += len(part)
                if len(part) > MAX_DOCX_MEMBER_BYTES or actual_total > MAX_DOCX_EXPANDED_BYTES:
                    oversized()
                if len(part) != info.file_size:
                    unsafe()
                if info.filename.lower().endswith((".xml", ".rels")):
                    SafeET.fromstring(part, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DocumentWorkspaceError:
        raise
    except (OSError, ValueError, RuntimeError, NotImplementedError, zipfile.BadZipFile,
            SafeET.ParseError, DefusedXmlException) as exc:
        raise DocumentWorkspaceError("unsafe_docx_archive", "The DOCX package could not be safely inspected.", status_code=409) from exc


def _new_output(path: Path, root: Path) -> Path:
    _reject_links(path.absolute())
    _reject_links(root.absolute())
    try:
        parent = path.parent.resolve(strict=True)
        allowed = root.resolve(strict=True)
        parent.relative_to(allowed)
        if not parent.is_dir() or not allowed.is_dir():
            raise ValueError("directory required")
    except (OSError, ValueError, RuntimeError) as exc:
        raise DocumentWorkspaceError("docx_path_outside_workspace", "The DOCX output path is outside the local workspace or unavailable.", status_code=409) from exc
    output = parent / path.name
    if output.suffix.lower() != ".docx":
        raise DocumentWorkspaceError("invalid_docx_extension", "Word exports must use the .docx extension.")
    if output.exists():
        raise DocumentWorkspaceError("docx_output_conflict", "A new DOCX output path is required.", status_code=409)
    return output


def _publish_new(path: Path, data: bytes) -> None:
    """Atomically publish a complete artifact without replacing any existing file."""
    _reject_links(path.absolute())
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".nhfl-docx-publish-", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Unlike os.replace(), link creation fails if another writer has
        # claimed the destination. No overwrite fallback on unsupported FSs.
        os.link(temporary, path)
    except FileExistsError as exc:
        raise DocumentWorkspaceError("docx_output_conflict", "The DOCX output path is already occupied.", status_code=409) from exc
    except OSError as exc:
        raise DocumentWorkspaceError("docx_output_unavailable", "The DOCX artifact could not be published safely.", status_code=503) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _assert_source_unchanged(source: Path, root: Path, expected: bytes) -> None:
    try:
        unchanged = _read_source(_inside(source, root)) == expected
    except DocumentWorkspaceError:
        unchanged = False
    if not unchanged:
        raise DocumentWorkspaceError("docx_source_changed", "The preserved DOCX changed during processing. Reload it before continuing.", status_code=409)


def engine_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "engine": "docx-editor",
        "license": "MIT",
        "copyright": "Copyright (c) 2026 Pablo Speciale",
        "tracked_changes_available": False,
        "document_creation_available": False,
        "local_only": True,
        "source_overwrite_allowed": False,
    }
    try:
        importlib.import_module("docx_editor")
        try:
            version = importlib.metadata.version("docx-editor")
        except importlib.metadata.PackageNotFoundError:
            version = "source-tree"
        status.update({"tracked_changes_available": True, "version": version})
    except Exception as exc:
        status["tracked_changes_reason"] = f"docx-editor unavailable: {type(exc).__name__}"
    try:
        importlib.import_module("docx")
        status["document_creation_available"] = True
    except Exception as exc:
        status["document_creation_reason"] = f"python-docx unavailable: {type(exc).__name__}"
    return status


def create_docx_from_text(
    *,
    title: str,
    content: str,
    output_path: Path,
    allowed_output_root: Path,
) -> dict[str, Any]:
    """Create a new review-required DOCX without touching any source document."""
    try:
        from docx import Document
        from docx.shared import Pt
    except Exception as exc:
        raise DocumentWorkspaceError("python_docx_unavailable", "Word export requires python-docx.", status_code=503) from exc

    output_path = _new_output(Path(output_path), Path(allowed_output_root))

    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    document.add_heading(str(title)[:240], level=0)
    document.add_paragraph("REVIEW REQUIRED — WORKING DRAFT — NOT FILING-READY")
    for raw_line in str(content or "").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            document.add_paragraph()
        elif stripped.startswith("### "):
            document.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            document.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            document.add_heading(stripped[2:], level=1)
        elif re.match(r"^[-*]\s+", stripped):
            document.add_paragraph(re.sub(r"^[-*]\s+", "", stripped), style="List Bullet")
        elif re.match(r"^\d+[.)]\s+", stripped):
            document.add_paragraph(re.sub(r"^\d+[.)]\s+", "", stripped), style="List Number")
        else:
            document.add_paragraph(line)

    with tempfile.TemporaryDirectory(prefix=".nhfl-docx-", dir=output_path.parent) as directory:
        temporary = Path(directory) / "created.docx"
        document.save(temporary)
        data = _read_source(temporary)
        _validate_docx(data)
        _publish_new(output_path, data)
    return {
        "path": output_path,
        "size_bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
        "format": "docx",
        "review_required": True,
        "filing_ready": False,
        "original_preserved": True,
    }


def _normalize_operations(operations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        rows = list(islice(iter(operations), MAX_EDIT_OPERATIONS + 1))
    except TypeError as exc:
        raise DocumentWorkspaceError("invalid_docx_edit", "DOCX edits must be an iterable of objects.") from exc
    if not rows:
        raise DocumentWorkspaceError("docx_edits_required", "At least one DOCX edit is required.")
    if len(rows) > MAX_EDIT_OPERATIONS:
        raise DocumentWorkspaceError("too_many_docx_edits", f"No more than {MAX_EDIT_OPERATIONS} edits may be applied at once.", status_code=413)
    fields = {
        "replace": {"paragraph", "find", "replace_with"},
        "delete": {"paragraph", "text", "find"},
        "insert_after": {"paragraph", "find", "text"},
        "rewrite_paragraph": {"paragraph", "text"},
        # The exposed backend comment API is document-wide, not paragraph-
        # scoped. Refuse a paragraph selector rather than silently ignore it.
        "add_comment": {"find", "text", "comment"},
    }
    normalized: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise DocumentWorkspaceError("invalid_docx_edit", "Each DOCX edit must be an object.")
        action = raw.get("action")
        if not isinstance(action, str) or action not in _ALLOWED_ACTIONS:
            raise DocumentWorkspaceError("invalid_docx_edit_action", "The DOCX edit action is not allowed.")
        if set(raw) - fields[action] - {"action", "occurrence"}:
            raise DocumentWorkspaceError("invalid_docx_edit_fields", "The DOCX edit contains unknown or unsupported fields.")
        row: dict[str, Any] = {"action": action}
        for key in fields[action]:
            if key not in raw:
                continue
            value = raw[key]
            if not isinstance(value, str) or any(
                    ord(char) < 32 and char not in "\t\n\r"
                    or 0xD800 <= ord(char) <= 0xDFFF or ord(char) in {0xFFFE, 0xFFFF}
                    for char in value):
                raise DocumentWorkspaceError("invalid_docx_edit_text", "DOCX edit text must contain valid XML characters and must be a string.")
            if len(value) > MAX_EDIT_TEXT_CHARS:
                raise DocumentWorkspaceError("docx_edit_text_too_large", "A DOCX edit field exceeds the safety limit.", status_code=413)
            row[key] = value
        if action != "add_comment" and not _PARAGRAPH_REF_RE.fullmatch(row.get("paragraph", "")):
            raise DocumentWorkspaceError("invalid_paragraph_reference", "DOCX edits require a current hash-anchored paragraph reference.")
        occurrence = raw.get("occurrence", 0)
        if type(occurrence) is not int or not 0 <= occurrence <= 100_000:
            raise DocumentWorkspaceError("invalid_docx_occurrence", "DOCX occurrence must be an integer within the allowed range.")
        if action == "rewrite_paragraph" and occurrence != 0:
            raise DocumentWorkspaceError("invalid_docx_occurrence", "A whole-paragraph rewrite cannot select a text occurrence.")
        row["occurrence"] = occurrence
        required = {"replace": ("find", "replace_with"), "insert_after": ("find", "text"),
                    "rewrite_paragraph": ("text",)}.get(action, ())
        if any(key not in row for key in required):
            raise DocumentWorkspaceError("invalid_docx_edit_fields", "A required DOCX edit field is missing.")
        selector = row.get("text", row.get("find", "")) if action == "delete" else row.get("find", row.get("text", ""))
        if action != "rewrite_paragraph" and not selector:
            raise DocumentWorkspaceError("invalid_docx_edit_fields", "A nonempty DOCX text selector is required.")
        if action in {"delete", "add_comment"} and "text" in row and "find" in row and row["text"] != row["find"]:
            raise DocumentWorkspaceError("invalid_docx_edit_fields", "Conflicting DOCX text selectors are not allowed.")
        normalized.append(row)
    return normalized


def list_docx_paragraphs(
    *,
    source_path: Path,
    allowed_source_root: Path,
    start: int = 1,
    limit: int = 200,
) -> dict[str, Any]:
    """Return bounded, hash-anchored paragraph references from a preserved DOCX."""
    if type(start) is not int or type(limit) is not int or not 1 <= start <= 100_000 or not 1 <= limit <= 500:
        raise DocumentWorkspaceError("invalid_docx_range", "The DOCX paragraph range is invalid.")
    source = _inside(Path(source_path), Path(allowed_source_root))
    data = _read_source(source)
    _validate_docx(data)
    try:
        from docx_editor import Document
    except Exception as exc:
        raise DocumentWorkspaceError("docx_editor_unavailable", "Tracked Word editing requires the MIT-licensed docx-editor package.", status_code=503) from exc
    try:
        with tempfile.TemporaryDirectory(prefix=".nhfl-docx-", dir=source.parent) as directory:
            working = Path(directory) / "source.docx"
            working.write_bytes(data)
            workspace = Path(directory) / "engine"
            workspace.mkdir(mode=0o700)
            with Document.open(working, author="New Hampshire Family Law LLM User", force_recreate=True, workspace_dir=workspace) as document:
                paragraphs = document.list_paragraphs_structured(start=start, limit=limit)
                total = document.paragraph_count()
                rows = [{"index": int(item.index), "ref": str(item.ref), "text": str(item.text)[:10_000]} for item in paragraphs]
            _assert_source_unchanged(source, Path(allowed_source_root), data)
    except DocumentWorkspaceError:
        raise
    except Exception as exc:
        raise DocumentWorkspaceError("docx_processing_failed", "The DOCX could not be processed safely. The preserved source was not edited.", status_code=422) from exc
    return {"paragraphs": rows, "total": total, "start": start, "limit": limit, "source_sha256": hashlib.sha256(data).hexdigest()}


def tracked_edit_copy(
    *,
    source_path: Path,
    allowed_source_root: Path,
    output_path: Path,
    allowed_output_root: Path,
    operations: Iterable[dict[str, Any]],
    author: str = "New Hampshire Family Law LLM User",
) -> dict[str, Any]:
    """Apply bounded tracked edits to a new copy of a preserved DOCX source."""
    normalized = _normalize_operations(operations)
    if not isinstance(author, str) or len(author) > 120 or any(ord(char) < 32 for char in author):
        raise DocumentWorkspaceError("invalid_docx_author", "The DOCX reviewer name is invalid.")
    source = _inside(Path(source_path), Path(allowed_source_root))
    data = _read_source(source)
    _validate_docx(data)
    output_path = _new_output(Path(output_path), Path(allowed_output_root))
    try:
        from docx_editor import Document
    except Exception as exc:
        raise DocumentWorkspaceError("docx_editor_unavailable", "Tracked Word editing requires the MIT-licensed docx-editor package.", status_code=503) from exc

    try:
        with tempfile.TemporaryDirectory(prefix=".nhfl-docx-", dir=output_path.parent) as directory:
            temporary = Path(directory) / "working.docx"
            temporary.write_bytes(data)
            workspace_dir = Path(directory) / "engine"
            workspace_dir.mkdir(mode=0o700)
            edit_results: list[dict[str, Any]] = []
            with Document.open(temporary, author=author.strip() or "Reviewer", force_recreate=True, workspace_dir=workspace_dir) as document:
                for row in normalized:
                    action = row["action"]
                    if action == "replace":
                        new_ref = document.replace(row.get("find", ""), row.get("replace_with", ""), paragraph=row["paragraph"], occurrence=row["occurrence"])
                        edit_results.append({"action": action, "paragraph": row["paragraph"], "new_ref": str(new_ref)})
                    elif action == "delete":
                        new_ref = document.delete(row.get("text", row.get("find", "")), paragraph=row["paragraph"], occurrence=row["occurrence"])
                        edit_results.append({"action": action, "paragraph": row["paragraph"], "new_ref": str(new_ref)})
                    elif action == "insert_after":
                        new_ref = document.insert_after(row.get("find", ""), row.get("text", ""), paragraph=row["paragraph"], occurrence=row["occurrence"])
                        edit_results.append({"action": action, "paragraph": row["paragraph"], "new_ref": str(new_ref)})
                    elif action == "rewrite_paragraph":
                        result = document.rewrite_paragraph(row["paragraph"], row.get("text", ""))
                        edit_results.append({"action": action, "paragraph": row["paragraph"], "new_ref": str(result)})
                    elif action == "add_comment":
                        comment = document.add_comment(row.get("find", row.get("text", "")), row.get("comment", "Review required"), occurrence=row["occurrence"])
                        edit_results.append({"action": action, "comment_id": int(getattr(comment, "id", -1))})
                document.save()
            edited = _read_source(temporary)
            _validate_docx(edited)
            _assert_source_unchanged(source, Path(allowed_source_root), data)
            _publish_new(output_path, edited)
    except DocumentWorkspaceError:
        raise
    except Exception as exc:
        raise DocumentWorkspaceError("docx_processing_failed", "The DOCX could not be processed safely. The preserved source was not edited.", status_code=422) from exc
    return {
        "path": output_path,
        "size_bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "edit_count": len(normalized),
        "edits": edit_results,
        "tracked_changes": True,
        "review_required": True,
        "filing_ready": False,
        "original_preserved": True,
    }
