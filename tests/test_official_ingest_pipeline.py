from datetime import datetime, timezone
from pathlib import Path

from legal.connectors.base import RetrievedSource, SourceTarget
from legal.connectors.ingest_pipeline import OfficialAuthorityIngestor


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
