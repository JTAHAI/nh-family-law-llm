"""Bundled New Hampshire family-case planning resources.

The resources in this module are local, public, non-authoritative planning aids.
They are never treated as statutes, court rules, official forms, case law, or
private matter evidence. Search runs only over the checked-in inventory.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


RESOURCE_RELATIVE = Path("resources") / "family_toolkit"
INVENTORY_NAME = "family_toolkit_inventory.json"
INVENTORY_SCHEMA = "nh_family_law_llm.family_toolkit_inventory.v1"
RESOURCE_LANE = "nh_family_toolkit_secondary_resource"


class PrintableAssetError(RuntimeError):
    """A known toolkit PDF cannot be safely opened from packaged assets."""

    def __init__(self, code: str, document_id: str, *, expected_path: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.document_id = document_id
        self.expected_path = expected_path


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve(strict=False)).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def resource_roots() -> list[Path]:
    """Return plausible toolkit roots in packaged-build priority order."""

    candidates: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", "")
    if frozen_root:
        root = Path(frozen_root)
        candidates.extend(
            [
                root / "nh_family_law_llm" / RESOURCE_RELATIVE,
                root / "src" / "nh_family_law_llm" / RESOURCE_RELATIVE,
            ]
        )
    candidates.append(Path(__file__).resolve().parent / RESOURCE_RELATIVE)
    return [path for path in _dedupe_paths(candidates) if path.is_dir()]


def resource_root() -> Path:
    roots = resource_roots()
    for candidate in roots:
        if (candidate / INVENTORY_NAME).is_file() and any(candidate.glob("*.pdf")):
            return candidate
    for candidate in roots:
        if (candidate / INVENTORY_NAME).is_file():
            return candidate
    raise RuntimeError("family_toolkit_resources_missing")


@lru_cache(maxsize=1)
def load_inventory() -> dict[str, Any]:
    payload = json.loads((resource_root() / INVENTORY_NAME).read_text(encoding="utf-8"))
    if payload.get("schema") != INVENTORY_SCHEMA:
        raise RuntimeError("family_toolkit_inventory_schema_invalid")
    if payload.get("authority_status") != "not_legal_authority":
        raise RuntimeError("family_toolkit_authority_boundary_invalid")
    return payload


def _terms(query: str) -> list[str]:
    stopwords = {
        "about",
        "all",
        "and",
        "are",
        "can",
        "do",
        "for",
        "from",
        "help",
        "how",
        "i",
        "in",
        "is",
        "me",
        "my",
        "of",
        "the",
        "to",
        "was",
        "what",
        "when",
        "where",
        "with",
        "would",
        "you",
    }
    return list(
        dict.fromkeys(
            term.lower()
            for term in re.findall(r"[A-Za-z0-9'-]{2,}", query)
            if term.lower() not in stopwords
        )
    )


def _query_phrase(query: str) -> str:
    quoted = re.search(r'"([^\"]+)"', query)
    return (quoted.group(1) if quoted else query).strip().lower()


PRACTICAL_INTENT_RULES: tuple[dict[str, Any], ...] = (
    {
        "intent": "served_or_starting",
        "triggers": (
            "served",
            "summons",
            "court papers",
            "before i call",
            "before i file",
            "where do i start",
        ),
        "expand": ("served", "papers", "deadline", "court", "file", "organize"),
        "preferred": (("before-you-file-or-call", 120),),
    },
    {
        "intent": "court_day",
        "triggers": (
            "bring to court",
            "court day",
            "prepare for court",
            "hearing",
            "what to bring",
        ),
        "expand": ("court", "hearing", "papers", "exhibits", "questions", "checklist"),
        "preferred": (("court-day-preparation", 125),),
    },
    {
        "intent": "exchange_medication",
        "triggers": (
            "exchange medication",
            "medication transfer",
            "belongings transfer",
            "handoff medication",
        ),
        "expand": ("exchange", "handoff", "medication", "belongings", "transfer"),
        "preferred": (("parenting-exchange-medication-transfer", 150),),
    },
    {
        "intent": "deadlines",
        "triggers": (
            "track deadlines",
            "deadline tracker",
            "orders dates",
            "court dates",
            "due dates",
        ),
        "expand": ("orders", "dates", "deadlines", "tracker", "hearing", "service"),
        "preferred": (("orders-dates-deadlines-tracker", 150),),
    },
    {
        "intent": "best_interest",
        "triggers": (
            "best interest",
            "best-interest",
            "rsa 461-a:6",
            "parenting modification",
        ),
        "expand": ("best", "interest", "child", "facts", "parenting", "evidence"),
        "preferred": (("best-interest-fact-organizer", 150),),
    },
    {
        "intent": "two_home_schedule",
        "triggers": (
            "two homes",
            "two-home",
            "shared parenting",
            "50/50",
            "half the week",
            "parenting schedule",
        ),
        "expand": ("two", "homes", "schedule", "school", "exchange", "parenting"),
        "preferred": (("two-home-parenting-schedule-planner", 150),),
    },
    {
        "intent": "manchester_help",
        "triggers": (
            "manchester family resources",
            "manchester legal aid",
            "hillsborough legal help",
            "low-cost lawyer",
            "legal aid intake",
        ),
        "expand": ("manchester", "hillsborough", "legal", "aid", "intake", "resources"),
        "preferred": (("manchester-family-help-preparation", 175),),
    },
)


def _intent_profile(query: str) -> tuple[list[str], list[tuple[str, int]], list[str]]:
    lowered = query.lower()
    expansions: list[str] = []
    preferred: list[tuple[str, int]] = []
    intents: list[str] = []
    for rule in PRACTICAL_INTENT_RULES:
        if any(trigger in lowered for trigger in rule["triggers"]):
            intents.append(str(rule["intent"]))
            expansions.extend(str(term) for term in rule["expand"])
            preferred.extend((str(token), int(boost)) for token, boost in rule["preferred"])
    return list(dict.fromkeys(expansions)), preferred, intents


def _preferred_boost(filename: str, preferred: list[tuple[str, int]]) -> int:
    lowered = filename.lower()
    return max((boost for token, boost in preferred if token in lowered), default=0)


def public_printable_view(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "title": document["display_title"],
        "description": document["description"],
        "category": document["category"],
        "audience": document["intended_audience"],
        "likely_use_cases": document["likely_use_cases"],
        "county": document.get("county", ""),
        "municipality": document.get("municipality", ""),
        "page_count": document["page_count"],
        "source_hash": document["source_hash"],
        "resource_lane": RESOURCE_LANE,
        "authority_status": "not_legal_authority",
        "open_path": f"/api/printables/{document['document_id']}/open",
        "preview_path": f"/api/printables/{document['document_id']}",
        "warnings": document.get("warnings", []),
    }


def get_printable(document_id: str) -> dict[str, Any] | None:
    return next(
        (
            document
            for document in load_inventory().get("documents", [])
            if document.get("document_id") == document_id
        ),
        None,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def printable_pdf_path(document_id: str, *, verify_hash: bool = True) -> Path | None:
    """Resolve a known PDF and fail closed on missing or modified bytes."""

    document = get_printable(document_id)
    if document is None:
        return None
    filename = str(document.get("original_filename") or "").strip()
    if not filename or Path(filename).name != filename or not filename.lower().endswith(".pdf"):
        raise PrintableAssetError(
            "printable_asset_path_invalid", document_id, expected_path=filename
        )
    for root in resource_roots():
        path = root / filename
        if not path.is_file():
            continue
        expected_hash = str(document.get("source_hash") or "").strip().lower()
        if verify_hash and expected_hash and _sha256_file(path).lower() != expected_hash:
            raise PrintableAssetError(
                "printable_hash_mismatch", document_id, expected_path=filename
            )
        return path
    raise PrintableAssetError("printable_asset_missing", document_id, expected_path=filename)


def audit_packaged_printables(*, verify_hashes: bool = True) -> dict[str, Any]:
    documents = list(load_inventory().get("documents", []))
    missing: list[str] = []
    mismatched: list[str] = []
    resolved: list[str] = []
    for document in documents:
        document_id = str(document.get("document_id") or "")
        try:
            path = printable_pdf_path(document_id, verify_hash=verify_hashes)
        except PrintableAssetError as exc:
            (mismatched if exc.code == "printable_hash_mismatch" else missing).append(
                document_id
            )
        else:
            if path is not None:
                resolved.append(document_id)
    return {
        "status": (
            "pass"
            if not missing and not mismatched and len(resolved) == len(documents)
            else "fail"
        ),
        "expected": len(documents),
        "resolved": len(resolved),
        "missing": missing,
        "hash_mismatches": mismatched,
        "resource_lane": RESOURCE_LANE,
        "resource_roots": [str(path) for path in resource_roots()],
    }


def _printable_family_key(document: dict[str, Any]) -> str:
    return Path(str(document.get("original_filename") or "")).stem.lower()


def search_printables(query: str, limit: int = 4) -> dict[str, Any]:
    """Search content-backed toolkit entries and apply practical intent reranking."""

    base_terms = _terms(query)
    expanded_terms, preferred, intents = _intent_profile(query)
    query_terms = list(dict.fromkeys([*base_terms, *expanded_terms]))
    phrase = _query_phrase(query)
    if not query_terms:
        return {
            "query": query,
            "exact_phrase": phrase,
            "exact_content_match": False,
            "results": [],
            "matched_intents": intents,
            "resource_lane": RESOURCE_LANE,
            "authority_status": "not_legal_authority",
        }

    scored: list[tuple[int, dict[str, Any], list[dict[str, Any]], bool, list[str]]] = []
    for document in load_inventory().get("documents", []):
        matched_chunks: list[dict[str, Any]] = []
        exact_content = False
        best_chunk_score = 0
        matched_terms: set[str] = set()
        for chunk in document.get("chunks", []):
            text = str(chunk.get("text", "")).lower()
            if not text:
                continue
            chunk_terms = {term for term in query_terms if term in text}
            phrase_match = len(phrase) >= 3 and phrase in text
            if not phrase_match and not chunk_terms:
                continue
            matched_chunks.append(chunk)
            matched_terms.update(chunk_terms)
            exact_content = exact_content or phrase_match
            best_chunk_score = max(
                best_chunk_score,
                len(chunk_terms) * 10 + (28 if phrase_match else 0),
            )
        if not matched_chunks:
            continue

        title = str(document.get("display_title") or "")
        filename = str(document.get("original_filename") or "")
        metadata_text = " ".join(
            [
                title,
                str(document.get("description") or ""),
                str(document.get("category") or ""),
                str(document.get("intended_audience") or ""),
                " ".join(str(value) for value in document.get("likely_use_cases", [])),
                str(document.get("county") or ""),
                str(document.get("municipality") or ""),
                " ".join(str(value) for value in document.get("headings", [])),
            ]
        ).lower()
        title_text = f"{title} {filename}".lower()
        metadata_matches = {term for term in query_terms if term in metadata_text}
        title_matches = {term for term in query_terms if term in title_text}
        score = (
            best_chunk_score
            + min(len(matched_chunks), 5) * 2
            + len(metadata_matches) * 5
            + len(title_matches) * 12
            + _preferred_boost(filename, preferred)
        )

        municipality = str(document.get("municipality") or "").strip().lower()
        county = str(document.get("county") or "").strip().lower()
        lowered_query = query.lower()
        if municipality and re.search(
            rf"(?<!\w){re.escape(municipality)}(?!\w)", lowered_query
        ):
            score += 140
        if county and county in lowered_query:
            score += 55

        scored.append(
            (score, document, matched_chunks, exact_content, sorted(matched_terms))
        )

    scored.sort(key=lambda row: (-row[0], row[1]["display_title"]))
    results: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for score, document, chunks, exact_content, matched_terms in scored:
        family_key = _printable_family_key(document)
        if family_key in seen_families:
            continue
        seen_families.add(family_key)
        best_chunk = max(
            chunks,
            key=lambda chunk: sum(
                1
                for term in query_terms
                if term in str(chunk.get("text", "")).lower()
            ),
        )
        view = public_printable_view(document)
        view.update(
            {
                "score": score,
                "exact_content_match": exact_content,
                "matched_pages": sorted(
                    {int(chunk.get("page_number") or 1) for chunk in chunks}
                ),
                "matched_terms": matched_terms,
                "snippet": str(best_chunk.get("text", ""))[:360],
                "why_relevant": (
                    f"Matched toolkit content for "
                    f"{', '.join(matched_terms[:6]) or 'your request'}."
                ),
                "match_basis": "curated_content_with_practical_metadata_reranking",
            }
        )
        results.append(view)
        if len(results) >= max(1, min(limit, 8)):
            break

    return {
        "query": query,
        "exact_phrase": phrase,
        "exact_content_match": any(item["exact_content_match"] for item in results),
        "results": results,
        "matched_intents": intents,
        "resource_lane": RESOURCE_LANE,
        "authority_status": "not_legal_authority",
    }


def suggest_printables(question: str, limit: int = 3) -> list[dict[str, Any]]:
    return search_printables(question, limit=limit)["results"]
