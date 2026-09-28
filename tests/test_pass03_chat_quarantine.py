"""Production cannot treat inherited prose or fixture retrieval as NH authority."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.release_boundary import production_request_active
from nh_family_law_llm import chat_library
from nh_family_law_llm.answer import compose_answer
from nh_family_law_llm.best_interest import compose_best_interest_answer
from nh_family_law_llm.safety import classify_prompt
from nh_family_law_llm.workbench import retrieve_fixture_sources


@pytest.mark.parametrize("mode", ["request_context", "store"])
@pytest.mark.parametrize("question", ["What court handles appeals?", "What are the best interest factors?"])
def test_inherited_legal_composers_are_quarantined_in_production(monkeypatch, mode, question):
    # Fixture data is deliberately passed at this unit boundary to prove that
    # even apparently supportive cards cannot enable the inherited prose.
    sources = retrieve_fixture_sources(question).results
    monkeypatch.setenv("NHFL_RUNTIME_MODE", "store" if mode == "store" else "source")
    token = production_request_active.set(mode == "request_context")
    try:
        assert chat_library.compose_library_answer(question, sources) is None
        assert compose_best_interest_answer(question, sources) is None
    finally:
        production_request_active.reset(token)


def test_production_query_expansion_does_not_inject_inherited_authorities():
    question = "What court handles appeals?"
    token = production_request_active.set(True)
    try:
        assert chat_library.expand_query_for_library(question) == question
        assert chat_library.match_chat_library(question) is None
    finally:
        production_request_active.reset(token)


def test_snippet_composition_still_available_without_precomposed_law():
    question = "What court handles appeals?"
    example = retrieve_fixture_sources(question).results[0]
    synthetic = replace(example, title="Fictional source", citation="fictional-source",
                        snippet="Fictional amber material for source-display testing only.",
                        metadata={"source_type": "synthetic", "review_required": True})
    token = production_request_active.set(True)
    try:
        answer = compose_answer(question, [synthetic], classify_prompt(question))
    finally:
        production_request_active.reset(token)
    assert "Fictional amber" in answer.answer
    assert "Supreme Judicial Court" not in answer.answer
    assert "matched_library_id" not in answer.metadata
    assert answer.review_required is True and answer.citations == (synthetic,)


@pytest.mark.parametrize("route", ["/api/question-library", "/api/starter-prompt-packs", "/api/missing-information-prompts"])
def test_production_prompt_endpoints_exclude_inherited_legal_answers(route):
    from app.api.production import app
    response = TestClient(app).get(route)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows
    encoded = json.dumps(rows, ensure_ascii=False)
    assert "Supreme Judicial Court" not in encoded
    assert "RSA § 1653" not in encoded
    if route.endswith("question-library"):
        assert all(row["answer"] == "" and row["next_steps"] == [] for row in rows)
        assert all(row["content_status"] == "prompt_only_legal_answer_quarantined" for row in rows)
        assert all(row["prompts"] and row["review_required"] is True for row in rows)
    assert production_request_active.get() is False


def test_raw_legacy_content_is_available_for_review_not_silently_rewritten(monkeypatch):
    monkeypatch.setenv("NHFL_RUNTIME_MODE", "source")
    token = production_request_active.set(False)
    try:
        raw = chat_library.public_library()
    finally:
        production_request_active.reset(token)
    assert any("Supreme Judicial Court" in row["answer"] for row in raw)


def test_legacy_audit_is_blocked_and_binds_preserved_dataset_bytes():
    import hashlib
    from pathlib import Path
    audit = chat_library.legacy_content_audit()
    raw = Path(chat_library.__file__).with_name("legacy_chat_library.py").read_bytes()
    assert audit["status"] == "blocked" and audit["legal_review_verified"] is False
    assert audit["production_templates_enabled"] is False
    assert audit["findings"] and audit["blockers"]
    assert audit["dataset_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "absence is not legal validation" in audit["scope"]


def test_prompt_pack_and_topic_counts_match_filtered_catalog():
    token = production_request_active.set(True)
    try:
        rows = chat_library.public_library()
        ids = {row["id"] for row in rows}
        topics = chat_library.public_topics()
        packs = chat_library.public_prompt_packs()
    finally:
        production_request_active.reset(token)
    assert sum(topic["count"] for topic in topics) == len(rows)
    assert len(ids) == len(rows)
    assert {"parent", "lawyer", "caregiver", "counselor", "therapist"}.issubset({row["audience"] for row in rows})
    for pack in packs:
        assert pack["prompt_count"] == len(pack["prompts"]) > 0
        assert all(row["item_id"] in ids for row in pack["prompts"])


def test_mirrored_facade_and_legacy_bytes_stay_identical():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name in ("chat_library.py", "legacy_chat_library.py"):
        assert (root / "nh_family_law_llm" / name).read_bytes() == (root / "src/nh_family_law_llm" / name).read_bytes()


def test_removing_known_markers_does_not_manufacture_legal_review(monkeypatch):
    example = chat_library._legacy.get_chat_library()[0]
    synthetic = replace(example, answer="Fictional clean text.", prompts=("Fictional prompt?",),
                        next_steps=(), keywords=(), source_terms=(), title="Fictional topic")
    monkeypatch.setattr(chat_library._legacy, "get_chat_library", lambda: (synthetic,))
    audit = chat_library.legacy_content_audit()
    assert audit["findings"] == []
    assert audit["status"] == "blocked"
    assert audit["legal_review_verified"] is False


def test_ambiguous_duplicate_ids_are_withheld_not_silently_selected(monkeypatch):
    item = chat_library._legacy.get_chat_library()[0]
    monkeypatch.setattr(chat_library._legacy, "get_chat_library", lambda: (item, replace(item, title="Different prompt")))
    token = production_request_active.set(True)
    try:
        assert chat_library.public_library() == []
    finally:
        production_request_active.reset(token)
    assert chat_library.legacy_content_audit()["duplicate_item_ids"] == [item.id]
