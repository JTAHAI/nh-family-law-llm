"""The retained behavior gate follows active metadata, never legal approval."""
from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location('pass07_behavior_gate', ROOT / 'scripts/verify_pass_06.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_engineering_behavior_gate_runs_without_historical_version_pin(gate, capsys):
    assert gate.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report['version'] == '8.0.10'
    assert report['scope'] == 'engineering_behavior_contract_only'
    assert report['production_ready'] is False and report['legal_review_verified'] is False
    assert report['future_effective_gate'] == 'pass'
    assert report['authority_promotions'] == 0


@pytest.mark.parametrize('field,value', [
    ('VERSION', '0.0.1'), ('PACKAGE_VERSION', '0.0.1.0'), ('BUILD_NUMBER', 999),
    ('UI_VERSION', 'incorrect-ui'), ('UI_PASS_MARKER', 'incorrect-marker'),
    ('UI_FOOTER_LABEL', 'incorrect-footer'),
])
def test_inconsistent_runtime_version_fields_still_fail_closed(gate, monkeypatch, field, value):
    monkeypatch.setattr(gate, field, value)
    with pytest.raises(SystemExit, match='FAIL:'):
        gate.main()


@pytest.mark.parametrize('field,value', [
    ('production_ready', True), ('attorney_reviewed', True), ('filing_ready', True),
    ('authority_promotions', 1), ('new_public_feature_ids', ['unearned-claim']),
    ('package_version', '0.0.1.0'),
])
def test_scope_cannot_manufacture_promotion_or_review_evidence(gate, monkeypatch, field, value):
    real = gate.load_json

    def modified(name):
        result = deepcopy(real(name))
        if name == 'configs/v8010_release_scope.json':
            result[field] = value
        return result

    monkeypatch.setattr(gate, 'load_json', modified)
    with pytest.raises(SystemExit, match='FAIL:'):
        gate.main()


def test_release_truth_cannot_select_an_arbitrary_scope_path(gate, monkeypatch):
    real = gate.load_json

    def modified(name):
        assert name != '../sensitive.json', 'Must validate before opening the scope'
        result = deepcopy(real(name))
        if name == 'configs/release_feature_truth.json':
            result['release']['release_scope'] = '../sensitive.json'
        return result

    monkeypatch.setattr(gate, 'load_json', modified)
    with pytest.raises(SystemExit, match='FAIL:'):
        gate.main()
