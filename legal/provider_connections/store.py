from __future__ import annotations

from dataclasses import dataclass
import re
import stat
from pathlib import Path
from typing import Iterable

from legal.ops.release_pilot_hardening import ReleasePilotHardeningError, _safe_external_root

DEFAULT_PROVIDER_DIRNAME = "provider_store"
DEFAULT_PROVIDER_NAMESPACE = "nh-family-law-llm"
FORBIDDEN_SEGMENTS = {
    "matter", "matter_store", "model_store", "msix", "stage", "staging",
    "windows", "windowsapps", "program files", "program files (x86)",
    "programdata", "system32",
}
WINDOWS_DRIVE_RE = re.compile(r"(?i)^[a-z]:[\\/]")


class ProviderStoreRootError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _looks_like_traversal(path: str) -> bool:
    raw = str(path or "")
    return ".." in Path(raw).parts or bool(WINDOWS_DRIVE_RE.search(raw) and raw.count("..") > 0)


def _contains_forbidden_segment(path: Path, forbidden: Iterable[str]) -> str:
    parts = {part.casefold() for part in path.parts}
    if path.drive:
        parts.add(path.drive.casefold())
    for candidate in forbidden:
        folded = candidate.casefold()
        for part in parts:
            # A harmless short ancestor such as "a" is not "matter".
            if folded == part or folded in part:
                return candidate
    return ""


def default_external_provider_root(project_root: str | Path = ".") -> Path:
    project = Path(project_root).resolve()
    namespace = project.name or DEFAULT_PROVIDER_NAMESPACE
    return Path.home() / ".codex" / DEFAULT_PROVIDER_DIRNAME / namespace


def _reject_linked_path(path: Path) -> None:
    """Inspect lexical ancestors before resolve hides links or junctions."""
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProviderStoreRootError(
                "provider_store_unavailable", "The provider store cannot be inspected."
            ) from exc
        reparse = getattr(metadata, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
        )
        if stat.S_ISLNK(metadata.st_mode) or reparse:
            raise ProviderStoreRootError(
                "provider_store_symlink_refused",
                "The provider store and its ancestors cannot be links or reparse points.",
            )


def resolve_external_provider_root(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = False,
) -> Path:
    project = Path(project_root).resolve()
    raw = str(configured).strip() if configured is not None else ""
    if not raw:
        # Default selection is not a policy exception.
        raw = str(default_external_provider_root(project))
    if _looks_like_traversal(raw):
        raise ProviderStoreRootError(
            "provider_store_path_traversal", "The provider store path contains traversal."
        )
    path = Path(raw).expanduser().absolute()
    _reject_linked_path(path)
    try:
        candidate = _safe_external_root(
            path, repo_root=project, forbidden_roots=(project,), create=False
        )
    except ReleasePilotHardeningError as exc:
        raise ProviderStoreRootError(exc.code, str(exc), status_code=exc.status_code) from exc
    if candidate is None:
        raise ProviderStoreRootError("provider_store_unavailable", "A provider store is required.")
    forbidden = _contains_forbidden_segment(candidate, FORBIDDEN_SEGMENTS)
    if forbidden:
        raise ProviderStoreRootError(
            "provider_store_inside_forbidden_root",
            "The provider store cannot live in a protected directory.",
        )
    _reject_linked_path(path)
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


@dataclass(frozen=True)
class ProviderStoreLayout:
    root: Path

    @property
    def connections(self) -> Path:
        return self.root / "connections"

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions"

    @property
    def audit(self) -> Path:
        return self.root / "audit"

    @property
    def usage(self) -> Path:
        return self.root / "usage"

    def ensure(self) -> None:
        paths = (self.connections, self.manifests, self.sessions, self.audit, self.usage)
        # Inspect every existing child before creating any layout directories.
        for path in paths:
            _reject_linked_path(path)
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)


def external_provider_store_layout(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = True,
) -> ProviderStoreLayout:
    root = resolve_external_provider_root(configured, project_root=project_root, create=create)
    layout = ProviderStoreLayout(root=root)
    if create:
        layout.ensure()
    return layout
