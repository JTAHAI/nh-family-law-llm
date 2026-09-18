"""Regression checks for official New Hampshire authority source identities.

These tests deliberately validate only source identity (citation-to-official URL),
not a legal proposition or currentness.  Promotion remains separately gated by
preserved source bytes, effective-date review, and human legal review.
"""

from __future__ import annotations

import json
from pathlib import Path

from legal.connectors.official_source_catalog import load_official_source_targets
from nh_family_law_llm.corpus_registry import FULL_CORPUS_REQUIREMENTS


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_CHAPTER_URLS = {
    "NH-0024": "https://gc.nh.gov/rsa/html/XLIV/463/463-mrg.htm",
    "NH-0025": "https://gc.nh.gov/rsa/html/XLIV/464-A/464-A-mrg.htm",
    "NH-0027": "https://gc.nh.gov/rsa/html/LV/546-B/546-B-mrg.htm",
}

EXPECTED_SESSION_LAW_INDEX_URL = (
    "https://gc.nh.gov/bill_status/misc/chaptered_final_version.aspx"
)


def test_seed_catalog_uses_verified_general_court_title_directories():
    """Prevent reintroduction of the three observed title-directory 404s."""
    catalog = json.loads((ROOT / "config" / "nh_authority_sources.json").read_text(encoding="utf-8"))
    actual = {
        row["authority_id"]: row["source_url"]
        for row in catalog["sources"]
        if row["authority_id"] in EXPECTED_CHAPTER_URLS
    }
    assert actual == EXPECTED_CHAPTER_URLS


def test_runtime_registry_matches_verified_seed_source_identities():
    actual = {row.citation_hint: row.url for row in FULL_CORPUS_REQUIREMENTS}
    assert actual["RSA 463"] == EXPECTED_CHAPTER_URLS["NH-0024"]
    assert actual["RSA 464-A"] == EXPECTED_CHAPTER_URLS["NH-0025"]
    assert actual["RSA 546-B"] == EXPECTED_CHAPTER_URLS["NH-0027"]
    assert actual["N.H. Laws"] == EXPECTED_SESSION_LAW_INDEX_URL


def test_session_law_seed_uses_official_chaptered_final_version_index():
    catalog = json.loads((ROOT / "config" / "nh_authority_sources.json").read_text(encoding="utf-8"))
    row = next(item for item in catalog["sources"] if item["authority_id"] == "NH-0038")
    assert row["source_url"] == EXPECTED_SESSION_LAW_INDEX_URL


def test_canonical_manifest_and_embedded_snapshots_keep_seed_identities_in_sync():
    expected = {
        **EXPECTED_CHAPTER_URLS,
        "NH-0038": EXPECTED_SESSION_LAW_INDEX_URL,
    }
    canonical = ROOT / "corpus" / "manifest" / "nh_authorities.json"
    payload = json.loads(canonical.read_text(encoding="utf-8"))
    actual = {
        row["authority_id"]: row["source_url"]
        for row in payload["authorities"]
        if row["authority_id"] in expected
    }
    assert actual == expected

    # The embedded snapshots intentionally include only promoted records, not
    # every seed.  They must nevertheless never retain a superseded identity.
    obsolete = (
        "https://gc.nh.gov/rsa/html/XLIII/463/463-mrg.htm",
        "https://gc.nh.gov/rsa/html/XLIII/464-A/464-A-mrg.htm",
        "https://gc.nh.gov/legislation/",
    )
    for manifest in (
        ROOT / "nh_family_law_llm" / "data" / "authority_snapshot" / "manifest" / "nh_authorities.json",
        ROOT / "src" / "nh_family_law_llm" / "data" / "authority_snapshot" / "manifest" / "nh_authorities.json",
    ):
        text = manifest.read_text(encoding="utf-8")
        assert not any(url in text for url in obsolete)


def test_authority_build_policy_classes_are_backed_by_real_catalog_targets():
    """Do not let the production audit demand phantom source-class labels."""
    policy = json.loads((ROOT / "configs" / "nh_authority_build_policy.json").read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for target in load_official_source_targets():
        counts[target.source_class] = counts.get(target.source_class, 0) + 1
    for source_class, minimum in policy["required_source_class_minimums"].items():
        assert counts.get(source_class, 0) >= minimum
