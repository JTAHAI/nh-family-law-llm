"""Isolation contracts, not a substitute for real Windows installation."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_qa_is_host_limited_and_never_uses_real_store_identity():
    text=(ROOT/'scripts/test-store-msix-lifecycle.ps1').read_text()
    assert "RUNNER_ENVIRONMENT -ne 'github-hosted'" in text
    assert '-not $IsolatedTestEnvironment' in text
    assert text.index('disposable GitHub-hosted Windows runners') < text.index('New-Item -ItemType Directory -Path $work')
    assert "$qaName = $realName + '.QA' + $nonce" in text
    assert '$manifest.Package.Identity.Name = $qaName' in text
    assert '-KeyExportPolicy NonExportable' in text
    assert 'Export-PfxCertificate' not in text
    assert "'Cert:\\LocalMachine\\TrustedPeople'" in text
    assert 'Cert:\\LocalMachine\\Root' not in text


def test_qa_receipt_requires_package_identity_byte_checks_and_cleanup():
    text=(ROOT/'scripts/test-store-msix-lifecycle.ps1').read_text()
    for required in ('GetCurrentPackageFullName','-PreventBreakaway','Assert-InstalledBytes',
                     'candidate_sha256','external_marker_preserved','cleanup_complete',
                     "'graphical-launcher' -Gui",'PrintWindow','Remove-AppxPackage'):
        assert required in text
    assert 'production_identity_installed=$false' in text
    assert 'production_ready=$false' in text
    assert 'wack_qualified=$false' in text


def test_qa_download_is_exact_build_and_does_not_upload_certificates():
    text=(ROOT/'.github/workflows/nh-store-installed-qualification.yml').read_text()
    assert '42584016414' in text and '6e1208291e26bd5f86333888e9927c5f5dd12c33' in text
    assert 'continue-on-error' not in text
    assert 'contents: write' not in text
    assert 'candidate_sha256' in (ROOT/'scripts/test-store-msix-lifecycle.ps1').read_text()
    assert '*.pfx' not in text and '*.cer' not in text and '*.msix' not in text.split('uses: actions/upload-artifact')[1]
