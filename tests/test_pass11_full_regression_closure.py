"""Pass 11 regressions for the final complete-suite failures.

These checks use only synthetic paths and identifiers. They verify engineering
boundaries and do not establish legal review, authority currentness, MSIX
qualification, or release readiness.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from legal.release.post_ga_review import _root_pass_logs
from legal.review.filing_packet import _normalize_changed_form_id

ROOT = Path(__file__).resolve().parents[1]


def _prelaunch_module():
    script = ROOT / "scripts" / "verify-prelaunch-release.py"
    spec = importlib.util.spec_from_file_location("pass11_verify_prelaunch", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "candidate",
    [
        r"C:\outside\candidate.msix",
        r"C:relative\candidate.msix",
        r"\\server\share\candidate.msix",
        "//server/share/candidate.msix",
        "bad\x00candidate.msix",
        "",
    ],
)
def test_candidate_resolution_rejects_cross_platform_absolute_or_invalid_paths(candidate):
    with pytest.raises(ValueError, match="inside the repository"):
        _prelaunch_module()._resolve_candidate(candidate)


def test_candidate_resolution_keeps_a_repository_relative_package_inside_checkout():
    resolved = _prelaunch_module()._resolve_candidate("dist/pass11/candidate.msix")
    assert resolved == ROOT / "dist" / "pass11" / "candidate.msix"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NHJB-9999-F", "NHJB-9999-F"),
        ("nhjb 9999 f", "NHJB-9999-F"),
        ("NHJB-12345-ABC", "NHJB-12345-ABC"),
        ("FM 123A", "FM-123A"),
    ],
)
def test_changed_form_identifiers_are_normalized_without_losing_nhjb_identity(raw, expected):
    assert _normalize_changed_form_id(raw) == expected


def test_nested_evidence_text_does_not_count_as_a_second_root_pass_log(tmp_path):
    root_pass = tmp_path / "PASS_CHANGES.txt"
    root_pass.write_text("synthetic pass control", encoding="utf-8")
    nested = tmp_path / "artifacts" / "pass-07" / "gates" / "pass07_tests.stdout.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("synthetic test output", encoding="utf-8")
    assert _root_pass_logs(tmp_path, [root_pass, nested]) == [root_pass]


def test_an_extra_root_pass_log_is_still_detected(tmp_path):
    primary = tmp_path / "PASS_CHANGES.txt"
    extra = tmp_path / "PASS_OTHER.txt"
    for path in (primary, extra):
        path.write_text("synthetic", encoding="utf-8")
    assert _root_pass_logs(tmp_path, [primary, extra]) == [primary, extra]


def test_store_build_containment_uses_platform_directory_separator():
    text = (ROOT / "scripts" / "store-build-workspace.ps1").read_text(encoding="utf-8")
    assert "[System.IO.Path]::DirectorySeparatorChar" in text
    assert "$dist + '\\'" not in text


def test_pass11_workflow_runs_focused_and_complete_suites_fail_closed():
    text = (ROOT / ".github" / "workflows" / "nh-pass11-full-regression-closure.yml").read_text(encoding="utf-8")
    assert "tests/test_pass11_full_regression_closure.py" in text
    assert "pytest', 'tests'" in text
    assert "NHFL_CI_EXTERNAL_ROOT" in text
    assert "run-public-source-preflight.py" in text
    assert "continue-on-error" not in text
    assert "if: always()" in text
