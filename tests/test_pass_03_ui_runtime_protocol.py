from __future__ import annotations

import importlib
import json
import os
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_product_identity_is_nh_native() -> None:
    data = json.loads((ROOT / "config" / "product_identity.json").read_text(encoding="utf-8"))
    assert data["product_name"] == "New Hampshire Family Law LLM"
    assert data["jurisdiction"]["code"] == "NH"
    assert data["uri_scheme"] == "nhfl"
    assert data["windows_aumid"] == "JTAHAI.NHFamilyLawLLM"

def test_protocol_schema_is_nh_native() -> None:
    data = json.loads((ROOT / "schemas" / "nhfl-evidence-envelope.schema.json").read_text(encoding="utf-8"))
    props = data["properties"]
    assert props["protocol"]["const"] == "nhfl"
    assert props["jurisdiction"]["const"] == "NH"

def test_brand_assets_are_packaged_in_source_tree() -> None:
    assert (ROOT / "assets" / "brand" / "nh-family-law-llm-mark.svg").is_file()
    assert (ROOT / "assets" / "brand" / "nhfl-theme.css").is_file()
    assert (ROOT / "assets" / "brand" / "nh-family-law-llm-banner.png").is_file()

def test_legacy_environment_alias_does_not_override_current(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("nh_family_law_llm.compat.legacy_environment")
    suffix = mod.KNOWN_SUFFIXES[0]
    legacy = f"{mod.LEGACY_PREFIX}{suffix}"
    current = f"{mod.CURRENT_PREFIX}{suffix}"
    env = {legacy: "legacy", current: "current"}
    assert mod.apply_legacy_environment_aliases(env) == {}
    assert env[current] == "current"

def test_legacy_environment_alias_warns_and_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("nh_family_law_llm.compat.legacy_environment")
    suffix = mod.KNOWN_SUFFIXES[0]
    legacy = f"{mod.LEGACY_PREFIX}{suffix}"
    current = f"{mod.CURRENT_PREFIX}{suffix}"
    env = {legacy: "legacy"}
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        applied = mod.apply_legacy_environment_aliases(env)
    assert applied == {legacy: current}
    assert env[current] == "legacy"
    assert any(issubclass(item.category, DeprecationWarning) for item in seen)

def test_protocol_urn() -> None:
    mod = importlib.import_module("nh_family_law_llm.protocol")
    value = mod.ProtocolEnvelope("authority").urn("rsa-461-a")
    assert value == "urn:nhfl:authority:rsa-461-a"
    assert mod.MEDIA_TYPE == "application/vnd.nhfl.evidence+json"

def test_export_metadata() -> None:
    mod = importlib.import_module("nh_family_law_llm.branding")
    data = mod.export_metadata(title="Parenting-plan research", authority_as_of="2026-09-11")
    assert data["creator"] == "New Hampshire Family Law LLM"
    assert data["jurisdiction_code"] == "NH"
    assert data["authority_as_of"] == "2026-09-11"
