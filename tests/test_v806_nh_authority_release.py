"""Maintenance identity advances without enabling failed specialist candidates."""

import json
from pathlib import Path

from nh_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_v806_scope_remains_historical_while_current_release_advances():
    scope = json.loads((ROOT / "configs/v806_release_scope.json").read_text())
    current_scope = json.loads((ROOT / "configs/v8010_release_scope.json").read_text())
    truth = json.loads((ROOT / "configs/release_feature_truth.json").read_text())
    identity = json.loads((ROOT / "store/msix/identity.example.json").read_text())

    # The Pass 4 scope is immutable provenance.  The canonical product identity
    # now advances independently to the Pass 8 desktop source checkpoint.
    assert scope["release"] == "8.0.6"
    assert scope["package_version"] == "8.0.6.0"
    assert VERSION == current_scope["release"] == truth["release"]["product_version"] == "8.0.10"
    assert PACKAGE_VERSION == current_scope["package_version"] == identity["package_version"] == "8.0.10.0"
    assert BUILD_NUMBER == 80
    assert tuple(map(int, PACKAGE_VERSION.split("."))) > (8, 0, 6, 0)
    assert truth["release"]["release_scope"] == "configs/v8010_release_scope.json"
    assert current_scope["existing_feature_scope_reference"] == "configs/v809_release_scope.json"
    assert "capability_75_nh_legal_behavior_engine" in current_scope["source_reachable_feature_ids"]
    assert "capability_76_nh_legal_evaluation_harness" in current_scope["source_reachable_feature_ids"]

    assert scope["new_bundled_legal_model_ids"] == []
    assert scope["new_public_feature_ids"] == []
    assert scope["model_import_requires_production_admission"] is True
    assert scope["storage_schema_change"] is False
    assert scope["automatic_downloads"] is False
    assert identity["identity_name"] == "TAHAIWebServices.NewHampshireFamilyLawLLM"
    assert identity["publisher"] == "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868"
    assert identity["identity_status"] == "reserved_partner_center_identity_submission_not_completed"
    assert identity["production_identity_confirmed"] is False
    assert (ROOT / "src/nh_family_law_llm/version.py").read_bytes() == (
        ROOT / "nh_family_law_llm/version.py"
    ).read_bytes()
