from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from legal.ops.release_pilot_hardening import ReleasePilotHardeningError, _safe_external_root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_DIRNAME = "eval_store"
DEFAULT_EVAL_NAMESPACE = "nh-family-law-llm"
FORBIDDEN_SEGMENTS = {
    "02_private_forensic_master",
    "02_private",
    "private",
    "private_matter",
    "private_matter_store",
    "matter_store",
    "eval_data",
    "msix",
    "stage",
    "staging",
    "windows",
    "windowsapps",
    "program files",
    "program files (x86)",
    "programdata",
    "system32",
}

class ExternalEvalRootError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _casefold_parts(path: Path) -> set[str]:
    parts = {part.casefold() for part in path.parts}
    if path.drive:
        parts.add(path.drive.casefold())
    return parts


def _contains_forbidden_segment(path: Path, forbidden: Iterable[str]) -> str:
    parts = _casefold_parts(path)
    for candidate in forbidden:
        folded = candidate.casefold()
        for part in parts:
            # Do not reverse this comparison: a harmless component such as
            # "data" is a substring of "programdata", not the protected folder.
            if folded == part or folded in part:
                return candidate
    return ""


def _looks_like_traversal(path: str) -> bool:
    """Reject traversal using both POSIX and Windows separator semantics."""

    raw = str(path or "").strip()
    if not raw:
        return False
    normalized = raw.replace("\\", "/")
    return ".." in PurePosixPath(normalized).parts or ".." in PureWindowsPath(raw).parts


def _reject_linked_path(path: Path) -> None:
    """Inspect lexical ancestors before resolve() hides links or junctions."""

    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as exc:
            raise ExternalEvalRootError(
                "external_eval_root_unavailable",
                "The evaluation root cannot be inspected.",
            ) from exc
        reparse = getattr(metadata, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
        )
        if stat.S_ISLNK(metadata.st_mode) or reparse:
            raise ExternalEvalRootError(
                "external_eval_root_symlink_refused",
                "The evaluation root and its ancestors cannot be links or reparse points.",
            )


def _default_eval_candidate(project: Path) -> Path:
    namespace = project.name or DEFAULT_EVAL_NAMESPACE
    return Path.home() / ".codex" / DEFAULT_EVAL_DIRNAME / namespace


def default_external_eval_root(project_root: str | Path = ".") -> Path:
    """Return and create the validated user-local default evaluation root."""

    project = Path(project_root).resolve()
    return resolve_external_eval_root(
        _default_eval_candidate(project), project_root=project, create=True
    )


def resolve_external_eval_root(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = False,
) -> Path:
    """Resolve an external eval root with fail-closed containment checks.

    Selecting the default only chooses a candidate. It does not create a
    directory or bypass validation when ``create`` is false.
    """

    project = Path(project_root).resolve()
    raw = (
        str(_default_eval_candidate(project))
        if configured is None or not str(configured).strip()
        else str(configured).strip()
    )
    if _looks_like_traversal(raw):
        raise ExternalEvalRootError(
            "external_eval_root_path_traversal",
            "The evaluation root path contains a traversal segment.",
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise ExternalEvalRootError(
            "external_eval_root_path_invalid",
            "The evaluation root path is invalid.",
        )

    try:
        path = Path(raw).expanduser().absolute()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExternalEvalRootError(
            "external_eval_root_path_invalid",
            "The evaluation root path is invalid.",
        ) from exc
    _reject_linked_path(path)
    try:
        # Validation remains side-effect-free until all checks have passed.
        candidate = _safe_external_root(
            path, repo_root=project, forbidden_roots=(project,), create=False
        )
    except ReleasePilotHardeningError as exc:
        raise ExternalEvalRootError(
            exc.code, str(exc), status_code=exc.status_code
        ) from exc
    if candidate is None:
        raise ExternalEvalRootError(
            "external_eval_root_unavailable",
            "An evaluation root is required.",
        )

    forbidden = _contains_forbidden_segment(candidate, FORBIDDEN_SEGMENTS)
    if forbidden:
        raise ExternalEvalRootError(
            "external_eval_root_inside_forbidden_root",
            f"The evaluation root cannot live inside forbidden directory segment: {forbidden}.",
        )
    # Recheck lexical components immediately before any write to narrow a
    # link-swap window and ensure a dangling link is never followed.
    _reject_linked_path(path)
    if create:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExternalEvalRootError(
                "external_eval_root_unavailable",
                "The evaluation root cannot be created.",
            ) from exc
    return candidate


@dataclass(frozen=True)
class ExternalEvalRootLayout:
    root: Path

    @property
    def annotation_queue(self) -> Path:
        return self.root / "annotation_queue"

    @property
    def assignments(self) -> Path:
        return self.root / "assignments"

    @property
    def reviews(self) -> Path:
        return self.root / "reviews"

    @property
    def adjudications(self) -> Path:
        return self.root / "adjudications"

    @property
    def promoted_gold(self) -> Path:
        return self.root / "promoted_gold"

    @property
    def datasets(self) -> Path:
        return self.root

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def metrics(self) -> Path:
        return self.root / "metrics"

    @property
    def failure_clusters(self) -> Path:
        return self.root / "failure_clusters"

    @property
    def release_comparisons(self) -> Path:
        return self.root / "release_comparisons"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def audit(self) -> Path:
        return self.root / "audit"

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    def _children(self) -> tuple[Path, ...]:
        return (
            self.annotation_queue,
            self.assignments,
            self.reviews,
            self.adjudications,
            self.promoted_gold,
            self.runs,
            self.metrics,
            self.failure_clusters,
            self.release_comparisons,
            self.exports,
            self.audit,
            self.schemas,
        )

    def ensure(self) -> None:
        children = self._children()
        # Inspect all existing children before creating any sibling so a
        # rejected layout has no partial side effects.
        for path in children:
            _reject_linked_path(path)
        for path in children:
            path.mkdir(parents=True, exist_ok=True)


def external_eval_root_layout(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = True,
) -> ExternalEvalRootLayout:
    root = resolve_external_eval_root(configured, project_root=project_root, create=create)
    layout = ExternalEvalRootLayout(root=root)
    if create:
        layout.ensure()
    return layout
