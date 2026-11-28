from datetime import datetime, timezone
from pathlib import Path

from legal.connectors.base import RetrievedSource, SourceTarget
from legal.connectors.ingest_pipeline import OfficialAuthorityIngestor
from legal.connectors.nh_rules import parse_rules_index
from legal.connectors.official_source_catalog import load_official_source_targets


class StaticFetcher:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        return RetrievedSource(
            target=target,
            content=self.body,
            retrieved_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
            content_type="text/html",
            status_code=200,
            final_url=target.url,
        )


def test_ingest_pipeline_snapshots_and_manifests_official_source(tmp_path):
    target = SourceTarget(
        target_id="fixture-rsa-461-a",
        source_class="statute_title_index",
        jurisdiction="nh",
        url="https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-mrg.htm",
        parser_name="nh_general_court_chapter_index",
    )
    body = b"""
    <html><body><h1>Chapter 461-A: DOMESTIC RELATIONS</h1>
    <a href="461-A-6.htm">RSA 461-A:6. Best Interest and Parenting Schedule.</a>
    <p>Data for this page extracted on 10/20/2025 14:32:56.</p></body></html>
    """
    ingestor = OfficialAuthorityIngestor(fetcher=StaticFetcher(body), snapshot_base_dir=tmp_path)

    result = ingestor.ingest_target(target)
    manifest_path = ingestor.write_manifest([result])

    assert result.source_record.source_class == "statute_title_index"
    assert result.source_record.freshness_status == "known_extracted_timestamp"
    assert result.parser_audit.status == "parsed"
    assert result.canonical_count == 1
    assert manifest_path.exists()
    assert Path(result.snapshot_path).exists() is True
    assert "official_authority_store" not in result.snapshot_path


def test_judicial_branch_rule_books_keep_distinct_in_page_citations():
    targets = {target.target_id: target for target in load_official_source_targets()}
    target = targets["NH-0030"]
    assert target.url == "https://www.courts.nh.gov/rules-supreme-court-state-new-hampshire"
    body = """
        <nav><a href="/rules-circuit-court-state-new-hampshire-family-division">Family Division Rules</a></nav>
        <a href="#page-id-100">Rule 11. Fictional provision.</a>
        <a href="#page-id-101">Rule 12. Fictional provision.</a>
        <section id="page-id-100"></section>
        <section id="page-id-101"></section>
    """
    rows, audit = parse_rules_index(body, source_id="fictional-rules", url=target.url)
    assert audit.extracted_count == 2
    assert [row.citation for row in rows] == ["N.H. Sup. Ct. R. 11", "N.H. Sup. Ct. R. 12"]
    assert [row.source_location.url_or_path for row in rows] == [
        f"{target.url}#page-id-100", f"{target.url}#page-id-101",
    ]
    assert len({row.document_id for row in rows}) == 2
    assert all(row.retrieved_freshness_status == "official_snapshot_timestamp_required" for row in rows)


def test_administrative_index_records_matching_chapters_without_admitting_index(tmp_path):
    targets = {target.target_id: target for target in load_official_source_targets()}
    body = b"""
    <a href="http://gencourt.state.nh.us/rules/state_agencies/he-w400.html">CHAPTER He-W 400</a>
    <a href="he-w400.html">Chapter He-W 400</a>
    <a href="he-w500.html">Chapter He-W 600</a>
    <a href="he-c700.html">Chapter He-C 700</a>
    <a href="https://unaffiliated.example/rules/state_agencies/he-w800.html">Chapter He-W 800</a>
    """
    ingestor = OfficialAuthorityIngestor(fetcher=StaticFetcher(body), snapshot_base_dir=tmp_path)

    result = ingestor.ingest_target(targets["NH-0034"])

    assert result.parser_audit.status == "parsed"
    assert result.canonical_count == 1
    assert result.canonical_examples[0]["chapter"] == "He-W 400"
    assert result.source_record.metadata["retrieval_admission"] == "quarantined"
    assert result.source_record.metadata["retrieval_quarantine_review_required"] is True


def test_guidance_identity_requires_matching_h1_and_stays_quarantined(tmp_path):
    targets = {target.target_id: target for target in load_official_source_targets()}
    target = targets["NH-0036"]
    fetcher = StaticFetcher(b"<h1>Child <strong>Support</strong> Services</h1>")
    ingestor = OfficialAuthorityIngestor(fetcher=fetcher, snapshot_base_dir=tmp_path)

    result = ingestor.ingest_target(target)
    assert result.parser_audit.status == "snapshot_only"
    assert result.parser_audit.metadata["heading"] == "Child Support Services"
    assert result.canonical_count == 0
    assert result.source_record.metadata["retrieval_admission"] == "quarantined"

    fetcher.body = b"<title>Child Support Services</title><h1>Temporarily unavailable</h1>"
    rejected = ingestor.ingest_target(target)
    assert rejected.parser_audit.status == "parsed_empty"
    assert rejected.source_record.metadata["retrieval_quarantine_reason"] == "parser_status:parsed_empty"
