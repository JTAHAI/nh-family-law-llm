from __future__ import annotations

"""Parsers for Supreme Court of New Hampshire opinion indexes and snapshots."""

import re
from urllib.parse import urlparse

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import OpinionReference

PARSER_VERSION = "nh_supreme_court_opinion_parser_v1"
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)
_CITATION_RE = re.compile(r"\b(20\d{2}\s+N\.H\.\s+\d+)\b", re.I)
_DOCKET_RE = re.compile(r"\b(?:No\.?\s*)?((?:[A-Z]{2,6}-)?(?:20)?\d{2,4}-\d{2,6})\b", re.I)
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\b")


def _opinion_id_from_href(href: str) -> str:
    return stable_source_id("nh-supreme-court-opinion", urlparse(href).path)


def parse_supreme_court_opinion_index(
    html: str, *, source_id: str, url: str
) -> tuple[list[OpinionReference], ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    opinions: list[OpinionReference] = []
    seen: set[str] = set()
    for link in links:
        href = link["href"]
        text = normalize_whitespace(link.get("text") or "")
        combined = f"{text} {href}"
        if not _PDF_RE.search(href) and "opinion" not in combined.lower():
            continue
        if href in seen:
            continue
        seen.add(href)
        citation_match = _CITATION_RE.search(text)
        docket_match = _DOCKET_RE.search(text) or _DOCKET_RE.search(href)
        date_match = _DATE_RE.search(text)
        opinions.append(
            OpinionReference(
                opinion_id=_opinion_id_from_href(href),
                title=text or href.rsplit("/", 1)[-1],
                href=href,
                decision_date=date_match.group(1) if date_match else None,
                docket_number=docket_match.group(1) if docket_match else None,
                citation=(citation_match.group(1).replace("n.h.", "N.H.").replace("N.h.", "N.H.") if citation_match else None),
                source_id=source_id,
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_supreme_court_opinion_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed Supreme Court of New Hampshire opinion index",
        extracted_count=len(opinions),
        metadata={"text_length": len(visible_text), "opinion_count": len(opinions)},
    )
    return opinions, event


def parse_supreme_court_opinion_text(
    text: str, *, source_id: str, url: str
) -> tuple[OpinionReference, ParserAuditEvent]:
    visible_text = normalize_whitespace(text)
    first_line = visible_text.split(".")[0][:220] if visible_text else url.rsplit("/", 1)[-1]
    citation_match = _CITATION_RE.search(visible_text)
    docket_match = _DOCKET_RE.search(visible_text) or _DOCKET_RE.search(url)
    date_match = _DATE_RE.search(visible_text)
    citation = citation_match.group(1) if citation_match else None
    if citation:
        citation = re.sub(r"n\.h\.", "N.H.", citation, flags=re.I)
    opinion = OpinionReference(
        opinion_id=_opinion_id_from_href(url),
        title=first_line or url.rsplit("/", 1)[-1],
        href=url,
        decision_date=date_match.group(1) if date_match else None,
        docket_number=docket_match.group(1) if docket_match else None,
        citation=citation,
        source_id=source_id,
    )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_supreme_court_opinion_text",
        parser_version=PARSER_VERSION,
        status="parsed" if visible_text else "partial",
        message="parsed Supreme Court of New Hampshire opinion snapshot",
        extracted_count=1 if visible_text else 0,
        metadata={"text_length": len(visible_text), "citation": opinion.citation},
    )
    return opinion, event


__all__ = [
    "PARSER_VERSION",
    "parse_supreme_court_opinion_index",
    "parse_supreme_court_opinion_text",
]
