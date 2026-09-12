"""Shared NH authority-product fixture for API regression tests.

The full New Hampshire-specific acceptance module was intentionally removed.  Other
jurisdiction-neutral tests still import ``_authority_root``; this replacement
creates a small synthetic New Hampshire authority product without network use.
"""

from __future__ import annotations

__test__ = False

import hashlib
import json
from pathlib import Path

from legal.production import AuthorityProductPublisher


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_root(tmp_path: Path) -> Path:
    root = tmp_path / "external-authority"
    official = root / "official_authority_store"
    snapshot = official / "snapshots" / "rsa-461-a-6.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(
        "<h1>RSA 461-A:6</h1><p>Parental rights and responsibilities are decided according to the best interests of the child.</p>",
        encoding="utf-8",
    )
    source_url = "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-6.htm"
    source_id = "rsa-461-a-6"
    citation = "RSA 461-A:6"
    source_text = "Parental rights and responsibilities are decided according to the best interests of the child."

    _write_json(
        official / "source_manifest.json",
        [
            {
                "source_id": source_id,
                "source_class": "statute_section",
                "jurisdiction": "nh",
                "retrieved_at": "2026-09-11T00:00:00+00:00",
                "hash": _sha(snapshot),
                "parser_status": "parsed",
                "freshness_status": "fresh",
                "data_class": "official_public_authority",
                "source_url_or_path": source_url,
                "snapshot_path": "snapshots/rsa-461-a-6.html",
                "parser_audit": {"status": "parsed"},
            }
        ],
    )

    parsed = root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    parsed.parent.mkdir(parents=True, exist_ok=True)
    parsed.write_text(
        json.dumps(
            {
                "record_id": source_id,
                "source_id": source_id,
                "source_hash": _sha(snapshot),
                "source_class": "statute_section",
                "authority_kind": "statute_section",
                "jurisdiction": "nh",
                "authority_status": "verified_official_nh",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": len(source_text)},
                "title": "Best-interest factors",
                "citation": citation,
                "source_url_or_path": source_url,
                "text": source_text,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {
            "status": "pass",
            "record_counts": {"statutes": 1, "rules": 0, "forms": 0, "opinions": 0},
            "output_files": {"statutes/statute_sections.jsonl": str(parsed)},
        },
    )

    citation_index = _write_json(
        root / "authority_layer" / "citation_index.json",
        [
            {
                "kind": "nh_statute",
                "normalized_citation": citation,
                "source_id": source_id,
                "authority_status": "verified_official_nh",
                "metadata": {"source_class": "statute_section", "freshness_status": "fresh"},
            }
        ],
    )
    source_cards = root / "authority_layer" / "source_cards.jsonl"
    source_cards.parent.mkdir(parents=True, exist_ok=True)
    source_cards.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "title": "Best-interest factors",
                "citation": citation,
                "source_class": "statute_section",
                "jurisdiction": "nh",
                "authority_status": "verified_official_nh",
                "freshness_status": "fresh",
                "source_url_or_path": source_url,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    graph = _write_json(root / "authority_layer" / "authority_graph.json", {"nodes": [], "edges": []})
    _write_json(
        root / "authority_layer" / "authority_layer_report.json",
        {
            "status": "pass",
            "outputs": {
                "citation_index": str(citation_index),
                "authority_graph": str(graph),
                "source_cards": str(source_cards),
            },
        },
    )

    retrieval = root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    retrieval.parent.mkdir(parents=True, exist_ok=True)
    retrieval.write_text(
        json.dumps(
            {
                "record_id": source_id,
                "source_id": source_id,
                "title": "Best-interest factors",
                "citation": citation,
                "source_class": "statute_section",
                "jurisdiction": "nh",
                "authority_status": "verified_official_nh",
                "freshness_status": "fresh",
                "text": f"{citation}. {source_text}",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    exact = _write_json(
        root / "embedding_store" / "hybrid" / "exact_citation_lookup.json",
        {citation: [source_id]},
    )
    _write_json(
        root / "embedding_store" / "retrieval_index_manifest.json",
        {
            "status": "pass",
            "document_count": 1,
            "outputs": {"hybrid_documents": str(retrieval), "exact_citation_lookup": str(exact)},
        },
    )
    _write_json(
        root / "source_update_report.json",
        {"status": "pass", "freshness_counts": {"fresh": 1, "stale": 0, "unknown": 0}},
    )
    published = AuthorityProductPublisher(data_root=root, repo_root=Path.cwd()).publish(
        product_version="8.0.6-pass4"
    )
    assert published.status == "pass"
    return root
