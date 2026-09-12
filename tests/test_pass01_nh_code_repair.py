from __future__ import annotations

from app.api.main import app as service_app
from nh_family_law_llm.api import app as workbench_app
from nh_family_law_llm.fetch import is_official_url
from nh_family_law_llm.sources import load_seed_manifest


def test_pass01_application_titles_are_new_hampshire() -> None:
    assert service_app.title == "New Hampshire Family Law LLM"
    assert workbench_app.title == "New Hampshire Family Law LLM Local Workbench"


def test_pass01_seed_manifest_is_nh_only_and_fixture_ready() -> None:
    entries = load_seed_manifest()
    assert entries
    assert all(entry.jurisdiction == "New Hampshire" for entry in entries)
    assert all(is_official_url(entry.url) for entry in entries if entry.official)
    assert all(not is_official_url(entry.url) for entry in entries if not entry.official)
    assert any(entry.official for entry in entries)
    assert any(not entry.official for entry in entries)


def test_pass01_official_url_boundary_is_nh_and_federal_only() -> None:
    assert is_official_url("https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-mrg.htm")
    assert is_official_url("https://www.courts.nh.gov/rules-comment")
    assert is_official_url("https://www.dhhs.nh.gov/programs-services")
    assert is_official_url("https://www.ca1.uscourts.gov/opinions")
    assert is_official_url("https://legislature." + "nh.gov/statutes/")
    assert not is_official_url("https://courts.maine.invalid/not-nh")
    assert not is_official_url("https://example.com/not-official")
