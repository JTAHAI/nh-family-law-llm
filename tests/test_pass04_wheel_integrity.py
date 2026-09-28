"""Synthetic source, wheel and installation identity tests; no legal evidence."""
from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import stat
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal.release import wheel_integrity as integrity

DIST = 'nh_family_law_llm-8.0.10.dist-info'
ROOT = Path(__file__).resolve().parents[1]


def write_wheel(path, payload, *, repair_record=True, wire_names=None):
    payload = dict(payload)
    if repair_record:
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        for name, raw in payload.items():
            if name == DIST + '/RECORD':
                continue
            digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
            writer.writerow([name, 'sha256=' + digest, len(raw)])
        writer.writerow([DIST + '/RECORD', '', ''])
        payload[DIST + '/RECORD'] = stream.getvalue().encode()
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in payload.items():
            # Negative fixtures must retain their exact wire name on Windows
            # too. ZipInfo's constructor normalizes backslashes and truncates
            # NULs, so assign the deliberately unsafe name after construction.
            info = zipfile.ZipInfo()
            info.filename = info.orig_filename = (wire_names or {}).get(name, name)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return path


@pytest.fixture
def candidate(tmp_path):
    source = tmp_path / 'fictional-source'
    files = {
        'app/__init__.py': b'# fictional application\n',
        'legal/__init__.py': b'# fictional legal package\n',
        'legal/security/local_encryption.py': b'# fictional vault implementation\n',
        'nh_family_law_llm/__init__.py': b'# fictional package\n',
        'nh_family_law_llm/chat_library.py': b'# fictional quarantine facade\n',
        'nh_family_law_llm/ui/example.js': b'// fictional static asset\n',
    }
    for name, raw in files.items():
        path = source / ('src' if name.startswith('nh_family_law_llm/') else '') / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (source / 'pyproject.toml').write_text('''[project]
name="nh-family-law-llm"
version="8.0.10"
[project.scripts]
nhfl="nh_family_law_llm.cli:main"
[tool.setuptools.package-data]
nh_family_law_llm=["ui/*.js"]
''', encoding='utf-8')
    files.update({
        DIST + '/METADATA': b'Metadata-Version: 2.4\nName: nh-family-law-llm\nVersion: 8.0.10\n',
        DIST + '/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
        DIST + '/entry_points.txt': b'[console_scripts]\nnhfl = nh_family_law_llm.cli:main\n',
    })
    wheel = write_wheel(tmp_path / 'fictional.whl', files)
    return source, wheel, files


def test_complete_candidate_is_digest_bound_without_release_claim(candidate):
    source, wheel, _ = candidate
    report = integrity.audit_wheel(wheel, source_root=source)
    assert report['status'] == 'pass', report
    assert report['checked_file_count'] == report['package_file_count'] == 6
    assert report['wheel_sha256'] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert report['production_ready'] is report['legal_review_verified'] is report['msix_qualified'] is False


@pytest.mark.parametrize('name', ['legal/security/local_encryption.py', 'nh_family_law_llm/chat_library.py', 'nh_family_law_llm/ui/example.js'])
def test_changed_package_bytes_fail_even_with_correct_record(candidate, name):
    source, wheel, files = candidate
    files[name] += b'# fictional changed implementation\n'
    write_wheel(wheel, files)
    report = integrity.audit_wheel(wheel, source_root=source)
    assert report['blockers'] == ['wheel_source_bytes_mismatch']


@pytest.mark.parametrize('name', ['legal/security/local_encryption.py', 'nh_family_law_llm/chat_library.py', 'nh_family_law_llm/ui/example.js'])
def test_missing_security_code_or_asset_is_not_a_passing_wheel(candidate, name):
    source, wheel, files = candidate
    del files[name]
    write_wheel(wheel, files)
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['wheel_source_inventory_mismatch']


@pytest.mark.parametrize('name', ['app/untracked.py', 'legal/private.pfx', 'nh_family_law_llm/unexpected.json'])
def test_unexpected_package_files_are_rejected(candidate, name):
    source, wheel, files = candidate
    files[name] = b'fictional unexpected bytes'
    write_wheel(wheel, files)
    assert integrity.audit_wheel(wheel, source_root=source)['status'] == 'fail'


