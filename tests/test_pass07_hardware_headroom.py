"""Synthetic capacity regressions: zero or hints never authorize real allocation."""
from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.fast_interchange_worker_service import ManagedWorkerError, _device_environment
from legal.model_orchestration import hardware
from legal.model_orchestration.adaptive import AdaptiveRuntimePlanner, runtime_budget
from test_adaptive_local_runtime import model, profile

GIB = 1024**3


@pytest.fixture
def measured(monkeypatch):
    monkeypatch.setattr(hardware, '_total_memory_bytes', lambda: 32 * GIB)
    monkeypatch.setattr(hardware, '_available_memory_bytes', lambda: 24 * GIB)
    monkeypatch.setattr(hardware, '_nvidia_inventory', lambda: ())
    monkeypatch.delenv('NHFL_VRAM_BYTES', raising=False)
    monkeypatch.delenv('NHFL_GPU_NAME', raising=False)
    return monkeypatch


def test_no_free_ram_remains_zero_through_profile_and_planner(measured, tmp_path):
    measured.setattr(hardware, '_available_memory_bytes', lambda: 0)
    value = hardware.profile_hardware(tmp_path)
    assert value.available_memory_bytes == 0
    assert value.recommended_concurrency == 1
    budget = runtime_budget(value)
    assert budget.memory_budget_bytes == 0
    plan = AdaptiveRuntimePlanner(value).plan(task='general_chat', models=[model()])
    assert plan['selected_model_id'] is None and plan['review_required'] is True
    assert 'insufficient_safe_memory_headroom' in plan['candidates'][0]['reasons']


def test_zero_free_vram_is_not_replaced_with_total_capacity(measured, tmp_path):
    measured.setattr(hardware, '_nvidia_inventory', lambda: ({
        'index': 0, 'uuid': 'FICTIONAL', 'name': 'Fictional GPU',
        'total_vram_bytes': 24 * GIB, 'available_vram_bytes': 0,
        'compute_capability': 8.6, 'source': 'local_driver',
    },))
    value = hardware.profile_hardware(tmp_path)
    assert value.vram_bytes == 24 * GIB and value.available_vram_bytes == 0
    plan = AdaptiveRuntimePlanner(value).plan(task='general_chat', models=[model(min_vram_bytes=4 * GIB)])
    assert plan['selected_model_id'] is None
    assert 'insufficient_vram' in plan['candidates'][0]['reasons']


def test_operator_vram_hint_is_not_measured_free_vram(measured, tmp_path):
    measured.setenv('NHFL_VRAM_BYTES', str(24 * GIB))
    measured.setenv('NHFL_GPU_NAME', 'Fictional operator hint')
    value = hardware.profile_hardware(tmp_path)
    assert value.vram_bytes == 24 * GIB  # Retain the hint for display, not admission.
    assert value.available_vram_bytes == 0
    assert value.details['gpu_capacity_source'] == 'operator_hint'
    plan = AdaptiveRuntimePlanner(value).plan(task='general_chat', models=[model(min_vram_bytes=GIB)])
    assert plan['selected_model_id'] is None


@pytest.mark.parametrize('setting', ['invalid', '-1', 'NaN', '1.5'])
def test_invalid_operator_capacity_does_not_crash_readonly_profile(measured, tmp_path, setting):
    measured.setenv('NHFL_VRAM_BYTES', setting)
    value = hardware.profile_hardware(tmp_path)
    assert value.vram_bytes == value.available_vram_bytes == 0
    assert 'invalid_vram_hint' in value.warnings
    assert json.dumps(setting) not in json.dumps(value.as_dict())


def test_driver_capacity_takes_precedence_over_unrelated_operator_hint(measured, tmp_path):
    measured.setenv('NHFL_VRAM_BYTES', str(96 * GIB))
    measured.setenv('NHFL_GPU_NAME', 'Unverified GPU')
    measured.setattr(hardware, '_nvidia_inventory', lambda: ({
        'index': 0, 'uuid': 'FICTIONAL', 'name': 'Fictional measured GPU',
        'total_vram_bytes': 8 * GIB, 'available_vram_bytes': 2 * GIB,
        'compute_capability': 8.6, 'source': 'local_driver',
    },))
    value = hardware.profile_hardware(tmp_path)
    assert value.vram_bytes == 8 * GIB and value.available_vram_bytes == 2 * GIB
    assert value.gpu_name == 'Fictional measured GPU'
    assert value.details['gpu_capacity_source'] == 'local_driver'


