from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CitationKind = Literal["nh_statute", "nh_case", "nh_rule", "nh_form", "federal_statute"]


@dataclass(frozen=True)
class ParsedCitation:
    raw: str
    kind: CitationKind
    normalized: str
    start: int
    end: int
    title: str | None = None
    section: str | None = None
    reporter_year: str | None = None
    reporter_number: str | None = None
    rule_set: str | None = None
    rule_number: str | None = None
    form_id: str | None = None
    pinpoint: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "raw": self.raw,
            "kind": self.kind,
            "normalized": self.normalized,
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "section": self.section,
            "reporter_year": self.reporter_year,
            "reporter_number": self.reporter_number,
            "rule_set": self.rule_set,
            "rule_number": self.rule_number,
            "form_id": self.form_id,
            "pinpoint": self.pinpoint,
            "status": "unverified",
        }


# New Hampshire authorities use RSA chapter:section citations, slip-opinion
# citations such as ``2026 N.H. 12``, Judicial Branch rule abbreviations, and
# NHJB form identifiers.  The parser accepts common punctuation/OCR variants
# while retaining the exact source text in ``raw``.
_RSA_CHAPTER = r"\d+[A-Z]?(?:-[A-Z])?"
_RSA_SECTION = r"\d+[A-Z]?(?:-[A-Z])?(?:\([A-Z0-9-]+\))*"

NH_RSA_PATTERN = re.compile(
    rf"\b(?:N\.?\s*H\.?\s*)?R\.?\s*S\.?\s*A\.?\s*"
    rf"(?P<chapter>{_RSA_CHAPTER})\s*:\s*(?P<section>{_RSA_SECTION})(?![A-Z0-9])",
    re.I,
)
NH_REVISED_STATUTES_PATTERN = re.compile(
    rf"\bN\.?\s*H\.?\s+Rev\.?\s+Stat\.?\s+Ann\.?\s*§+\s*"
    rf"(?P<chapter>{_RSA_CHAPTER})\s*:\s*(?P<section>{_RSA_SECTION})(?![A-Z0-9])",
    re.I,
)
NH_CHAPTER_SECTION_PATTERN = re.compile(
    rf"\bChapter\s+(?P<chapter>{_RSA_CHAPTER})\s*,?\s*"
    rf"(?:Section|§)\s*(?P<section>{_RSA_SECTION})(?![A-Z0-9])",
    re.I,
)
NH_CASE_PATTERN = re.compile(
    r"\b(?P<year>20\d{2}|19\d{2})\s+N\.?\s*H\.?\s+(?P<number>\d+)"
    r"(?P<pinpoint>\s*,\s*(?:¶+|para\.?|paragraph)\s*\d+(?:-\d+)?)?\b",
    re.I,
)
NH_RULE_PATTERN = re.compile(
    r"\b(?P<rule_set>"
    r"N\.?\s*H\.?\s+R\.?\s+Evid\.?|"
    r"N\.?\s*H\.?\s+Sup\.?\s*Ct\.?\s+R\.?|"
    r"N\.?\s*H\.?\s+R\.?\s+Cir\.?\s*Ct\.?\s+Fam\.?\s*Div\.?|"
    r"N\.?\s*H\.?\s+R\.?\s+Civ\.?\s*P\.?"
    r")\s*(?:Rule\s*)?(?P<rule>\d+(?:\.\d+)*[A-Z]?(?:\([A-Z0-9-]+\))*)\b",
    re.I,
)
NH_FORM_PATTERN = re.compile(
    r"\bNHJB[-\s]?(?P<number>\d{3,5})[-\s]?(?P<suffix>[A-Z]{1,4})\b",
    re.I,
)
FEDERAL_STATUTE_PATTERN = re.compile(
    rf"\b(?P<title>\d+)\s*U\.?\s*S\.?\s*C\.?\s*§+\s*"
    rf"(?P<section>{_RSA_SECTION})(?![A-Z0-9])",
    re.I,
)


def normalize_nh_statute(chapter: str, section: str) -> str:
    return f"RSA {chapter.upper()}:{section.upper()}"


