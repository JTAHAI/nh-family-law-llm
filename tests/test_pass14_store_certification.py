"""WACK-negative regressions: long installed QA path and PE DPI declaration.

Only fictional ZIPs are generated. No certification, signing or legal-review
claim is implied by a green source-tree regression.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


budget = _load("pass14_budget", "verify-store-path-budget.py")
dpi = _load("pass14_dpi", "verify-store-launcher-dpi.py")


def make_package(tmp_path: Path, *, name: str, member: str = "safe/fictional.txt") -> Path:
    file = tmp_path / "candidate.msix"
    manifest = f'''<?xml version="1.0"?>
    <Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
      <Identity Name="{name}" Publisher="CN=synthetic" Version="8.0.10.0" ProcessorArchitecture="x64"/>
    </Package>'''.encode()
    with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("AppxManifest.xml", manifest)
        z.writestr(member, "fictional")
    return file


def test_qa_identity_is_longer_than_production_but_bounded():
    assert budget.QA_IDENTITY == budget.PRODUCTION_IDENTITY + ".Q"
    assert len(budget.QA_IDENTITY) > len(budget.PRODUCTION_IDENTITY)
    assert len(budget.QA_IDENTITY) < len(budget.PRODUCTION_IDENTITY + ".QA123456")
    script = (ROOT / "scripts/test-store-msix-lifecycle.ps1").read_text(encoding="utf-8-sig")
    assert "$qaName = $realName + '.Q'" in script
    assert "New-SelfSignedCertificate" in script and "'CN=NHFL.IsolatedQA.' + $nonce" in script
    assert "verify-store-path-budget.py" in script


def test_wack_script_must_bind_exact_current_candidate_not_old_sha():
    content = (ROOT / "scripts/test-store-qa-wack.ps1").read_text(encoding="utf-8-sig")
    assert "ExpectedCandidateSha256" in content
    assert "$receipt.candidate_sha256 -cne $ExpectedCandidateSha256.ToLowerInvariant()" in content
    assert "$receipt.qa_identity -cne 'TAHAIWebServices.NewHampshireFamilyLawLLM.Q'" in content
    assert "69a6f22ef6d45c8a85498c5ac5ac780c21302bf4df7b9d227c23a0e0b7916937" not in content


def test_real_pass13_package_shows_old_qa_prefix_legacy_exceedance():
    # Pass 13's known longest member was 152 characters; new candidate
    # inventory is separately checked using the actual freshly built MSIX.
    longest = 152
    legacy_prefix = budget.WINDOWS_APPS_ROOT + budget.PRODUCTION_IDENTITY + ".QA123456_8.0.10.0_x64__" + "x" * 13 + "\\"
    new_prefix = budget.WINDOWS_APPS_ROOT + budget.QA_IDENTITY + "_8.0.10.0_x64__" + "x" * 13 + "\\"
    assert len(legacy_prefix) + longest > budget.MAX_FILE_LENGTH
    assert len(new_prefix) + longest <= budget.MAX_FILE_LENGTH


def test_manifest_build_spec_uses_embedded_exe_manifest():
    manifest = ROOT / "store/pyinstaller/windows-app.manifest"
    assert dpi.validate_manifest(manifest.read_bytes()) == []
    spec = (ROOT / "store/pyinstaller/nh_family_law_llm.spec").read_text()
    assert 'manifest=str(ROOT / "store" / "pyinstaller" / "windows-app.manifest")' in spec
    # MSIX package manifest alone does not satisfy WACK launcher DPI checks.
    assert 'EXE(' in spec and 'manifest=str(ROOT' in spec


@pytest.mark.parametrize("changed,blocker", [
    (b"<dpiAwareness>System</dpiAwareness>", "per_monitor_v2_missing_or_ambiguous"),
    (b"<longPathAware>false</longPathAware>", "long_path_awareness_missing_or_ambiguous"),
])
def test_bad_embedded_manifest_settings_are_blocked(changed, blocker):
    raw = b'''<assembly xmlns="urn:schemas-microsoft-com:asm.v1"><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"/></requestedPrivileges></security></trustInfo><application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings><dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness><longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">true</longPathAware></windowsSettings></application></assembly>'''
    needle = b"<dpiAwareness xmlns=\"http://schemas.microsoft.com/SMI/2016/WindowsSettings\">PerMonitorV2</dpiAwareness>" if b"dpiAwareness" in changed else b"<longPathAware xmlns=\"http://schemas.microsoft.com/SMI/2016/WindowsSettings\">true</longPathAware>"
    if b"dpiAwareness" in changed:
        raw = raw.replace(needle, changed.replace(b"<dpiAwareness>",b"<dpiAwareness xmlns=\"http://schemas.microsoft.com/SMI/2016/WindowsSettings\">"))
    else:
        raw = raw.replace(needle, changed.replace(b"<longPathAware>",b"<longPathAware xmlns=\"http://schemas.microsoft.com/SMI/2016/WindowsSettings\">"))
    assert blocker in dpi.validate_manifest(raw)


def test_dtd_manifest_is_refused():
    raw = b'<!DOCTYPE data [<!ENTITY x SYSTEM "file:///fictional">]><assembly />'
    assert dpi.validate_manifest(raw) == ["unsafe_manifest_declaration"]


@pytest.mark.parametrize("name", [budget.PRODUCTION_IDENTITY, budget.QA_IDENTITY])
def test_normal_sample_package_fits_windows_budget(name, tmp_path):
    package = make_package(tmp_path, name=name)
    result = budget.audit_msix(package)
    assert result["status"] == "pass", result
    assert result["production_ready"] is False and result["wack_qualified"] is False


def test_synthetic_long_member_fails_legacy_budget(tmp_path):
    path = make_package(tmp_path, name=budget.PRODUCTION_IDENTITY, member="fictional/" + "q" * 200)
    result = budget.audit_msix(path)
    assert "installed_path_exceeds_legacy_wack_budget" in result["blockers"]


def test_noncanonical_identity_fails_closed(tmp_path):
    package = make_package(tmp_path, name="Unknown.Publisher")
    assert budget.audit_msix(package)["status"] == "blocked"


def test_windows_traversal_alias_fails_closed(tmp_path):
    package = make_package(tmp_path, name=budget.PRODUCTION_IDENTITY, member="fictional/../outside.txt")
    assert budget.audit_msix(package)["status"] == "blocked"


def test_missing_package_fails_without_positive_report(tmp_path):
    result = budget.audit_msix(tmp_path / "missing.msix")
    assert result["status"] == "blocked"
    assert not result["wack_qualified"]