@pytest.mark.parametrize('name', ['../outside.py', '/absolute.py', 'legal/a:stream', 'legal/CON', 'legal/a./b', 'legal\\escape.py', 'legal/.git/config'])
def test_unsafe_archive_paths_are_never_accepted(candidate, name):
    source, wheel, files = candidate
    files[name] = b'fictional'
    write_wheel(wheel, files)
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['unsafe_wheel_path']



@pytest.mark.parametrize('wire_name', [
    r'nh_family_law_llm\__init__.py',
    'nh_family_law_llm/__init__.py\x00hidden',
])
def test_raw_archive_alias_cannot_hide_behind_normalized_name(candidate, monkeypatch, wire_name):
    source, wheel, files = candidate
    canonical = 'nh_family_law_llm/__init__.py'
    original_info = zipfile.ZipInfo

    class WindowsNormalizedInfo(original_info):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Exercise Windows filename normalization on every test host;
            # orig_filename retains the actual central-directory name.
            self.filename = self.filename.replace('\\', '/')

    monkeypatch.setattr(zipfile, 'ZipInfo', WindowsNormalizedInfo)
    write_wheel(wheel, files, wire_names={canonical: wire_name})
    with zipfile.ZipFile(wheel) as archive:
        info = next(item for item in archive.infolist() if item.orig_filename == wire_name)
        assert info.filename == canonical
        assert archive.read(info) == files[canonical]
    # RECORD and payload bytes are otherwise correct. It is the original
    # member name, not a checksum discrepancy, that must prevent acceptance.
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['unsafe_wheel_path']


def test_self_consistent_wheel_still_requires_expected_sha(candidate):
    source, wheel, _ = candidate
    assert integrity.audit_wheel(wheel, source_root=source, expected_sha256='0' * 64)['blockers'] == ['wheel_sha256_mismatch']


def test_record_hash_mismatch_fails_closed(candidate):
    source, wheel, files = candidate
    with zipfile.ZipFile(wheel) as archive:
        files[DIST + '/RECORD'] = archive.read(DIST + '/RECORD')
    files['legal/security/local_encryption.py'] += b'# tampered\n'
    write_wheel(wheel, files, repair_record=False)
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['wheel_record_digest_mismatch']


def test_duplicate_archive_entries_are_rejected(candidate):
    source, wheel, files = candidate
    with pytest.warns(UserWarning, match='Duplicate'):
        with zipfile.ZipFile(wheel, 'a') as archive:
            archive.writestr('app/__init__.py', files['app/__init__.py'])
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['duplicate_wheel_member']


def test_symlink_member_cannot_represent_application_code(candidate):
    source, wheel, _ = candidate
    with zipfile.ZipFile(wheel, 'a') as archive:
        info = zipfile.ZipInfo('app/linked.py')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b'../fictional')
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['nonregular_wheel_member']


@pytest.mark.parametrize('limit', ['MAX_ARCHIVE_BYTES', 'MAX_EXPANDED_BYTES', 'MAX_MEMBER_BYTES', 'MAX_MEMBERS'])
def test_archive_budgets_fail_closed(candidate, monkeypatch, limit):
    source, wheel, _ = candidate
    monkeypatch.setattr(integrity, limit, 1)
    report = integrity.audit_wheel(wheel, source_root=source)
    assert report['status'] == 'fail' and report['blockers']


def test_changed_entry_point_is_rejected(candidate):
    source, wheel, files = candidate
    files[DIST + '/entry_points.txt'] = b'[console_scripts]\nnhfl = app.different:main\n'
    write_wheel(wheel, files)
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['wheel_entry_points_mismatch']


def test_changed_source_version_is_rejected(candidate):
    source, wheel, _ = candidate
    path = source / 'pyproject.toml'
    path.write_text(path.read_text().replace('8.0.10', '8.0.11'))
    assert integrity.audit_wheel(wheel, source_root=source)['blockers'] == ['wheel_source_version_mismatch']


