from __future__ import annotations

"""Parsers for official New Hampshire General Court RSA pages.

These parsers preserve provenance and structure only.  They do not decide whether
an RSA section is current; currentness is determined by the authority review and
promotion pipeline after an official snapshot has been acquired.
"""

import re
from urllib.parse import urlparse

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import SourceLocation, StatuteSection, StatuteTitle

PARSER_VERSION = "nh_general_court_parser_v1"

_TITLE_RE = re.compile(r"\bTITLE\s+(?P<title>[IVXLCDM]+)\b", re.I)
_CHAPTER_RE = re.compile(
    r"\bCHAPTER\s+(?P<chapter>\d+(?:-[A-Z]+)?)\s+(?P<heading>[^\n]{1,220})",
    re.I,
)
_SECTION_CITATION_RE = re.compile(
    r"\b(?P<chapter>\d+(?:-[A-Z]+)?):(?P<section>\d+(?:-[A-Z0-9]+)*)\b",
    re.I,
)
_SECTION_HEADING_RE = re.compile(
    r"\b(?P<citation>\d+(?:-[A-Z]+)?:\d+(?:-[A-Z0-9]+)*)\s+"
    r"(?P<heading>[^\n]{1,220}?)(?:\.|\n|$)",
    re.I,
)
_SECTION_HREF_RE = re.compile(
    r"/(?P<chapter>\d+(?:-[A-Z]+)?)/(?P=chapter)-(?P<section>\d+(?:-[A-Z0-9]+)*)\.htm(?:l)?$",
    re.I,
)
_REVISED_RE = re.compile(
    r"(?:source|section)\s*\.?\s*(?:effective|amended|revised)\s*[:,-]?\s*([^\n]{4,100})",
    re.I,
)
_DATA_EXTRACTED_RE = re.compile(
    r"data\s+for\s+this\s+page\s+extracted\s+on\s+([^\n<]{4,100})",
    re.I,
)
_SUBSECTION_RE = re.compile(r"(?:^|\s)(?P<label>(?:[IVXLCDM]+|\d+|[a-z])\.)\s+(?P<body>[^\n]{8,260})", re.I)


def infer_general_court_freshness(html: str) -> tuple[str, str | None]:
    """Return only an explicitly printed amendment/effective marker.

    The parser intentionally does not label a source current merely because it
    came from an official host.  A reviewer or update job must compare the
    captured source against enacted law and effective dates.
    """

    text = normalize_whitespace(html)
    extraction = _DATA_EXTRACTED_RE.search(text)
    if extraction:
        return "known_extracted_timestamp", normalize_whitespace(extraction.group(1))
    match = _REVISED_RE.search(text)
    if match:
        return "printed_revision_marker", normalize_whitespace(match.group(1))
    return "official_snapshot_timestamp_required", None