def normalize_nh_case(year: str, number: str) -> str:
    return f"{year} N.H. {int(number)}"


def normalize_rule(rule_set: str, rule_number: str) -> str:
    compact = re.sub(r"[^A-Z]", "", rule_set.upper())
    if "SUPCT" in compact:
        display = "N.H. Sup. Ct. R."
    elif "FAMDIV" in compact:
        display = "N.H. R. Cir. Ct. Fam. Div."
    elif "EVID" in compact:
        display = "N.H. R. Evid."
    else:
        display = "N.H. R. Civ. P."
    return f"{display} {rule_number.upper()}"


def normalize_form(number: str, suffix: str) -> str:
    return f"NHJB-{number.upper()}-{suffix.upper()}"


def normalize_federal_statute(title: str, section: str) -> str:
    return f"{title} U.S.C. § {section.upper()}"


def citation_aliases(citation: ParsedCitation) -> tuple[str, ...]:
    """Return deterministic display/search aliases for an already parsed citation."""
    aliases = {citation.normalized}
    if citation.kind == "nh_statute" and citation.title and citation.section:
        aliases.update(
            {
                f"N.H. Rev. Stat. Ann. § {citation.title}:{citation.section}",
                f"NH RSA {citation.title}:{citation.section}",
                f"Chapter {citation.title}, Section {citation.section}",
            }
        )
    elif citation.kind == "nh_form" and citation.form_id:
        aliases.add(citation.form_id.replace("-", " "))
    return tuple(sorted(aliases))


def _append_statute_match(citations: list[ParsedCitation], match: re.Match[str]) -> None:
    chapter = match.group("chapter").upper()
    section = match.group("section").upper()
    citations.append(
        ParsedCitation(
            raw=match.group(0),
            kind="nh_statute",
            normalized=normalize_nh_statute(chapter, section),
            start=match.start(),
            end=match.end(),
            title=chapter,
            section=section,
        )
    )


def extract_citations(text: str) -> list[ParsedCitation]:
    citations: list[ParsedCitation] = []
    occupied: list[tuple[int, int]] = []

    for pattern in (NH_RSA_PATTERN, NH_REVISED_STATUTES_PATTERN, NH_CHAPTER_SECTION_PATTERN):
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(span[0] < end and start < span[1] for start, end in occupied):
                continue
            _append_statute_match(citations, match)
            occupied.append(span)

    for match in NH_CASE_PATTERN.finditer(text):
        pinpoint = match.group("pinpoint")
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="nh_case",
                normalized=normalize_nh_case(match.group("year"), match.group("number")),
                start=match.start(),
                end=match.end(),
                reporter_year=match.group("year"),
                reporter_number=str(int(match.group("number"))),
                pinpoint=pinpoint.strip(" ,") if pinpoint else None,
            )
        )

    for match in NH_RULE_PATTERN.finditer(text):
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="nh_rule",
                normalized=normalize_rule(match.group("rule_set"), match.group("rule")),
                start=match.start(),
                end=match.end(),
                rule_set=match.group("rule_set"),
                rule_number=match.group("rule").upper(),
            )
        )

    for match in NH_FORM_PATTERN.finditer(text):
        form_id = normalize_form(match.group("number"), match.group("suffix"))
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="nh_form",
                normalized=form_id,
                start=match.start(),
                end=match.end(),
                form_id=form_id,
            )
        )

    for match in FEDERAL_STATUTE_PATTERN.finditer(text):
        citations.append(
            ParsedCitation(
                raw=match.group(0),
                kind="federal_statute",
                normalized=normalize_federal_statute(match.group("title"), match.group("section")),
                start=match.start(),
                end=match.end(),
                title=match.group("title"),
                section=match.group("section").upper(),
            )
        )

    return sorted(citations, key=lambda citation: (citation.start, citation.end, citation.kind))


def extract_nh_statute_citations(text: str) -> list[dict[str, str | int | None]]:
    return [citation.to_dict() for citation in extract_citations(text) if citation.kind == "nh_statute"]
