from __future__ import annotations

import json
from pathlib import Path

from legal.addons import ADDON_IDS
from nh_family_law_llm.local_workbench_ui import render_local_workbench_html
from nh_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_FOOTER_LABEL, UI_VERSION, VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_v800_canonical_versions_and_about_surface_are_consistent() -> None:
    assert VERSION == "8.0.10"
    assert PACKAGE_VERSION == "8.0.10.0"
    assert BUILD_NUMBER == 80
    assert UI_VERSION == "8.0.10-pass8-b80"
    assert UI_FOOTER_LABEL == "v8.0.10 Pass 8"
    assert 'version = "8.0.10"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    html = render_local_workbench_html()
    assert "8.0.10" in html
    assert "8.0.10.0" in html


def test_v800_store_identity_is_development_only_with_new_version() -> None:
    identity = json.loads((ROOT / "store/msix/identity.example.json").read_text(encoding="utf-8"))
    # An inherited publisher GUID is not proof of an NH Store registration.
    assert identity['identity_name'] == 'NHFamilyLawLLM.LocalQA'
    assert identity['publisher'] == 'CN=NHFamilyLawLLM-LocalQA'
    assert identity['package_version'] == PACKAGE_VERSION
    assert identity['identity_status'] == 'development_example_not_store_registered'
    assert identity['production_identity_confirmed'] is False
    manifest = (ROOT / "store/msix/AppxManifest.xml.in").read_text(encoding="utf-8")
    assert 'ProcessorArchitecture="x64"' in manifest
    assert '<Resource Language="en-us" />' in manifest
    assert "x-generate" not in manifest.casefold()


def test_v800_release_scope_contains_all_and_only_verified_addons() -> None:
    scope = json.loads((ROOT / "configs/v800_release_scope.json").read_text(encoding="utf-8"))
    assert scope["decision"] == "VERSION_FROZEN"
    assert scope["acceptance_status"] == "verified_end_to_end"
    assert set(scope["public_addon_features"]) == set(ADDON_IDS)
    assert scope["release_boundaries"]["review_required"] is True
    assert scope["release_boundaries"]["enterprise_organizational_validation_claimed"] is False
