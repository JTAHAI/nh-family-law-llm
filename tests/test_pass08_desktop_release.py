from __future__ import annotations

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.nh_family_law.authorities import AuthorityGate
from nh_family_law_llm.authority_snapshot import (
    AuthorityRecord, _candidate_manifest_paths, read_verified_record, verify_record_file,
)
from nh_family_law_llm.local_workbench_ui import render_nh_review_html
from nh_family_law_llm.version import VERSION, PACKAGE_VERSION, BUILD_NUMBER

ROOT = Path(__file__).resolve().parents[1]
ROLE = {"X-User-Role": "reviewer", "X-Tenant-Id": "synthetic-pass08", "Origin": "http://127.0.0.1"}
AS_OF = "2026-09-11"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("NH_FAMILY_LAW_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("NHFL_RUNTIME_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("NHFL_AUTHORITY_DATA_ROOT", str(tmp_path / "authority"))
    from app.api.production import app
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 31234)) as value:
        yield value


def test_version_scope_and_no_windows_claim():
    scope = json.loads((ROOT / "configs/v8010_release_scope.json").read_text())
    assert VERSION == scope["release"] == "8.0.10"
    assert PACKAGE_VERSION == "8.0.10.0" and BUILD_NUMBER == 80
    assert not scope["production_ready"] and not scope["attorney_reviewed"]
    assert not scope["windows_frozen_verified"] and not scope["wack_verified"]
    assert scope["authority_promotions"] == 0


