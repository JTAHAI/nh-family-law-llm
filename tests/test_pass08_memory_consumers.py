"""Zero/invalid free capacity never authorizes warm-up or unconstrained budgets."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from legal.model_orchestration.control_center import ModelControlCenter
from legal.runtime import context_budget, low_memory_mode, warm_model_pool
from test_adaptive_local_runtime import profile
from test_pass104_warm_model_pool_acceptance import FakeWarmWorker, _admitted_model

GIB = 1024**3
UNAVAILABLE = [0, None, -1, True, False, 'unknown', float('nan'), float('inf')]


def hardware(monkeypatch, module, available):
    data = {'available_memory_bytes': available, 'total_memory_bytes': 32*GIB,
            'available_vram_bytes': 0, 'vram_bytes': 24*GIB,
            'recommended_context_limit': 8192}
    monkeypatch.setattr(module, 'profile_hardware', lambda _: SimpleNamespace(as_dict=lambda: data))
    return data


@pytest.mark.parametrize('available', UNAVAILABLE)
def test_unavailable_ram_refuses_worker_without_launch(monkeypatch, tmp_path, available):
    hardware(monkeypatch, warm_model_pool, available)
    store = warm_model_pool.WarmModelPoolStore(tmp_path, encryption_key='fictional-memory-key')
    worker = FakeWarmWorker()
    result = store.warm({'task':'summarization','user_confirmed':True},
                        model=_admitted_model(), worker=worker)
    assert result['status'] == 'not_warmed_pressure_review_required'
    assert result['pressure']['available_memory_bytes'] == 0
    assert result['pressure']['release_required'] is True
    assert result['review_required'] and not result['network_used']
    assert worker.warm_calls == worker.release_calls == 0
    assert store.status()['workers'] == []


def test_zero_free_vram_status_does_not_spend_total_capacity(monkeypatch, tmp_path):
    hardware(monkeypatch, warm_model_pool, 8*GIB)
    result = warm_model_pool.WarmModelPoolStore(tmp_path)._hardware_fit({'min_vram_bytes':GIB})
    assert result['available_vram_bytes'] == 0
    assert 'insufficient_available_vram_for_specialist' in result['blockers']


@pytest.mark.parametrize('available', UNAVAILABLE)
def test_low_memory_detects_unavailable_capacity_without_activating_it(monkeypatch, tmp_path, available):
    hardware(monkeypatch, low_memory_mode, available)
    store = low_memory_mode.LowMemoryModeStore(tmp_path, encryption_key='fictional-memory-key')
    result = store.status()
    assert result['detected_low_memory'] is True
    assert result['hardware']['available_memory_bytes'] == 0
    assert result['active'] is False
    assert result['fallbacks']['warm_workers'] == 'release'
    assert result['review_required'] and not result['network_used']
    assert not store.path.exists()


@pytest.mark.parametrize('available', UNAVAILABLE)
def test_context_budget_caps_unavailable_capacity(monkeypatch, tmp_path, available):
    hardware(monkeypatch, context_budget, available)
    store = context_budget.ContextBudgetStore(tmp_path, encryption_key='fictional-memory-key')
    result = store.create({'budget_id':'fictional-budget','task':'research',
        'requested_context_tokens':8192, 'source_refs':[{
            'source_id':'fictional-source','content_sha256':'a'*64,'char_count':24000}],
        'verifier_requirements':{'citation':True,'quote':True,'claim':True}})['budget']
    assert result['allocation']['context_tokens'] == 2048
    assert result['hardware']['available_memory_bytes'] == 0
    assert 'low_memory_context_cap_active' in result['blockers']
    assert 'requested_context_capped_by_hardware' in result['blockers']
    assert result['allocation']['verifier_reserve_tokens'] == 1920
    assert result['status'] == 'allocated_with_limits_review_required'
    assert result['review_required'] and not result['network_used']
    assert store.get('fictional-budget')['budget'] == result


@pytest.mark.parametrize('available', UNAVAILABLE)
def test_estimate_does_not_report_success_without_measured_capacity(available):
    center = ModelControlCenter.__new__(ModelControlCenter)
    center.hardware_profile = replace(profile(total=32*GIB,available=24*GIB),
                                      available_memory_bytes=available)
    result = center.estimate({'artifact_size_bytes':GIB,'context_limit_tokens':4096})
    assert result['status'] == 'constrained'
    assert 'estimated_peak_memory_exceeds_available_memory' in result['warnings']
    assert result['estimated_peak_memory_bytes'] == 3*GIB


@pytest.mark.parametrize('available,low', [(4*GIB-1,True),(4*GIB,False),(8*GIB,False)])
def test_positive_thresholds_remain_consistent(monkeypatch,tmp_path,available,low):
    for module in (warm_model_pool,low_memory_mode):
        hardware(monkeypatch,module,available)
    assert warm_model_pool.WarmModelPoolStore(tmp_path)._pressure('normal')['memory_pressure'] is low
    assert low_memory_mode.LowMemoryModeStore(tmp_path).evaluate()['detected_low_memory'] is low


def test_sufficient_measured_capacity_still_allows_warmup_and_estimate(monkeypatch,tmp_path):
    hardware(monkeypatch,warm_model_pool,8*GIB)
    worker=FakeWarmWorker()
    result=warm_model_pool.WarmModelPoolStore(tmp_path,encryption_key='fictional-memory-key').warm(
        {'task':'summarization','user_confirmed':True},model=_admitted_model(),worker=worker)
    assert result['status']=='warm_review_required' and worker.warm_calls==1
    center=ModelControlCenter.__new__(ModelControlCenter)
    center.hardware_profile=profile(total=32*GIB,available=8*GIB)
    assert center.estimate({'artifact_size_bytes':GIB})['status']=='pass'