@pytest.fixture
def installed(candidate, tmp_path, monkeypatch):
    _, wheel, _ = candidate
    purelib = tmp_path / 'site-packages'
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(purelib)
    distribution = SimpleNamespace(locate_file=lambda path: purelib / path, version='8.0.10')
    monkeypatch.setattr(integrity, 'sysconfig', SimpleNamespace(get_path=lambda name: str(purelib)))
    monkeypatch.setattr(integrity, 'sys', SimpleNamespace(flags=SimpleNamespace(isolated=1)))
    monkeypatch.setattr(integrity, 'importlib', SimpleNamespace(
        metadata=SimpleNamespace(distribution=lambda name: distribution),
        util=SimpleNamespace(find_spec=lambda name: SimpleNamespace(origin=str(purelib / name / '__init__.py')))))
    return wheel, purelib


def test_installed_bytes_may_have_pip_record_rewrite(installed):
    wheel, purelib = installed
    (purelib / DIST / 'RECORD').write_text('fictional pip-generated record')
    report = integrity.audit_wheel(wheel, installed=True)
    assert report['status'] == 'pass', report
    assert report['interpreter_isolated'] is True
    assert report['checked_file_count'] == 9


@pytest.mark.parametrize('kind', ['changed', 'missing', 'extra'])
def test_installed_code_drift_is_rejected(installed, kind):
    wheel, purelib = installed
    target = purelib / 'legal/security/local_encryption.py'
    if kind == 'changed':
        target.write_bytes(b'# fictional stale installed code\n')
    elif kind == 'missing':
        target.unlink()
    else:
        (purelib / 'app/rogue.py').write_bytes(b'# fictional extra module\n')
    assert integrity.audit_wheel(wheel, installed=True)['status'] == 'fail'


def test_checkout_import_cannot_impersonate_installed_package(installed, monkeypatch):
    wheel, _ = installed
    monkeypatch.setattr(integrity.importlib.util, 'find_spec', lambda name: SimpleNamespace(origin=str(ROOT / name / '__init__.py')))
    assert integrity.audit_wheel(wheel, installed=True)['blockers'] == ['installed_package_origin_mismatch']


def test_unisolated_interpreter_never_qualifies(installed, monkeypatch):
    wheel, _ = installed
    monkeypatch.setattr(integrity.sys.flags, 'isolated', 0)
    assert integrity.audit_wheel(wheel, installed=True)['blockers'] == ['isolated_interpreter_required']


def test_missing_wheel_returns_safe_failure_receipt(tmp_path):
    report = integrity.audit_wheel(tmp_path / 'fictional-private-path.whl', source_root=tmp_path)
    assert report['status'] == 'fail'
    assert 'fictional-private-path' not in json.dumps(report)


def load_qualifier():
    spec = importlib.util.spec_from_file_location('pass04_desktop_qualifier', ROOT / 'scripts/qualify_nh_desktop.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installed_journey_requires_exact_wheel_before_spawning(tmp_path, monkeypatch):
    module = load_qualifier()
    output = tmp_path / 'receipt.json'
    monkeypatch.setattr(sys, 'argv', ['qualify', '--installed', '--work-dir', str(tmp_path / 'journey'), '--output', str(output)])
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: pytest.fail('Must not launch without exact wheel'))
    assert module.main() == 1
    result = json.loads(output.read_text())
    assert result['errors'] == ['exact_wheel_required_for_installed_qualification']
    assert result['launches'] == [] and result['status'] == 'fail'


def test_import_failure_still_writes_sanitized_journey_receipt(tmp_path, monkeypatch):
    module = load_qualifier()
    output = tmp_path / 'receipt.json'
    monkeypatch.setattr(sys, 'argv', ['qualify', '--work-dir', str(tmp_path / 'journey'), '--output', str(output)])
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=1, stdout='', stderr='fictional-private-directory'))
    assert module.main() == 1
    result = json.loads(output.read_text())
    assert result['errors'] == ['installed_import_probe_failed']
    assert 'fictional-private-directory' not in output.read_text()
    assert result['production_ready'] is False
