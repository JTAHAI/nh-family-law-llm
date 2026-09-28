"""Prompt-only production facade over an unreviewed inherited chat library.

The original dataset is preserved in legacy_chat_library for development and
review. No inherited answer, next-step directive, or retrieval hint is promoted
by this facade. Production answers continue through admitted-source retrieval
and the existing assertion/currentness gates; prompts are not legal authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from app.api.release_boundary import official_authority_required
from . import legacy_chat_library as _legacy
from .legacy_chat_library import ChatLibraryItem, LibraryAnswer

DISCLAIMER = _legacy.DISCLAIMER
_CONTENT_STATUS = "prompt_only_legal_answer_quarantined"
_MARKERS = {
    "inherited_section_1653": re.compile(r"\b1653\b", re.I),
    "inherited_court_label": re.compile(r"\bsupreme\s+judicial\s+court\b", re.I),
    "inherited_foreign_title": re.compile(r"\b19[ -]a\b", re.I),
}


def _has_marker(text: str) -> bool:
    return any(pattern.search(text) for pattern in _MARKERS.values())


def _prompt_items() -> tuple[ChatLibraryItem, ...]:
    items = []
    raw_items = _legacy.get_chat_library()
    counts = Counter(item.id for item in raw_items)
    for item in raw_items:
        # Ambiguous identities cannot silently select one of two templates.
        if counts[item.id] != 1:
            continue
        # A question may be useful without endorsing its premise. Known
        # mislabeled jurisdiction identifiers are withheld rather than fixed
        # by a mechanical statute/court-name substitution.
        prompts = tuple(prompt for prompt in item.prompts if not _has_marker(prompt))
        if not prompts or _has_marker(item.title):
            continue
        items.append(replace(item, prompts=prompts, answer="", next_steps=(),
                             keywords=(), source_terms=(),
                             safety_note="Question prompt only; verify sources and obtain human review."))
    return tuple(items)


def get_chat_library() -> tuple[ChatLibraryItem, ...]:
    return _prompt_items() if official_authority_required() else _legacy.get_chat_library()


def public_library() -> list[dict[str, Any]]:
    if not official_authority_required():
        return _legacy.public_library()
    return [{**item.public_dict(), "content_status": _CONTENT_STATUS,
             "review_required": True, "attorney_reviewed": False,
             "legal_authority": False} for item in _prompt_items()]


def public_topics() -> list[dict[str, Any]]:
    if not official_authority_required():
        return _legacy.public_topics()
    items = _prompt_items()
    return [{"topic": topic, "audiences": sorted({i.audience for i in items if i.topic == topic}),
             "count": sum(i.topic == topic for i in items), "review_required": True}
            for topic in sorted({i.topic for i in items})]


def missing_information_for_item(item: ChatLibraryItem) -> list[str]:
    return _legacy.missing_information_for_item(item)


def follow_up_questions_for_item(item: ChatLibraryItem) -> list[str]:
    return _legacy.follow_up_questions_for_item(item)


def public_missing_information_prompts() -> list[dict[str, Any]]:
    if not official_authority_required():
        return _legacy.public_missing_information_prompts()
    return [{"item_id": item.id, "audience": item.audience, "topic": item.topic,
             "title": item.title, "missing_information": missing_information_for_item(item),
             "follow_up_questions": follow_up_questions_for_item(item),
             "content_status": _CONTENT_STATUS, "review_required": True}
            for item in _prompt_items()]


def public_prompt_packs() -> list[dict[str, Any]]:
    if not official_authority_required():
        return _legacy.public_prompt_packs()
    items = {item.id: item for item in _prompt_items()}
    packs = []
    for pack in _legacy.public_prompt_packs():
        if _has_marker(str(pack.get("title", "")) + str(pack.get("description", ""))):
            continue
        prompts = [{**row, "title": items[row["item_id"]].title,
                    "prompt": items[row["item_id"]].prompts[0],
                    "content_status": _CONTENT_STATUS, "review_required": True}
                   for row in pack["prompts"] if row["item_id"] in items]
        if prompts:
            packs.append({**pack, "prompts": prompts, "prompt_count": len(prompts),
                          "content_status": _CONTENT_STATUS, "review_required": True})
    return packs


def expand_query_for_library(question: str) -> str:
    if official_authority_required():
        return question
    return _legacy.expand_query_for_library(question)


def match_chat_library(question: str) -> ChatLibraryItem | None:
    if official_authority_required():
        return None
    return _legacy.match_chat_library(question)


def compose_library_answer(question, retrieval_results, *, answer_style="plain_language", matter_context="") -> LibraryAnswer | None:
    if official_authority_required():
        return None
    return _legacy.compose_library_answer(question, retrieval_results,
                                          answer_style=answer_style, matter_context=matter_context)


def legacy_content_audit() -> dict[str, Any]:
    """Inventory known defects, never certify the remainder as correct law."""
    findings = []
    for item in _legacy.get_chat_library():
        for field, value in asdict(item).items():
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            for marker, pattern in _MARKERS.items():
                if pattern.search(text):
                    findings.append({"item_id": item.id, "field": field, "marker": marker})
    return {"schema_version": "nhfl.legacy_chat_audit.v1", "status": "blocked",
            "content_status": "unreviewed_legacy_dataset",
            "production_templates_enabled": False, "legal_review_verified": False,
            "scope": "known-marker inventory only; absence is not legal validation",
            "dataset_sha256": hashlib.sha256(Path(_legacy.__file__).read_bytes()).hexdigest(),
            "item_count": len(_legacy.get_chat_library()),
            "duplicate_item_ids": sorted(key for key, count in Counter(
                item.id for item in _legacy.get_chat_library()).items() if count > 1),
            "findings": findings,
            "blockers": ["legacy_chat_requires_independent_nh_review"]}
