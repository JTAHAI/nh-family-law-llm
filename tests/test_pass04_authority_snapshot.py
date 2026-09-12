from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

from nh_family_law_llm.authority_snapshot import (
    AuthorityRecord,
    active_records,
    default_manifest_path,
    load_payload,
    substantive_records,
    verify_record_file,
)

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"corpus/manifest/nh_authorities.json"

def payload():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

def by_citation(citation: str):
    return next(row for row in payload()["authorities"] if row["citation"]==citation)

def content(citation: str) -> str:
    row=by_citation(citation)
    return (ROOT/row["local_filename"]).read_text(encoding="utf-8")

def test_core_current_capsules_are_promoted_and_checksummed():
    data=payload()
    current=[r for r in data["authorities"] if r.get("status")=="current_verified"]
    assert len(current)>=35
    assert all(r.get("retrieval_eligible") is True for r in current)
    for row in current:
        path=ROOT/row["local_filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row["sha256"]
        assert row["raw_source_bytes_preserved"] is False
        assert row["retrieval_scope"]=="capsule_only"

def test_support_capsules_capture_current_shared_parenting_and_modification_rules():
    definitions=content("RSA 458-C:2")
    deviations=content("RSA 458-C:5")
    modification=content("RSA 458-C:7")
    assert "greater than 40 percent" in definitions
    assert "greater than 35 percent" in definitions
    assert "not greater than 10 percent" in definitions
    assert "rebuttable presumption that a $0" in deviations
    assert "does not automatically reduce support to zero" in deviations
    assert "three years after the last support order" in modification
    assert "may not take effect before notice" in modification

def test_parenting_capsules_capture_policy_findings_and_modification_gates():
    assert "approximately equal parenting time" in content("RSA 461-A:2")
    best=content("RSA 461-A:6")
    assert "must make supporting findings" in best
    assert "paragraph I-b" in best and "excluded" in best
    mod=content("RSA 461-A:11")
    assert "moving party bears the burden" in mod
    assert "statutory gates" in mod

def test_administrative_support_and_later_order_supersession_are_separated():
    no_order=content("RSA 161-C:8")
    hearing=content("RSA 161-C:9")
    assert "If no legal support order exists" in no_order
    assert "subsequent legal support order supersedes" in hearing
    assert "same force and effect as court orders" in hearing

def test_uccjea_capsules_require_home_state_analysis_and_separate_emergency_power():
    initial=content("RSA 458-A:12")
    emergency=content("RSA 458-A:15")
    assert "home state" in initial
    assert "Physical presence" in initial
    assert "temporary emergency jurisdiction" in emergency
    assert "does not automatically create permanent" in emergency

def test_future_effective_text_is_not_active_on_snapshot_date():
    rows=payload()["authorities"]
    future=[r for r in rows if r.get("status")=="future_effective_pending"]
    assert {r["effective_date"] for r in future}=={"2026-09-13","2027-01-01"}
    assert all(r["retrieval_eligible"] is False for r in future)
    active={r.citation for r in active_records(as_of=date(2026,9,11),path=MANIFEST)}
    assert all(r["citation"] not in active for r in future)

def test_snapshot_loader_enforces_scope_and_hashes():
    records=active_records(as_of=date(2026,9,11),path=MANIFEST)
    assert records
    assert all(r.retrieval_scope=="capsule_only" for r in records)
    assert all(verify_record_file(r,repository_root=ROOT) for r in records)
    assert all(r.answer_scope!="source_currentness_only" for r in substantive_records(records))
    assert len(substantive_records(records)) < len(records)

def test_court_and_dhhs_failures_are_receipted_not_promoted():
    data=payload()
    blockers=data["acquisition_blockers"]
    assert len(blockers)>=2
    assert all(b["retrieval_eligible"] is False for b in blockers)
    assert all((ROOT/b["receipt_filename"]).is_file() for b in blockers)


def test_default_manifest_resolves_and_validates():
    manifest = default_manifest_path()
    assert manifest.is_file()
    data = load_payload(manifest)
    assert data["as_of_date"] == "2026-09-11"
    assert any(row.get("status") == "current_verified" for row in data["authorities"])

def test_packaged_snapshots_are_built_for_both_package_layouts():
    for package in (ROOT / "nh_family_law_llm", ROOT / "src" / "nh_family_law_llm"):
        embedded = package / "data" / "authority_snapshot" / "manifest" / "nh_authorities.json"
        assert embedded.is_file()
        data = json.loads(embedded.read_text(encoding="utf-8"))
        assert data["authority_count"] == 39
        assert {row["status"] for row in data["authorities"]} == {
            "current_verified",
            "future_effective_pending",
        }
