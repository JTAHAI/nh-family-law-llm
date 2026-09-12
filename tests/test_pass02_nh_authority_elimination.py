from __future__ import annotations

import json
from pathlib import Path

from legal.retrieval.query_expansion import expand_query_guarded
from scripts.scan_for_maine_authority import scan

ROOT = Path(__file__).resolve().parents[1]


def test_pass02_active_legacy_authority_scan_is_zero() -> None:
    assert scan() == []


def test_pass02_query_expansion_is_nh_scoped_and_preserves_rsa_references() -> None:
    result = expand_query_guarded("Under RSA 461-A:6, how is custody decided?")
    assert result.jurisdiction_status == "nh_expansion_allowed"
    assert result.exact_reference_preserved is True
    assert result.expansion_applied is True
    assert "residential" in result.terms
    assert "exact_reference_preserved" in result.guardrails


def test_pass02_foreign_state_scope_blocks_nh_synonym_injection_but_federal_overlay_does_not() -> None:
    foreign = expand_query_guarded("What is the Maine custody standard?")
    assert foreign.jurisdiction_status == "non_nh_review_required"
    assert foreign.expansion_applied is False
    assert "non_nh_jurisdiction_detected_no_nh_synonyms_added" in foreign.guardrails

    federal = expand_query_guarded("42 U.S.C. 666 child support withholding")
    assert federal.jurisdiction_status == "nh_default_scope"
    assert federal.exact_reference_preserved is True
    assert "non_nh_review_required" not in federal.guardrails


def test_pass02_packaging_and_launcher_use_nh_executable_identity() -> None:
    spec = (ROOT / "store/pyinstaller/nh_family_law_llm.spec").read_text(encoding="utf-8")
    old_package = "maine" + "_family_law_llm"
    old_exe = "Maine" + "FamilyLawLLM"
    assert old_package not in spec
    assert old_exe not in spec
    assert 'name="NHFamilyLawLLM"' in spec
    assert 'ROOT / "src" / "nh_family_law_llm"' in spec

    launcher = (ROOT / "START_NH_FAMILY_LAW_LLM.vbs").read_text(encoding="utf-8")
    assert "START_NH_FAMILY_LAW_LLM.cmd" in launcher


def test_pass02_enterprise_catalog_is_nh_seed_inventory_and_fail_closed() -> None:
    catalog = json.loads((ROOT / "configs/nh_enterprise_resource_catalog.json").read_text(encoding="utf-8"))
    assert catalog["jurisdiction"] == "NH"
    assert "seed inventory" in catalog["coverage_claim"]
    assert len(catalog["resources"]) >= 40
    assert all(item["jurisdiction"] == "nh" for item in catalog["resources"])
    assert all(item["retrieval_eligible"] is False for item in catalog["resources"])
    assert all(item["resource_id"].startswith("nh-") for item in catalog["resources"])


def test_pass02_ga_control_names_the_nh_authority_gate() -> None:
    policy = json.loads((ROOT / "configs/nh_ga_release_policy.json").read_text(encoding="utf-8"))
    assert "uses_real_official_nh_authority" in policy["pass_51_required_controls"]
    old_control = "uses_real_official_" + "maine_authority"
    assert old_control not in policy["pass_51_required_controls"]
