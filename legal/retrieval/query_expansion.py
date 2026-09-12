from __future__ import annotations

import re
from dataclasses import dataclass

NH_FAMILY_LAW_SYNONYMS: dict[str, tuple[str, ...]] = {
    "custody": ("parental rights", "parental responsibilities", "residential responsibility", "parenting time"),
    "visitation": ("parenting time", "residential responsibility", "parent-child contact"),
    "parenting": ("parental rights", "parental responsibilities", "residential responsibility", "parenting schedule"),
    "parental": ("parental rights", "parental responsibilities", "residential responsibility", "best interests"),
    "responsibilities": ("parental rights", "decision-making responsibility", "residential responsibility", "best interests"),
    "support": ("child support", "medical support", "support order", "uniform support order"),
    "divorce": ("divorce", "legal separation", "domestic relations", "family division"),
    "pfa": ("protection from abuse", "domestic violence protective order", "protective order"),
    "protection": ("protection from abuse", "stalking protective order", "protective order"),
    "findings": ("findings of fact", "best interests", "written findings"),
    "appeal": ("New Hampshire Supreme Court", "standard of review", "preservation", "record on appeal"),
    "uccjea": ("child custody jurisdiction", "home state", "RSA 458-A"),
    "uifsa": ("interstate support", "registration", "RSA 546-B"),
    "form": ("NHJB form", "Family Division form", "Judicial Branch form"),
}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "the", "to", "under", "what", "when", "with",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.I)

# Mentioning another state is a scope warning. Directly relevant federal authority is not
# treated as foreign because federal overlays can govern New Hampshire family proceedings.
_NON_NH_JURISDICTION = re.compile(
    r"\b(?:maine|massachusetts|vermont|connecticut|rhode\s+island|new\s+york|"
    r"new\s+jersey|california|texas|florida)\b|\bM\.?R\.?S\.?A?\.?\b",
    re.I,
)
_NH_JURISDICTION = re.compile(
    r"\b(?:new\s+hampshire|RSA|NHJB)\b|\bN\.H\.(?:\s+Rev\.\s+Stat\.)?",
    re.I,
)
_EXACT_REFERENCE = re.compile(
    r"(?:"
    r"\bRSA\s+\d+(?:-[A-Z]+)?(?::\d+(?:-[a-z0-9]+)?)?\b|"
    r"\bN\.H\.\s+R\.\s+[A-Za-z][A-Za-z. ]*\s+\d+(?:\.\d+)?\b|"
    r"\bNHJB-?\d+[A-Za-z0-9-]*\b|"
    r"\b\d{4}\s+N\.H\.\s+\d+\b|"
    r"\b\d+\s+N\.H\.\s+\d+\b|"
    r"\b\d+\s+U\.S\.C\.\s*§?\s*\d+[A-Za-z0-9()\-]*\b|"
    r"\b\d+\s+U\.S\.\s+\d+\b"
    r")",
    re.I,
)


@dataclass(frozen=True)
class GuardedQueryExpansion:
    terms: tuple[str, ...]
    expansion_applied: bool
    jurisdiction_status: str
    exact_reference_preserved: bool
    guardrails: tuple[str, ...]

    def receipt(self) -> dict[str, object]:
        return {
            "expansion_applied": self.expansion_applied,
            "jurisdiction_status": self.jurisdiction_status,
            "exact_reference_preserved": self.exact_reference_preserved,
            "guardrails": list(self.guardrails),
            "expanded_term_count": len(self.terms),
            "review_required": True,
        }


def tokenize(text: str, *, keep_stop_words: bool = False) -> tuple[str, ...]:
    tokens = tuple(token.lower() for token in TOKEN_PATTERN.findall(text))
    if keep_stop_words:
        return tokens
    return tuple(token for token in tokens if token not in STOP_WORDS and len(token) > 1)


def expand_query_guarded(query: str) -> GuardedQueryExpansion:
    """Expand only New Hampshire family-law vocabulary without silently changing scope."""

    query = str(query or "")
    base_terms = list(tokenize(query))
    terms = list(base_terms)
    exact_reference = bool(_EXACT_REFERENCE.search(query))
    non_nh = bool(_NON_NH_JURISDICTION.search(query))
    nh = bool(_NH_JURISDICTION.search(query))
    guardrails: list[str] = []

    if non_nh:
        guardrails.append("non_nh_jurisdiction_detected_no_nh_synonyms_added")
    if exact_reference:
        guardrails.append("exact_reference_preserved")

    if not non_nh:
        lowered = query.lower()
        for trigger, expansions in NH_FAMILY_LAW_SYNONYMS.items():
            if trigger in lowered or trigger in base_terms:
                for phrase in expansions:
                    terms.extend(tokenize(phrase))
    else:
        guardrails.append("non_nh_review_required")

    seen: set[str] = set()
    ordered_terms: list[str] = []
    for term in terms:
        if term not in seen:
            ordered_terms.append(term)
            seen.add(term)

    if non_nh:
        jurisdiction_status = "non_nh_review_required"
    elif nh:
        jurisdiction_status = "nh_expansion_allowed"
    else:
        jurisdiction_status = "nh_default_scope"

    return GuardedQueryExpansion(
        terms=tuple(ordered_terms),
        expansion_applied=not non_nh and len(ordered_terms) > len(base_terms),
        jurisdiction_status=jurisdiction_status,
        exact_reference_preserved=exact_reference,
        guardrails=tuple(guardrails),
    )


def expand_query(query: str) -> tuple[str, ...]:
    """Return normalized query terms plus deterministic New Hampshire family-law synonyms."""

    return expand_query_guarded(query).terms