@pytest.mark.parametrize('available', [0, -1, GIB, 2 * GIB])
def test_budget_does_not_spend_reserved_ram(available):
    value = profile(total=8 * GIB, available=available)
    budget = runtime_budget(value)
    assert budget.memory_budget_bytes <= max(0, available - budget.reserve_bytes)
    assert AdaptiveRuntimePlanner(value).plan(task='general_chat', models=[model()])['selected_model_id'] is None


def test_zero_total_capacity_cannot_create_a_budget():
    assert runtime_budget(profile(total=0, available=8 * GIB)).memory_budget_bytes == 0


def test_zero_free_vram_remains_blocked_with_direct_profile_input():
    value = replace(profile(total=32 * GIB, available=24 * GIB, vram=24 * GIB), available_vram_bytes=0)
    plan = AdaptiveRuntimePlanner(value).plan(task='general_chat', models=[model(min_vram_bytes=GIB)])
    assert plan['selected_model_id'] is None
    assert 'insufficient_vram' in plan['candidates'][0]['reasons']


def test_positive_measured_headroom_still_selects_admitted_model():
    value = replace(profile(total=32 * GIB, available=24 * GIB, vram=24 * GIB), available_vram_bytes=12 * GIB)
    plan = AdaptiveRuntimePlanner(value).plan(task='general_chat', models=[model(min_vram_bytes=4 * GIB)])
    assert plan['status'] == 'ready' and plan['selected_model_id'] == 'local-compact'
    assert plan['network_scope'] == 'loopback_only' and plan['review_required'] is True


@pytest.mark.parametrize('capability', ['nan', 'inf', '-inf', '0', '-1'])
def test_invalid_driver_compute_capability_is_not_reported(monkeypatch, capability):
    monkeypatch.setattr(hardware.shutil, 'which', lambda name: 'fictional-nvidia-smi')
    monkeypatch.setattr(hardware, 'subprocess', SimpleNamespace(
        run=lambda *a, **k: SimpleNamespace(stdout=f'0, FICTIONAL, Fictional GPU, 8192, 4096, {capability}\n'),
        SubprocessError=subprocess.SubprocessError,
    ))
    assert hardware._nvidia_inventory() == ()


@pytest.mark.parametrize('index', [True, False, -1, 32, '0', None])
def test_ambiguous_gpu_index_cannot_start_a_worker(index):
    with pytest.raises(ManagedWorkerError, match='fast_interchange_hardware_not_ready'):
        _device_environment({'recommended_accelerator': {'index': index}, 'quantization': 'fp32'})


@pytest.mark.parametrize('count,expected', [(None, 1), (1, 1), (2, 1), (4, 2), (8, 4), (64, 4)])
def test_cpu_thread_budget_is_host_adaptive_and_bounded(monkeypatch, count, expected):
    from app.services import fast_interchange_worker_service as service
    monkeypatch.setattr(service.os, 'cpu_count', lambda: count)
    result = _device_environment({'recommended_accelerator': {'kind': 'cpu'}})
    assert result['NHFL_FAST_INTERCHANGE_CPU_THREADS'] == str(expected)
    assert result['NHFL_FAST_INTERCHANGE_FORCE_CPU'] == result['NHFL_FAST_INTERCHANGE_ALLOW_CPU'] == '1'


def test_architecture_probe_does_not_spawn_platform_file_utility(measured, tmp_path):
    import struct

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Architecture inspection must not spawn a file utility')

    measured.setattr(hardware.platform, 'architecture', forbidden)
    assert hardware.profile_hardware(tmp_path).architecture == f"{struct.calcsize('P') * 8}bit"


def test_inconsistent_ram_probe_is_clamped_to_installed_capacity(measured, tmp_path):
    measured.setattr(hardware, '_available_memory_bytes', lambda: 64 * GIB)
    value = hardware.profile_hardware(tmp_path)
    assert value.available_memory_bytes == value.total_memory_bytes == 32 * GIB
