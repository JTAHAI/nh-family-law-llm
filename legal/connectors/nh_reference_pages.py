from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace

PARSER_VERSION = "nh_reference_pages_v1"
_RULE_INDEX = re.compile(r"/rules/state_agencies/(he-[cw])\.html", re.I)
_LEGISLATIVE_HOSTS = {"gc.nh.gov", "gencourt.state.nh.us", "www.gencourt.state.nh.us"}
_GUIDANCE = {
    ("www.courts.nh.gov", "/self-help"): "Self-Help",
    (
        "www.dhhs.nh.gov",
        "/programs-services/childcare-parenting-childbirth/child-support-services",
    ): "Child Support Services",
}


def parse_administrative_rule_index(
    html: str, *, source_id: str, url: str,
) -> tuple[list[dict[str, str]], ParserAuditEvent]:
    """Identify chapter references while keeping the index out of legal retrieval."""
    page = urlsplit(url)
    index = _RULE_INDEX.fullmatch(page.path)
    references: dict[str, dict[str, str]] = {}
    if index and page.netloc in _LEGISLATIVE_HOSTS:
        series = index.group(1).lower()
        chapter_label = re.compile(rf"Chapter\s+{series}\s+(\d+)", re.I)
        links, _ = collect_links_and_text(html, base_url=url)
        for link in links:
            label = chapter_label.fullmatch(link["text"])
            destination = urlsplit(link["href"])
            if not label or destination.netloc not in _LEGISLATIVE_HOSTS:
                continue
            number = label.group(1)
            if destination.path.lower() != f"/rules/state_agencies/{series}{number}.html":
                continue
            if destination.scheme not in {"https", "http"} or destination.query:
                continue
            references.setdefault(number, {
                "chapter": f"He-{series[-1].upper()} {number}",
                "index_href": link["href"],
            })
    return list(references.values()), ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_administrative_rule_index",
        parser_version=PARSER_VERSION,
        status="parsed" if references else "parsed_empty",
        message="Checked New Hampshire administrative rule chapter references for acquisition.",
        extracted_count=len(references),
    )


class _PageHeadings(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []
        self._parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h1":
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._parts is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._parts is not None:
            self.headings.append(normalize_whitespace(" ".join(self._parts)))
            self._parts = None


def inspect_guidance_page(html: str, *, source_id: str, url: str) -> ParserAuditEvent:
    """Check the agency page identity before retaining it as guidance only."""
    page = urlsplit(url)
    expected = _GUIDANCE.get((page.netloc, page.path))
    parser = _PageHeadings()
    parser.feed(html)
    matches = expected is not None and parser.headings == [expected]
    return ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_guidance_snapshot",
        parser_version=PARSER_VERSION,
        status="snapshot_only" if matches else "parsed_empty",
        message="Checked the identity of the New Hampshire official guidance snapshot.",
        metadata={"heading": expected} if matches else {},
    )
