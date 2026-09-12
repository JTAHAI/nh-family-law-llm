from __future__ import annotations

"""Parsers for official New Hampshire Judicial Branch rule snapshots."""

import re

from legal.connectors.base import ParserAuditEvent
from legal.connectors.html_utils import collect_links_and_text
from legal.corpus.source_normalizer import normalize_whitespace, stable_source_id
from legal.documents.models import CourtRule, SourceLocation

PARSER_VERSION = "nh_judicial_branch_rules_parser_v1"
_RULE_RE = re.compile(r"(?:^|\n|\s)Rule\s+(?P<number>\d+(?:\.\d+)*(?:-[A-Z0-9]+)?[A-Z]?)\b", re.I)
_RULE_DATE = r"(?:\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})"
_EFFECTIVE_RE = re.compile(rf"\b(?:effective|eff\.)\s*(?:date)?\s*[:,-]?\s*({_RULE_DATE})", re.I)
_AMENDMENT_RE = re.compile(rf"\b(amended|adopted|restyled|revised)\s*(?:effective\s*)?[:,-]?\s*({_RULE_DATE})", re.I)


def _infer_rule_set(text: str, url: str) -> tuple[str, str]:
    combined = f"{url}\n{text[:5000]}".lower()
    if "family division" in combined:
        return "New Hampshire Circuit Court Family Division Rules", "N.H. R. Cir. Ct. Fam. Div."
    if "rules of evidence" in combined or "evidence" in combined:
        return "New Hampshire Rules of Evidence", "N.H. R. Evid."
    if "supreme court rules" in combined or "supreme-court" in combined:
        return "Rules of the Supreme Court of New Hampshire", "N.H. Sup. Ct. R."
    if "civil procedure" in combined:
        return "New Hampshire Rules of Civil Procedure", "N.H. R. Civ. P."
    if "probate" in combined:
        return "New Hampshire Circuit Court Probate Division Rules", "N.H. R. Cir. Ct. Prob. Div."
    if "electronic filing" in combined or "e-filing" in combined or "efiling" in combined:
        return "New Hampshire Electronic Filing Rules", "N.H. E-Filing R."
    return "New Hampshire Court Rules", "N.H. Ct. R."


def _rule_history_metadata(text: str) -> tuple[str | None, list[dict[str, str]]]:
    effective = _EFFECTIVE_RE.search(text)
    history = [
        {"event": match.group(1).casefold(), "date": match.group(2)}
        for match in _AMENDMENT_RE.finditer(text)
    ]
    return (effective.group(1) if effective else None), history[:100]


def parse_rules_text(text: str, *, source_id: str, url: str) -> tuple[list[CourtRule], ParserAuditEvent]:
    visible_text = normalize_whitespace(text)
    rule_set, citation_prefix = _infer_rule_set(text, url)
    effective_date, amendment_history = _rule_history_metadata(text)
    seen: set[str] = set()
    rules: list[CourtRule] = []
    for match in _RULE_RE.finditer(text):
        rule_number = match.group("number")
        if rule_number in seen:
            continue
        seen.add(rule_number)
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 220)
        title = normalize_whitespace(text[start:end]) or f"Rule {rule_number}"
        rules.append(
            CourtRule(
                document_id=stable_source_id("nh-court-rule", f"{url}#rule-{rule_number}"),
                source_location=SourceLocation(source_id=source_id, url_or_path=f"{url}#rule-{rule_number}"),
                document_type="court_rule",
                title=title[:260],
                citation=f"{citation_prefix} {rule_number}",
                retrieved_freshness_status="retrieved_timestamp_known",
                rule_set=rule_set,
                rule_number=rule_number,
                effective_date=effective_date,
                amendment_history=list(amendment_history),
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_rules_text",
        parser_version=PARSER_VERSION,
        status="parsed" if rules else "parsed_empty",
        message="parsed New Hampshire Judicial Branch court-rules snapshot",
        extracted_count=len(rules),
        metadata={
            "text_length": len(visible_text),
            "rule_set": rule_set,
            "effective_date": effective_date,
            "amendment_event_count": len(amendment_history),
        },
    )
    return rules, event


def parse_rules_index(html: str, *, source_id: str, url: str) -> tuple[list[CourtRule], ParserAuditEvent]:
    links, visible_text = collect_links_and_text(html, base_url=url)
    rules: list[CourtRule] = []
    seen: set[str] = set()
    for link in links:
        label = normalize_whitespace(link.get("text") or "")
        href = link["href"]
        combined = f"{label} {href}"
        if "rule" not in combined.lower() and "order" not in combined.lower():
            continue
        key = href
        if key in seen:
            continue
        seen.add(key)
        rule_set, citation_prefix = _infer_rule_set(label, href)
        match = _RULE_RE.search(label)
        rule_number = match.group("number") if match else None
        rules.append(
            CourtRule(
                document_id=stable_source_id("nh-court-rule", href),
                source_location=SourceLocation(source_id=source_id, url_or_path=href),
                document_type="court_rule_reference",
                title=label or href.rsplit("/", 1)[-1],
                citation=f"{citation_prefix} {rule_number}" if rule_number else None,
                retrieved_freshness_status="official_snapshot_timestamp_required",
                rule_set=rule_set,
                rule_number=rule_number,
            )
        )
    event = ParserAuditEvent(
        source_id=source_id,
        parser_name="nh_rules_index",
        parser_version=PARSER_VERSION,
        status="parsed",
        message="parsed New Hampshire Judicial Branch rules index",
        extracted_count=len(rules),
        metadata={"text_length": len(visible_text), "reference_count": len(rules)},
    )
    return rules, event


__all__ = ["PARSER_VERSION", "parse_rules_text", "parse_rules_index"]
