from __future__ import annotations

"""Parsers for New Hampshire Judicial Branch forms and form indexes."""

import re

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import CourtForm, SourceLocation

PARSER_VERSION = "nh_judicial_branch_forms_parser_v1"
_FORM_ID_RE = re.compile(r"\bNHJB[-\s]?(\d{4})[-\s]?([A-Z]{1,5})\b", re.I)
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)
_VERSION_RE = re.compile(
    r"(?:Rev\.?|Revised|Revision|Version|Updated)\s*(?:date)?\s*[:\-]?\s*"
    r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}/\d{2,4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|[A-Za-z]+\s+\d{4})",
    re.I,
)


def normalize_form_id(value: str) -> str:
    match = _FORM_ID_RE.search(value)
    if not match:
        return value.strip().upper()
    return f"NHJB-{match.group(1)}-{match.group(2).upper()}"


def parse_forms_index(html: str, *, source_id: str, url: str) -> tuple[list[CourtForm], ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    forms: list[CourtForm] = []
    seen: set[str] = set()
    for link in links:
        href = link["href"]
        label = normalize_whitespace(link.get("text") or "")
        match = _FORM_ID_RE.search(label) or _FORM_ID_RE.search(href)
        if not match and not _PDF_RE.search(href):
            continue
        form_id = normalize_form_id(match.group(0)) if match else None
        key = form_id or href
        if key in seen:
            continue
        seen.add(key)
        forms.append(
            CourtForm(
                document_id=stable_source_id("nh-court-form", href),
                source_location=SourceLocation(source_id=source_id, url_or_path=href),
                document_type="court_form",
                title=label or href.rsplit("/", 1)[-1],
                citation=form_id,
                form_id=form_id,
                retrieved_freshness_status="official_snapshot_timestamp_required",
                stale_form_risk="unknown_until_version_reviewed",
                metadata={"index_url": url},
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_forms_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed New Hampshire Judicial Branch forms index",
        extracted_count=len(forms),
        metadata={"text_length": len(visible_text), "form_count": len(forms)},
    )
    return forms, event


def parse_form_text(text: str, *, source_id: str, url: str) -> tuple[CourtForm, ParserAuditEvent]:
    clean = normalize_whitespace(text)
    id_match = _FORM_ID_RE.search(clean) or _FORM_ID_RE.search(url)
    version_match = _VERSION_RE.search(clean)
    form_id = normalize_form_id(id_match.group(0)) if id_match else None
    title = clean[:180] if clean else "New Hampshire Judicial Branch court form"
    freshness_status = "known_version_date" if version_match else "form_pdf_retrieved_timestamp_known"
    form = CourtForm(
        document_id=stable_source_id("nh-court-form", url),
        source_location=SourceLocation(source_id=source_id, url_or_path=url),
        document_type="court_form",
        title=title,
        text=clean,
        citation=form_id,
        form_id=form_id,
        version_date=version_match.group(1) if version_match else None,
        retrieved_freshness_status=freshness_status,
        stale_form_risk=(
            "version_date_extracted" if version_match else "version_date_missing_uses_retrieved_timestamp"
        ),
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_form_text",
        parser_version=PARSER_VERSION,
        status="parsed" if clean else "partial",
        message="parsed New Hampshire Judicial Branch form text metadata",
        extracted_count=1 if clean else 0,
        metadata={"form_id": form_id, "version_date": form.version_date},
        warnings=[] if version_match else ["form version date not found; review required"],
    )
    return form, event


__all__ = ["PARSER_VERSION", "normalize_form_id", "parse_forms_index", "parse_form_text"]
