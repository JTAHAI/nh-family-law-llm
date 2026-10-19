from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

_NHJB_FORM_ID_RE = re.compile(
    r"\bNHJB(?:[-\s]+)?(?P<number>\d{3,5})(?:[-\s]+)?(?P<suffix>[A-Z]{1,3})\b",
    re.I,
)
_LEGACY_FORM_ID_RE = re.compile(
    r"\b(?P<prefix>FM|PA|CV|PB)[-\s]?(?P<number>\d{3})(?P<suffix>[A-Z]?)\b",
    re.I,
)
_FIELD_RE = re.compile(r"\b([A-Z][A-Za-z /'-]{2,40})(?:\s*[:_]{1,}|\s+\(.*?\)\s*[:_])")
_CITATION_RE = re.compile(
    r"\b(?:NHJB(?:[-\s]+)?\d{3,5}(?:[-\s]+)?[A-Z]{1,3}|"
    r"(?:FM|PA|CV|PB)[-\s]?\d{3}[A-Z]?|"
    r"\d{1,2}-?[A-Z]?\s+M\.R\.S\.\s*§\s*\d+[\w-]*|"
    r"M\.R\.\s+Civ\.\s+P\.\s*\d+)\b",
    re.I,
)


@dataclass(frozen=True)
class FormCatalogEntry:
    form_id: str
    title: str
    source_id: str
    version_date: str | None = None
    filing_context: str = "unknown"
    required_fields: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    freshness_status: str = "unknown"
    stale_form_warning: str | None = None
    issue_labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "form_id": self.form_id,
            "title": self.title,
            "source_id": self.source_id,
            "version_date": self.version_date,
            "filing_context": self.filing_context,
            "required_fields": list(self.required_fields),
            "dependencies": list(self.dependencies),
            "freshness_status": self.freshness_status,
            "stale_form_warning": self.stale_form_warning,
            "issue_labels": list(self.issue_labels),
        }


@dataclass(frozen=True)
class FormIntelligenceReport:
    status: str
    form_count: int
    entries: tuple[FormCatalogEntry, ...] = field(default_factory=tuple)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    stale_forms: tuple[str, ...] = ()
    context_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "form_count": self.form_count,
            "entries": [entry.to_dict() for entry in self.entries],
            "dependency_graph": self.dependency_graph,
            "stale_forms": list(self.stale_forms),
            "context_counts": self.context_counts,
        }


