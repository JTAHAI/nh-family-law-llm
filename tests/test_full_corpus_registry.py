from __future__ import annotations

import json
from pathlib import Path

from nh_family_law_llm.corpus_build import (
    audit_external_corpus,
    build_required_indexes,
    fetch_live_official_corpus,
    normalize_external_corpus,
    parse_external_corpus,
    write_full_corpus_manifest,
)
from nh_family_law_llm.corpus_registry import (
    AUTHORITY_RANKING,
    FEDERAL_JURISDICTION_WARNINGS,
    REQUIRED_ATTORNEY_REVIEWED_EVALS,
    corpus_summary,
    full_corpus_manifest_entries,
)
from nh_family_law_llm.fetch import is_official_url
from nh_family_law_llm.source_manifest import SourceManifestEntry


def test_full_registry_includes_nh_court_rules_forms_and_professional_authority() -> None:
    by_id = {entry.id: entry for entry in full_corpus_manifest_entries()}

    assert "nh-family-division-rules" in by_id
    assert "nh-rules-evidence" in by_id
    assert "nh-supreme-court-rules" in by_id
    assert "nh-professional-conduct-rules" in by_id
    assert "nh-family-division-forms" in by_id
    assert "nh-supreme-court-opinions-index" in by_id
    assert by_id["nh-professional-conduct-rules"].source_type == "professional_conduct_rule"
    assert by_id["nh-family-division-rules"].authority_class == "official_nh_family_division_rule"


def test_full_registry_includes_district_of_new_hampshire_federal_lane() -> None:
    by_id = {entry.id: entry for entry in full_corpus_manifest_entries()}

    assert "district-nh-local-rules" in by_id
    assert "district-nh-pro-se-guidance" in by_id
    assert "district-nh-rules-orders" in by_id
    assert "uscode-28-1915-ifp" in by_id
    assert by_id["district-nh-local-rules"].jurisdiction == "Federal - District of New Hampshire"
    assert by_id["district-nh-rules-orders"].corpus_lane == "federal_nh_intake_and_relief"


def test_federal_official_hosts_are_allowed_for_live_fetch() -> None:
    assert is_official_url("https://www.nhd.uscourts.gov/local-rules-0")
    assert is_official_url("https://www.uscourts.gov/forms-rules/current-rules-practice-procedure")
    assert is_official_url("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1915")
    assert is_official_url("https://www.ca1.uscourts.gov/opinions")


def test_corpus_summary_tracks_nh_ga_requirements_and_warning_doctrines() -> None:
    summary = corpus_summary()

    assert summary["source_count"] >= 50
    assert "federal_nh_intake_and_relief" in summary["lanes"]
    assert "official_nh_professional_conduct" in summary["authority_classes"]
    assert "domestic_relations_exception" in FEDERAL_JURISDICTION_WARNINGS
    assert REQUIRED_ATTORNEY_REVIEWED_EVALS["federal_jurisdiction_blockers_gold.jsonl"] >= 100
    assert AUTHORITY_RANKING.index("federal_rules_primary") < AUTHORITY_RANKING.index(
        "official_federal_district_nh_local_rules"
    )


def test_external_corpus_manifest_and_audit_use_data_root(tmp_path: Path) -> None:
    manifest_path = write_full_corpus_manifest(tmp_path)
    report = audit_external_corpus(tmp_path)

    assert manifest_path == tmp_path / "manifests" / "full_corpus_manifest.json"
    assert manifest_path.is_file()
    assert report["status"] == "blocked"
    assert "official_source_raw_fetch_incomplete" in report["blockers"]
    assert "attorney_reviewed_eval_pack_incomplete" in report["blockers"]
    assert not (tmp_path / ".git").exists()


def test_live_fetch_requires_explicit_allow_live(tmp_path: Path) -> None:
    entry = SourceManifestEntry(
        id="district-nh-local-rules-test",
        title="District of New Hampshire Local Rules test",
        source_type="federal_court_rule",
        jurisdiction="Federal - District of New Hampshire",
        official=True,
        url="https://www.nhd.uscourts.gov/local-rules-0",
        effective_date="unknown_review_required",
        retrieved_at="2026-09-11T00:00:00Z",
        version_label="synthetic test manifest",
        citation_hint="D.N.H. Local Rules",
        license_or_terms_note="Official source; synthetic manifest row used by test.",
        source_priority=21,
        notes="test only",
        authority_class="official_federal_district_nh_local_rules",
        corpus_lane="federal_nh_intake_and_relief",
        parser="federal_rules_index_parser",
        freshness_status="needs_live_fetch_and_review",
        completion_status="manifested",
    )

    try:
        fetch_live_official_corpus(tmp_path, [entry], allow_live=False)
    except ValueError as exc:
        assert "allow_live=True" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("live fetch should require explicit allow_live")


def test_external_normalize_parse_and_index_pipeline_with_synthetic_raw(tmp_path: Path) -> None:
    manifest_path = write_full_corpus_manifest(tmp_path)
    entry = next(item for item in full_corpus_manifest_entries() if item.id == "nh-rsa-461-a")
    raw_dir = tmp_path / "raw" / entry.id
    raw_dir.mkdir(parents=True)
    raw_path = raw_dir / "source.html"
    raw_path.write_text(
        "<h1>TITLE XLIII</h1><h2>CHAPTER 461-A PARENTAL RIGHTS AND RESPONSIBILITIES</h2>"
        "<a href='https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-6.htm'>461-A:6 Best Interest</a>",
        encoding="utf-8",
    )
    metadata = entry.to_dict()
    metadata.update({"id": entry.id, "raw_path": str(raw_path), "sha256": "0" * 64})
    (raw_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    normalized = normalize_external_corpus(tmp_path)
    parsed = parse_external_corpus(tmp_path)
    indexed = build_required_indexes(tmp_path)
    audit = audit_external_corpus(tmp_path)

    assert manifest_path.is_file()
    assert normalized["status"] == "pass"
    assert parsed["status"] == "pass"
    assert indexed["status"] == "pass"
    assert (tmp_path / "indexes" / "exact_citation_index.json").is_file()
    assert "official_source_raw_fetch_incomplete" in audit["blockers"]
    assert "required_indexes_incomplete" not in audit["blockers"]
