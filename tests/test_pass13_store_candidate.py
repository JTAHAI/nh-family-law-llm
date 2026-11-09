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
    import json
    manifest = json.loads((ROOT / 'store/native/tesseract/vcpkg.json').read_text())
    assert manifest['builtin-baseline'] == 'ec48c11eae9448c8c6e7739d93e06fa2433aa95f'
    assert manifest['dependencies'] == [{'name': 'tesseract', 'default-features': False}]
    assert '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2' in text
    assert '9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff' in text
    assert 'Get-FileHash' in text and 'SHA256' in text
    assert 'installer_executed=$false' in text
    assert 'runtime_downloads=$false' in text and 'native_url_reading=$false' in text
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


def _spec_function(name):
    import ast
    path = ROOT / 'store/pyinstaller/nh_family_law_llm.spec'
    node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {'Path': Path}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


def test_frozen_resources_cover_every_declared_wheel_resource():
    import tomllib
    package = ROOT / 'src/nh_family_law_llm'
    collect = _spec_function('collect_source_package_files')
    actual = {Path(source) for source, _ in collect(package, destination='nh_family_law_llm')}
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    expected = {p for pattern in config['tool']['setuptools']['package-data']['nh_family_law_llm']
                for p in package.glob(pattern) if p.is_file()}
    assert expected <= actual, sorted(str(p.relative_to(package)) for p in expected - actual)


def test_canonical_source_hook_and_post_analysis_completeness_gate():
    import importlib.util
    from types import SimpleNamespace
    path = ROOT / 'store/pyinstaller/hooks/pre_find_module_path/hook-nh_family_law_llm.py'
    spec = importlib.util.spec_from_file_location('canonical_source_hook', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    api = SimpleNamespace(search_dirs=[str(ROOT)])
    module.pre_find_module_path(api)
    assert api.search_dirs == [str(ROOT / 'src')]
    text = (ROOT / 'store/pyinstaller/nh_family_law_llm.spec').read_text()
    assert 'hookspath=[str(ROOT / "store" / "pyinstaller" / "hooks")]' in text
    assert 'incomplete_canonical_frozen_application' in text
    assert text.index('incomplete_canonical_frozen_application') < text.index('pyz = PYZ')