class FormCatalogBuilder:
    """Build a deterministic New Hampshire court-form catalog and dependency graph."""

    def build_catalog(
        self,
        records: list[dict[str, Any]],
        *,
        current_versions: dict[str, str] | None = None,
    ) -> FormIntelligenceReport:
        normalized_current_versions: dict[str, str] = {}
        for raw_form_id, raw_version in (current_versions or {}).items():
            normalized = self._normalize_form_id(str(raw_form_id))
            version = str(raw_version or "").strip()
            if normalized and version:
                normalized_current_versions[normalized] = version
        entries: list[FormCatalogEntry] = []
        for record in records:
            entry = self._entry_from_record(
                record,
                current_versions=normalized_current_versions,
            )
            if entry:
                entries.append(entry)
        dependency_graph = {entry.form_id: list(entry.dependencies) for entry in entries}
        stale_forms = tuple(entry.form_id for entry in entries if entry.freshness_status == "stale")
        context_counts: dict[str, int] = {}
        for entry in entries:
            context_counts[entry.filing_context] = context_counts.get(entry.filing_context, 0) + 1
        return FormIntelligenceReport(
            status="pass",
            form_count=len(entries),
            entries=tuple(entries),
            dependency_graph=dependency_graph,
            stale_forms=stale_forms,
            context_counts=context_counts,
        )

    def search(self, report: FormIntelligenceReport, *, filing_context: str | None = None, issue: str | None = None) -> list[dict[str, Any]]:
        results = []
        for entry in report.entries:
            if filing_context and entry.filing_context != filing_context:
                continue
            if issue and issue not in entry.issue_labels:
                continue
            results.append(entry.to_dict())
        return results

    def _entry_from_record(
        self,
        record: dict[str, Any],
        *,
        current_versions: dict[str, str],
    ) -> FormCatalogEntry | None:
        text = str(record.get("text") or "")
        title = str(record.get("title") or text[:80] or "New Hampshire court form")
        form_id = self._normalize_form_id(str(record.get("form_id") or record.get("citation") or title or text))
        if not form_id:
            return None
        version_date = record.get("version_date") or self._extract_version_date(text)
        explicit_freshness = str(record.get("freshness_status") or "").strip().lower()
        if explicit_freshness in {"current", "fresh", "verified_current"}:
            freshness_status, warning = "current", None
        elif explicit_freshness in {"stale", "superseded", "expired"}:
            freshness_status, warning = "stale", f"{form_id} is marked {explicit_freshness} by the admitted authority generation."
        else:
            freshness_status, warning = self._freshness_status(form_id, version_date, current_versions)
        filing_context = self.classify_filing_context(f"{title}\n{text}")
        issue_labels = tuple(sorted(set(record.get("issue_labels") or self._issue_labels_for_context(filing_context))))
        return FormCatalogEntry(
            form_id=form_id,
            title=title,
            source_id=str(record.get("source_id") or record.get("record_id") or form_id),
            version_date=version_date,
            filing_context=filing_context,
            required_fields=tuple(self.extract_required_fields(f"{title}\n{text}")),
            dependencies=tuple(self.extract_dependencies(f"{title}\n{text}")),
            freshness_status=freshness_status,
            stale_form_warning=warning,
            issue_labels=issue_labels,
        )

    def _normalize_form_id(self, value: str) -> str | None:
        nhjb = _NHJB_FORM_ID_RE.search(value)
        if nhjb:
            return f"NHJB-{nhjb.group('number')}-{nhjb.group('suffix').upper()}"
        legacy = _LEGACY_FORM_ID_RE.search(value)
        if legacy:
            suffix = legacy.group("suffix").upper()
            return f"{legacy.group('prefix').upper()}-{legacy.group('number')}{suffix}"
        return None

    def _extract_version_date(self, text: str) -> str | None:
        match = re.search(r"(?:Rev\.?|Revised|Version)\s*(?:date)?\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}/\d{4}|[A-Za-z]+\s+\d{4})", text, re.I)
        return match.group(1) if match else None

    def _freshness_status(
        self,
        form_id: str,
        version_date: str | None,
        current_versions: dict[str, str],
    ) -> tuple[str, str | None]:
        current = current_versions.get(form_id)
        if not current:
            return "unknown", "No current-version baseline available for this form."
        if not version_date:
            return "unknown", "Form version date was not extracted."
        detected_date = self._parse_version_date(version_date)
        current_date = self._parse_version_date(current)
        if detected_date is None:
            return "unknown", f"The extracted version date for {form_id} is not recognized."
        if current_date is None:
            return "unknown", f"The current-version baseline for {form_id} is not recognized."
        if detected_date < current_date:
            return "stale", f"{form_id} appears stale: extracted {version_date}, expected {current}."
        return "current", None

    def _parse_version_date(self, value: str) -> datetime | None:
        value = value.strip()
        for fmt in (
            "%m/%d/%Y",
            "%m/%d/%y",
            "%m/%Y",
            "%B %Y",
            "%b %Y",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def classify_filing_context(self, text: str) -> str:
        lowered = text.lower()
        if "protection from abuse" in lowered or "pfa" in lowered:
            return "protection_from_abuse"
        if "parentage" in lowered or "paternity" in lowered:
            return "parentage"
        if "child support" in lowered:
            return "child_support"
        if "post-judgment" in lowered or "modify" in lowered or "contempt" in lowered:
            return "post_judgment"
        if "divorce" in lowered or "family matter" in lowered or "parental rights" in lowered:
            return "family_matter"
        return "unknown"

    def extract_required_fields(self, text: str) -> list[str]:
        lowered = text.lower()
        fields = {m.group(1).strip().lower().replace(" ", "_") for m in _FIELD_RE.finditer(text)}
        known = {
            "docket_number": ("docket no", "docket number"),
            "plaintiff_name": ("plaintiff", "petitioner"),
            "defendant_name": ("defendant", "respondent"),
            "child_name": ("child name", "minor child"),
            "address": ("address",),
            "signature": ("signature", "signed"),
            "date": ("date",),
        }
        for field_name, terms in known.items():
            if any(term in lowered for term in terms):
                fields.add(field_name)
        return sorted(field for field in fields if 2 < len(field) <= 50)

    def extract_dependencies(self, text: str) -> list[str]:
        deps: set[str] = set()
        for match in _CITATION_RE.finditer(text):
            value = match.group(0).replace("  ", " ").strip()
            deps.add(self._normalize_form_id(value) or value)
        return sorted(deps)

    def _issue_labels_for_context(self, context: str) -> list[str]:
        return {
            "protection_from_abuse": ["protection_from_abuse", "pfa_family_overlap"],
            "parentage": ["parentage"],
            "child_support": ["child_support"],
            "post_judgment": ["post_judgment_motion"],
            "family_matter": ["divorce", "parental_rights_responsibilities"],
        }.get(context, [])