def _chapter_from_url(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    for part in reversed(parts):
        if re.fullmatch(r"\d+(?:-[A-Z]+)?", part, flags=re.I):
            return part.upper()
    return None


def _section_from_url(url: str) -> tuple[str | None, str | None]:
    match = _SECTION_HREF_RE.search(urlparse(url).path)
    if not match:
        return None, None
    return match.group("chapter").upper(), match.group("section").upper()


def parse_general_court_chapter_index(
    html: str, *, source_id: str, url: str
) -> tuple[StatuteTitle, ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    title_match = _TITLE_RE.search(visible_text)
    chapter_match = _CHAPTER_RE.search(visible_text)
    title_number = title_match.group("title").upper() if title_match else "UNKNOWN"
    chapter_number = (
        chapter_match.group("chapter").upper()
        if chapter_match
        else (_chapter_from_url(url) or "UNKNOWN")
    )
    chapter_heading = normalize_whitespace(chapter_match.group("heading")) if chapter_match else ""
    freshness_status, revision_marker = infer_general_court_freshness(html)

    section_links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        href = link["href"]
        chapter, section = _section_from_url(href)
        if not chapter or not section:
            citation_match = _SECTION_CITATION_RE.search(link.get("text") or "")
            if citation_match:
                chapter = citation_match.group("chapter").upper()
                section = citation_match.group("section").upper()
        if not chapter or not section:
            continue
        key = (chapter, section)
        if key in seen:
            continue
        seen.add(key)
        section_links.append(
            {
                "chapter": chapter,
                "section": section,
                "citation": f"RSA {chapter}:{section}",
                "text": normalize_whitespace(link.get("text") or ""),
                "href": href,
                "source_id": stable_source_id("nh-rsa-section", href),
            }
        )

    document = StatuteTitle(
        document_id=f"rsa-chapter-{chapter_number.lower()}",
        source_location=SourceLocation(source_id=source_id, url_or_path=url),
        document_type="statute_chapter_index",
        title=(
            f"New Hampshire Revised Statutes Chapter {chapter_number}"
            + (f": {chapter_heading}" if chapter_heading else "")
        ),
        text=visible_text,
        citation=f"RSA ch. {chapter_number}",
        retrieved_freshness_status=freshness_status,
        title_number=title_number,
        chapters=[
            {
                "chapter": chapter_number,
                "heading": chapter_heading,
                "title": title_number,
            }
        ],
        section_links=section_links,
        data_extracted_at=revision_marker,
        metadata={"chapter_number": chapter_number, "revision_marker": revision_marker},
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_general_court_chapter_index",
        parser_version=PARSER_VERSION,
        status="parsed" if chapter_number != "UNKNOWN" else "partial",
        message="parsed New Hampshire General Court RSA chapter index",
        extracted_count=len(section_links),
        metadata={
            "title_number": title_number,
            "chapter_number": chapter_number,
            "section_link_count": len(section_links),
            "revision_marker": revision_marker,
        },
    )
    return document, event


def parse_general_court_section_html(
    html: str, *, source_id: str, url: str
) -> tuple[StatuteSection, ParserAuditEvent]:
    _links, visible_text = collect_links_and_text(html, base_url=url)
    title_match = _TITLE_RE.search(visible_text)
    url_chapter, url_section = _section_from_url(url)
    heading_match = _SECTION_HEADING_RE.search(visible_text)
    citation_match = _SECTION_CITATION_RE.search(visible_text)

    if citation_match:
        chapter_number = citation_match.group("chapter").upper()
        section_number = citation_match.group("section").upper()
    else:
        chapter_number = url_chapter or _chapter_from_url(url) or "UNKNOWN"
        section_number = url_section or "UNKNOWN"
    title_number = title_match.group("title").upper() if title_match else "UNKNOWN"
    heading = normalize_whitespace(heading_match.group("heading")) if heading_match else ""
    freshness_status, revision_marker = infer_general_court_freshness(html)
    subsections = [
        normalize_whitespace(f"{match.group('label')} {match.group('body')}")
        for match in _SUBSECTION_RE.finditer(visible_text)
    ][:250]
    citation = (
        f"RSA {chapter_number}:{section_number}"
        if chapter_number != "UNKNOWN" and section_number != "UNKNOWN"
        else None
    )
    document = StatuteSection(
        document_id=(
            f"rsa-{chapter_number.lower()}-{section_number.lower()}"
            if citation
            else stable_source_id("nh-rsa-section", url)
        ),
        source_location=SourceLocation(source_id=source_id, url_or_path=url),
        document_type="statute_section",
        title=(f"{citation}: {heading}" if citation and heading else citation or "New Hampshire RSA section"),
        text=visible_text,
        citation=citation,
        retrieved_freshness_status=freshness_status,
        title_number=title_number,
        section_number=(f"{chapter_number}:{section_number}" if citation else None),
        section_heading=heading or None,
        subsections=subsections,
        metadata={
            "chapter_number": chapter_number,
            "section_component": section_number,
            "revision_marker": revision_marker,
        },
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_general_court_section",
        parser_version=PARSER_VERSION,
        status="parsed" if citation else "partial",
        message="parsed New Hampshire General Court RSA section",
        extracted_count=len(subsections),
        metadata={
            "citation": citation,
            "chapter_number": chapter_number,
            "section_number": section_number,
            "revision_marker": revision_marker,
        },
        warnings=[] if citation else ["RSA citation was not found in the page or URL"],
    )
    return document, event


def parse_general_court_html(html: str, *, source_id: str, url: str):
    """Route an official RSA snapshot to the chapter-index or section parser."""

    path = urlparse(url).path.lower()
    if path.endswith("-mrg.htm") or path.endswith("-mrg.html"):
        return parse_general_court_chapter_index(html, source_id=source_id, url=url)
    if _section_from_url(url)[1] is not None:
        return parse_general_court_section_html(html, source_id=source_id, url=url)
    # A merged page can be supplied through a fixture.invalid URL.  Prefer the
    # chapter parser when it contains chapter text and multiple RSA citations.
    if _CHAPTER_RE.search(normalize_whitespace(html)) and len(_SECTION_CITATION_RE.findall(html)) > 1:
        return parse_general_court_chapter_index(html, source_id=source_id, url=url)
    return parse_general_court_section_html(html, source_id=source_id, url=url)


__all__ = [
    "PARSER_VERSION",
    "infer_general_court_freshness",
    "parse_general_court_chapter_index",
    "parse_general_court_section_html",
    "parse_general_court_html",
]
