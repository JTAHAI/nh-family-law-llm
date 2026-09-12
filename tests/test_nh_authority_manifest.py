
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def records():
    return json.loads((ROOT/'corpus/manifest/nh_authorities.json').read_text(encoding='utf-8'))['authorities']

def test_manifest_is_nh_only():
    assert records()
    assert all(r['jurisdiction']=='NH' for r in records())

def test_core_nh_authorities_are_seeded():
    cites={r['citation'] for r in records()}
    for cite in {'RSA 461-A','RSA 458-C','RSA 161-B','RSA 161-C','RSA 458-A','RSA 546-B'}:
        assert cite in cites

def test_official_source_urls():
    assert all(r['source_url'].startswith('https://') for r in records())
    assert all('.nh.gov' in r['source_url'] or 'state.nh.us' in r['source_url'] for r in records())

def test_current_and_historical_separation_exists():
    assert (ROOT/'corpus/CURRENT_AUTHORITY').is_dir()
    assert (ROOT/'corpus/HISTORICAL_SUPERSEDED').is_dir()

def test_no_conversation_screenshot_assets():
    private_media = [
        path
        for path in ROOT.rglob('*')
        if path.is_file()
        and path.suffix.lower() in {'.jpg', '.jpeg'}
        and any(token in path.name.lower() for token in {'message', 'screenshot', 'chat-export'})
    ]
    assert private_media == []


def test_unverified_sources_are_not_current_retrieval_authority():
    assert all(r.get('retrieval_eligible') is False for r in records() if r.get('status') != 'current_verified')
    assert (ROOT/'corpus/PENDING_REVIEW').is_dir()
