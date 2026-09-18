import builtins
import json

from nh_family_law_llm import feature_tiers
from nh_family_law_llm.feature_tiers import feature_tier_status


def test_runtime_reports_core_and_optional_feature_packs():
    status = feature_tier_status()
    assert status["packs"]["core"]["status"] == "available"
    assert status["core_workflows_available"] is True
    assert status["default_store_tier"] == "essential"


def test_frozen_internal_layout_reads_parent_runtime_tier_stamp(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    internal = runtime / "_internal"
    internal.mkdir(parents=True)
    (runtime / "store").mkdir()
    (runtime / "store" / "feature-tier.json").write_text(
        json.dumps({"feature_tier": "essential"}), encoding="utf-8"
    )
    monkeypatch.delenv("NHFL_STORE_FEATURE_TIER", raising=False)
    monkeypatch.setattr(feature_tiers.sys, "executable", str(internal / "python.exe"))
    monkeypatch.setattr(feature_tiers.sys, "_MEIPASS", str(internal), raising=False)

    assert feature_tiers.feature_tier_status()["configured_tier"] == "essential"


def test_pyinstaller_spec_has_a_low_footprint_default_and_full_opt_in():
    text = builtins.open("store/pyinstaller/nh_family_law_llm.spec", encoding="utf-8").read()
    assert 'NHFL_STORE_FEATURE_TIER", "essential"' in text
    assert 'FEATURE_TIER == "full"' in text
    assert '"torch"' in text


def test_store_builder_skips_large_model_pack_for_essential_tier():
    text = builtins.open("scripts/build-store-runtime.ps1", encoding="utf-8").read()
    assert '[string]$FeatureTier = "essential"' in text
    assert 'if ($FeatureTier -eq "full")' in text


def test_store_build_embeds_the_selected_tier_for_the_frozen_runtime():
    builder = builtins.open("scripts/build-store-runtime.ps1", encoding="utf-8").read()
    spec = builtins.open("store/pyinstaller/nh_family_law_llm.spec", encoding="utf-8").read()
    assert "feature-tier-runtime-hook.py" in builder
    assert "NHFL_STORE_FEATURE_TIER_RUNTIME_HOOK" in builder
    assert "runtime_hooks=[FEATURE_TIER_RUNTIME_HOOK]" in spec
