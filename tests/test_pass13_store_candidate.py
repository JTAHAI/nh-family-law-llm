"""Store build contracts. No source test asserts Microsoft certification."""
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def _requirements(name):
    return {
        r.name.lower(): r for raw in (ROOT / 'store/pyinstaller' / name).read_text().splitlines()
        if (line := raw.strip()) and not line.startswith('#')
        for r in [Requirement(line)]
    }


def test_essential_build_keeps_core_security_versions_without_full_model_stack():
    core = _requirements('requirements-store-essential.in')
    full = _requirements('requirements-store-build.txt')
    for name in ('pyinstaller', 'pyinstaller-hooks-contrib', 'cryptography', 'pypdf', 'pypdfium2',
                 'fastapi', 'starlette', 'uvicorn', 'python-multipart', 'python-docx', 'docx-editor',
                 'pillow', 'psutil', 'pywin32'):
        assert str(core[name].specifier) == str(full[name].specifier), name
    assert {'docling', 'spacy', 'peft', 'accelerate', 'torch', 'presidio-analyzer'}.isdisjoint(core)
    assert 'defusedxml' in core
    text = (ROOT / 'scripts/build-store-runtime.ps1').read_text()
    assert 'if ($FeatureTier -eq "essential")' in text
    assert 'requirements-store-essential.in' in text
    assert 'Store runtime dependency installation failed.' in text
    assert 'Store runtime dependencies are inconsistent.' in text


def test_ocr_build_input_is_pinned_and_not_installed_on_the_host():
    text = (ROOT / 'scripts/provision-tesseract-engine.ps1').read_text()
    assert 'f3fc4236425b690c8be756f35793f77394ee004be0a6460a440c754d892f68bc' in text
    assert 'Get-FileHash' in text and 'SHA256' in text
    assert text.index('if ($actual -cne $expected)') < text.index('& $seven.Source x')
    assert 'installer_executed = $false' in text
    assert 'runtime_downloads = $false' in text
    assert 'Resolve-RepoBuildDirectory' in text
    assert 'if ($Offline)' in text
    assert 'Start-Process' not in text


def test_store_candidate_has_no_submission_or_failure_waiver():
    text = (ROOT / '.github/workflows/nh-store-candidate.yml').read_text()
    assert 'build-msix.ps1' in text and '-Unsigned' in text
    assert 'persist-credentials: false' in text
    assert 'continue-on-error' not in text
    assert 'contents: write' not in text
    assert '--index --require-ready' in text
    assert '*.pfx' not in text and '*.cer' not in text
