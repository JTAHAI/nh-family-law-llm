"""Restored deterministic retrieval contracts, not authority-admission evidence."""
from __future__ import annotations

import pytest

from legal.retrieval.models import RetrievalDocument, RetrievalResult
from legal.retrieval.retrieval_pipeline import RetrievalPipeline
from legal.verifiers.citation_resolver import SourceAuthorityIndex


def document(source_id="fictional-a", **overrides):
    values = dict(source_id=source_id, document_id=source_id + "-doc", title="Fictional evidence",
                  text="Fictional amber evidence note for retrieval testing.",
                  authority_status="user_provided_only", freshness_status="unknown")
    values.update(overrides)
    return RetrievalDocument(**values)


def test_empty_index_returns_no_sources_and_no_false_resolution():
    result = RetrievalPipeline(authority_index=SourceAuthorityIndex()).retrieve("RSA 461-A:6")
    assert result["retrieved_sources"] == result["source_cards"] == []
    assert all(row["status"] != "found" for row in result["citation_resolution_context"])
    assert result["review_required"] is True


def test_retrieval_preserves_provenance_and_excludes_text_on_request():
    item = document(metadata={"hash": "a" * 64, "source_span": {"start_offset": 1, "end_offset": 12}})
    result = RetrievalPipeline([item]).retrieve("amber evidence", include_text=False)
    assert result["retrieved_sources"]
    row = result["retrieved_sources"][0]
    assert "text" not in row["document"]
    card = row["source_card"]
    assert card["source_id"] == item.source_id and card["review_required"] is True
    assert card["authority_status"] == "user_provided_only"
    assert card["hash_value"] == "a" * 64
    assert (card["start_offset"], card["end_offset"]) == (1, 12)


def test_rank_order_is_deterministic_and_bounded():
    pipeline = RetrievalPipeline([document("fictional-b"), document("fictional-a")])
    first = pipeline.retrieve("amber evidence", top_k=1)
    second = pipeline.retrieve("amber evidence", top_k=1)
    assert first == second
    assert len(first["retrieved_sources"]) == 1
    assert first["retrieved_sources"][0]["rank"] == 1


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "2"])
def test_invalid_top_k_is_rejected_before_search(value):
    with pytest.raises(ValueError, match="top_k"):
        RetrievalPipeline([document()]).retrieve("amber", top_k=value)


def test_exact_citation_context_cannot_invent_a_document():
    index = SourceAuthorityIndex()
    index.add(kind="statute", normalized_citation="RSA 461-A:6", source_id="fictional-missing")
    result = RetrievalPipeline([document()], authority_index=index).retrieve("RSA 461-A:6 amber")
    assert all(row["source_id"] != "fictional-missing" for row in result["retrieved_sources"])


def test_diversification_deduplicates_sources_and_retains_distinct_classes():
    rows = [RetrievalResult(document("a", source_class="fictional-note"), 10, "synthetic"),
            RetrievalResult(document("a", source_class="fictional-note"), 9, "synthetic"),
            RetrievalResult(document("b", source_class="fictional-note"), 8, "synthetic"),
            RetrievalResult(document("c", source_class="fictional-table"), 7, "synthetic")]
    selected, detail = RetrievalPipeline._diversify_results(rows, top_k=3)
    assert [row.source_id for row in selected] == ["a", "c", "b"]
    assert [row.rank for row in selected] == [1, 2, 3]
    assert detail["review_required"] is True


def test_new_documents_are_searchable_without_rebuilding_pipeline():
    pipeline = RetrievalPipeline([])
    pipeline.add_documents([document()])
    assert pipeline.retrieve("amber")["retrieved_sources"][0]["source_id"] == "fictional-a"
