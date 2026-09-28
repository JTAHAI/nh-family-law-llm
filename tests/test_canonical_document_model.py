"""Restored canonical-model coverage; all text and sources are fictional."""
from __future__ import annotations

import pytest

from legal.documents.chunking import chunk_text
from legal.documents.models import CanonicalDocument, LegalChunk, SourceLocation


@pytest.mark.parametrize("text", [
    "  fictional source with leading and trailing spaces  ",
    "\n\tFictional first paragraph.\n\nSecond paragraph for testing.\n ",
    "   αβγ source 🧪 with unicode offsets.  " * 4,
    "one sentence.   another sentence.\n\n" * 10,
    "x" * 250,
])
def test_chunks_retain_exact_original_character_spans(text):
    chunks = chunk_text(document_id="fictional-doc", source_id="fictional-source",
                        text=text, max_chars=45, overlap_chars=10)
    assert chunks
    prior = -1
    for chunk in chunks:
        location = chunk.source_location
        assert 0 <= location.start_offset < location.end_offset <= len(text)
        assert location.start_offset > prior
        assert text[location.start_offset:location.end_offset] == chunk.text
        assert location.parent_id == chunk.parent_document_id == "fictional-doc"
        assert chunk.validate() == []
        prior = location.start_offset
    repeated = chunk_text(document_id="fictional-doc", source_id="fictional-source",
                          text=text, max_chars=45, overlap_chars=10)
    assert [c.to_dict() for c in chunks] == [c.to_dict() for c in repeated]


def test_chunk_spans_cover_every_non_whitespace_character():
    text = "  " + "Fictional detail.\n\nRepeated fictional detail. " * 10 + "  "
    chunks = chunk_text(document_id="d", source_id="s", text=text, max_chars=50, overlap_chars=8)
    covered = {i for c in chunks for i in range(c.source_location.start_offset, c.source_location.end_offset)}
    assert all(i in covered for i, char in enumerate(text) if not char.isspace())


@pytest.mark.parametrize("text", ["", " \t\n"])
def test_empty_document_has_no_invented_chunks(text):
    assert chunk_text(document_id="d", source_id="s", text=text) == []


@pytest.mark.parametrize("maximum,overlap", [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)])
def test_invalid_chunk_windows_are_rejected(maximum, overlap):
    with pytest.raises(ValueError):
        chunk_text(document_id="d", source_id="s", text="fictional", max_chars=maximum, overlap_chars=overlap)


def test_document_and_card_preserve_explicit_source_status():
    location = SourceLocation("fictional-source", "https://example.invalid/source", start_offset=3, end_offset=14)
    document = CanonicalDocument("fictional-doc", location, "private_record", "Fictional note",
                                 text="Fictional text", authority_status="user_provided_only",
                                 retrieved_freshness_status="unknown")
    card = document.source_card(hash_value="a" * 64).to_dict()
    assert document.validate() == []
    assert card["source_id"] == "fictional-source" and card["document_id"] == "fictional-doc"
    assert card["authority_status"] == "user_provided_only"
    assert card["freshness_status"] == "unknown" and card["review_required"] is True
    assert (card["start_offset"], card["end_offset"]) == (3, 14)
    assert card["hash_value"] == "a" * 64


def test_invalid_model_identifiers_and_offsets_are_reported():
    document = CanonicalDocument("", SourceLocation("", start_offset=-1, end_offset=-2), "", "")
    assert set(document.validate()) == {"source_id_required", "start_offset_negative",
                                       "end_offset_before_start", "document_id_required",
                                       "document_type_required", "title_required"}
    chunk = LegalChunk("", "", SourceLocation("s"), "")
    assert set(chunk.validate()) == {"chunk_id_required", "parent_document_id_required", "text_required"}
