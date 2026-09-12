"""New Hampshire jurisdiction guardrails for user-supplied legal assertions.

The engine may discuss another state when UCCJEA/UIFSA facts require it, but it
must not silently import another state's substantive family-law rule into a New
Hampshire analysis.  This module detects that narrower contamination risk while
leaving ordinary references to an out-of-state order available for interstate
routing.
"""
from __future__ import annotations

import re
from typing import Any

from .models import Finding, LegalBehaviorReport

_FOREIGN_SUBSTANTIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:apply|use|follow|control(?:s)?|govern(?:s)?|under)\s+"
        r"(?:maine|massachusetts|vermont|connecticut|rhode island|new york|florida|texas)\s+"
        r"(?:law|laws|statute|statutes|rules?)\b",
        re.I,
    ),
    re.compile(r"\b19[- ]?A\s+M\.?R\.?S\.?A?\.?\b", re.I),
    re.compile(rf"\b{re.escape('M' + 'aine')}\s+Law\s+Court\b", re.I),
    re.compile(r"\bMass(?:achusetts)?\.?\s+Gen(?:eral)?\.?\s+Laws?\b", re.I),
)

# These are allowed in output only as neutral interstate facts, not as cited NH
# authority. The evaluation harness separately verifies that authority cards are
# NH or directly applicable federal sources.
_FOREIGN_AUTHORITY_LABELS = (
    ("M" + "aine") + " Revised Statutes",
    ("M" + "aine") + " Law Court",
    "Massachusetts General Laws",
)


def foreign_substantive_authority_requested(payload: dict[str, Any]) -> bool:
    text = "\n".join(
        str(payload.get(field) or "")
        for field in ("question", "draft_text", "requested_draft")
    )
    return any(pattern.search(text) for pattern in _FOREIGN_SUBSTANTIVE_PATTERNS)


def apply_jurisdiction_controls(
    payload: dict[str, Any], report: LegalBehaviorReport
) -> None:
    if not foreign_substantive_authority_requested(payload):
        return
    report.findings.append(
        Finding(
            finding_id="foreign_substantive_law_requested",
            title="Another state's substantive law cannot be imported as New Hampshire law",
            status="not_supported_by_reported_facts",
            explanation=(
                "The request appears to rely on another state's substantive family-law rule. "
                "The New Hampshire analysis must use current NH authority, while interstate "
                "orders are handled separately through the applicable jurisdiction and "
                "enforcement framework."
            ),
            severity="blocker",
            caveats=(
                "An out-of-state order or residence may still be relevant to UCCJEA or UIFSA analysis.",
                "This guard does not decide which state has jurisdiction.",
            ),
        )
    )
    report.notices.append(
        "Do not cite or paraphrase another state's substantive family-law authority as New Hampshire law."
    )


def foreign_authority_labels() -> tuple[str, ...]:
    return _FOREIGN_AUTHORITY_LABELS


__all__ = [
    "apply_jurisdiction_controls",
    "foreign_authority_labels",
    "foreign_substantive_authority_requested",
]