def test_production_ui_and_packaged_assets(client):
    response = client.get("/nh-review")
    assert response.status_code == 200
    assert "NH Review Desk" in response.text and "{{PRODUCT_VERSION}}" not in response.text
    assert client.get("/").text.count('href="/nh-review"') >= 1
    for path in ["/ui-assets/nh-review.js", "/ui-assets/nh-review.css", "/ui-assets/brand/nh-mark.svg", "/ui-assets/brand/nh-banner.png", "/brand-assets/css/tokens.css", "/brand-assets/assets/favicon/favicon.svg"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers["x-content-type-options"] == "nosniff"
    assert "innerHTML" not in client.get("/ui-assets/nh-review.js").text
    assert "localStorage" not in client.get("/ui-assets/nh-review.js").text


def test_review_read_routes_keep_role_and_origin_guards(client):
    assert client.get("/api/nh-review/status").status_code == 403
    headers = {**ROLE, "Origin": "https://untrusted.example"}
    assert client.get("/api/nh-review/status", headers=headers).status_code == 403
    headers = {**ROLE, "Origin": "http://127.0.0.1:7777"}
    assert client.get("/api/nh-review/status", headers=headers).status_code == 403


def test_status_is_truthful_and_contains_no_filesystem_paths(client):
    r = client.get(f"/api/nh-review/status?as_of_date={AS_OF}", headers=ROLE)
    assert r.status_code == 200
    result = r.json()
    assert result["review_required"] is True
    assert result["active_catalog_source_count"] > 0
    assert not result["exhaustive_coverage"] and not result["attorney_reviewed"]
    assert not result["support_calculator_available"] and not result["facts_persisted_by_review_routes"]
    assert "local_filename" not in r.text and str(ROOT) not in r.text
    assert "x-nhfl-audit-event-id" in r.headers


def test_production_review_source_drilldown(client):
    r = client.post("/api/legal-behavior/analyze", headers=ROLE, json={
        "question": "Review a possible parenting-plan modification and child support",
        "as_of_date": AS_OF, "parenting": {"permanent_order": True},
    })
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["review_required"] and not report["filing_ready"] and not report["legal_advice"]
    ref = next(row for row in report["authority_references"] if row["retrieval_eligible"])
    source = client.get(f'/api/nh-review/sources/{ref["authority_id"]}?as_of_date={AS_OF}', headers=ROLE)
    assert source.status_code == 200
    capsule = source.json()
    assert capsule["safe_for_direct_quote"] is False
    assert capsule["extract_is_verbatim"] is False
    assert hashlib.sha256(capsule["text"].encode()).hexdigest() == capsule["sha256"]
    assert "local_filename" not in capsule


def test_malformed_input_remains_an_error(client):
    for payload in [{"as_of_date":"not-a-date"}, {"parenting":[]}, {"question":17}]:
        r = client.post("/api/legal-behavior/analyze", headers=ROLE, json=payload)
        assert r.status_code == 422
    assert client.get("/api/nh-review/status?as_of_date=invalid", headers=ROLE).status_code == 422
    assert client.get("/api/nh-review/sources/no-such-source", headers=ROLE).status_code == 404


def test_pending_amendment_blocks_source_display(client):
    gate = AuthorityGate(as_of=date(2026,9,11))
    sources = gate.available_sources()
    source = next(row for row in sources if row["citation"] == "RSA 461-A:6")
    url = f'/api/nh-review/sources/{source["authority_id"]}?as_of_date=2026-09-13'
    assert client.get(url, headers=ROLE).status_code == 409
    result = client.get("/api/nh-review/status?as_of_date=2026-09-13", headers=ROLE).json()
    assert "RSA 461-A:6" in result["known_amendment_blocks"]


def test_explicit_missing_manifest_fails_without_leaking_path(client, monkeypatch, tmp_path):
    private_path = tmp_path / "sensitive-local-location" / "manifest.json"
    monkeypatch.setenv("NHFL_AUTHORITY_MANIFEST", str(private_path))
    for method, url, payload in [("get", "/api/nh-review/status", None), ("post", "/api/legal-behavior/analyze", {"question":"child support"})]:
        r = client.request(method, url, headers=ROLE, json=payload)
        assert r.status_code == 503
        assert "sensitive-local-location" not in r.text and str(tmp_path) not in r.text


def make_record(name, raw):
    return AuthorityRecord.from_dict({"authority_id":"NH-TEST0001","citation":"synthetic","status":"current_verified","effective_date":"2026-01-01","retrieval_eligible":True,"local_filename":name,"sha256":hashlib.sha256(raw).hexdigest()})


def test_source_bytes_verified_once(tmp_path):
    raw = b"synthetic authority bytes"; (tmp_path/"capsule.md").write_bytes(raw)
    record = make_record("capsule.md", raw)
    assert read_verified_record(record, repository_root=tmp_path) == raw
    assert verify_record_file(record, repository_root=tmp_path)
    (tmp_path/"capsule.md").write_bytes(raw+b"tampered")
    assert read_verified_record(record, repository_root=tmp_path) is None


@pytest.mark.parametrize("name", ["../outside.md", "/etc/passwd", "C:/private.md", "C:\\private.md", "\\\\server\\share", "sub/../../private.md", "capsule.md:stream"])
def test_capsule_path_escape_rejected(tmp_path, name):
    assert read_verified_record(make_record(name,b"x"), repository_root=tmp_path) is None


def test_symlink_and_oversize_capsules_rejected(tmp_path):
    (tmp_path/"real.md").write_bytes(b"synthetic")
    try: (tmp_path/"link.md").symlink_to(tmp_path/"real.md")
    except OSError: pytest.skip("symlink creation unavailable")
    assert read_verified_record(make_record("link.md",b"synthetic"), repository_root=tmp_path) is None
    assert read_verified_record(make_record("real.md",b"synthetic"), repository_root=tmp_path, max_bytes=2) is None


def test_invalid_dates_and_digests_fail_closed(tmp_path):
    raw=b"x";(tmp_path/"a.md").write_bytes(raw)
    record=make_record("a.md",raw)
    assert not replace(record,effective_date="yesterday").is_active(date.today())
    assert read_verified_record(replace(record,sha256="not-a-hash"), repository_root=tmp_path) is None


def test_installed_snapshot_never_searches_arbitrary_ancestors(monkeypatch, tmp_path):
    import nh_family_law_llm.authority_snapshot as module
    fake_module=tmp_path/"dist/venv/lib/python3.13/site-packages/nh_family_law_llm/authority_snapshot.py"
    monkeypatch.setattr(module,"__file__",str(fake_module))
    monkeypatch.delenv("NHFL_AUTHORITY_MANIFEST",raising=False)
    paths=_candidate_manifest_paths()
    assert len(paths)==1
    assert "site-packages/nh_family_law_llm/data/authority_snapshot/manifest" in paths[0].as_posix()


def test_desktop_rejects_unsafe_port_without_starting():
    from nh_family_law_llm.desktop import serve_desktop
    assert serve_desktop(port=-1)==2
    assert serve_desktop(port=65536)==2
    assert serve_desktop(port=True)==2


@pytest.mark.parametrize("uri,view", [("nhfl://review","nh-review"),("nhfl://workbench/","workbench")])
def test_view_only_protocol(uri,view):
    from nh_family_law_llm.activation import protocol_view
    assert protocol_view(uri)==view


@pytest.mark.parametrize("uri", ["nhfl://review?run=cmd", "file:///C:/private", "nhfl://review/../../file", "nhfl://user@review", "nhfl://review:80", "nhfl://review#x", "nhfl://%72eview", "nhfl://review\n", "nhfl://review\\x", "nhfl://delete-all"])
def test_protocol_rejects_execution_or_file_arguments(uri):
    from nh_family_law_llm.activation import protocol_view
    with pytest.raises(ValueError): protocol_view(uri)


def test_packaging_has_one_template_and_reserved_identity_is_not_claimed_as_confirmed():
    import xml.etree.ElementTree as ET
    first=(ROOT/'store/msix/AppxManifest.xml.in').read_bytes()
    assert first==(ROOT/'packaging/windows/AppxManifest.template.xml').read_bytes()
    manifest=ET.fromstring(first)
    ns={'uap':'http://schemas.microsoft.com/appx/manifest/uap/windows10'}
    assert manifest.find('.//uap:Protocol',ns).attrib['Name']=='nhfl'
    identity=json.loads((ROOT/'store/msix/identity.example.json').read_text())
    assert identity['identity_name'] == 'TAHAIWebServices.NHFamilyLawLLM'
    assert identity['publisher'] == 'CN=D75EE668-B409-45ED-87E5-E37AA5FE3868'
    assert identity['identity_status'] == 'reserved_partner_center_identity_submission_not_completed'
    assert identity['production_identity_confirmed'] is False


def test_shipped_runtime_configs_match_source_bytes():
    from nh_family_law_llm.runtime_resources import runtime_config_path
    folder = ROOT / 'src/nh_family_law_llm/resources/runtime/configs'
    names = sorted(p.name for p in folder.glob('*.json'))
    assert len(names) == 19
    for name in names:
        assert (folder / name).read_bytes() == (ROOT / 'configs' / name).read_bytes()
        assert runtime_config_path(name) == ROOT / 'configs' / name


@pytest.mark.parametrize('name', ['../secret.json', '/secret.json', 'folder/secret.json', r'C:\secret.json', 'a.json/..', '', 'not-json'])
def test_runtime_config_resolver_rejects_path_inputs(name):
    from nh_family_law_llm.runtime_resources import runtime_config_path
    with pytest.raises(ValueError):
        runtime_config_path(name)


def test_readonly_source_status_does_not_approve_pending_law():
    current = AuthorityGate(as_of=date(2026, 9, 11)).desktop_status()
    later = AuthorityGate(as_of=date(2026, 9, 13)).desktop_status()
    assert current['active_catalog_source_count'] > later['active_catalog_source_count']
    assert later['known_amendment_blocks']
    assert not later['exhaustive_coverage'] and not later['attorney_reviewed']


def test_citation_endpoint_never_fabricates_a_default_source_index(client):
    response = client.post('/api/citations/verify', headers=ROLE, json={'text':'RSA 461-A:6'})
    # The unsafe legacy route stays disabled on the shipped gateway.
    assert response.status_code == 404
    assert response.json()['detail'] == 'legacy_contract_not_in_release_scope'
    from app.api.main import app as development_app
    with TestClient(development_app) as development:
        result = development.post('/api/citations/verify', headers={'X-User-Role':'reviewer','X-Tenant-Id':'synthetic-pass08'}, json={'text':'RSA 461-A:6'})
    assert result.status_code == 200
    assert 'source-rsa-461-a-6' not in result.text
    assert 'not_found' in result.text
    assert result.json()['review_required'] is True


def test_deliberation_directory_guard_does_not_reverse_substring_match():
    from legal.deliberation.external_root import _contains_forbidden_segment, FORBIDDEN_SEGMENTS
    assert _contains_forbidden_segment(Path('/mnt/data/synthetic-output'), FORBIDDEN_SEGMENTS) == ''
    for path in ['/system32/output', '/WindowsApps/output', '/programdata/output']:
        assert _contains_forbidden_segment(Path(path), FORBIDDEN_SEGMENTS)
