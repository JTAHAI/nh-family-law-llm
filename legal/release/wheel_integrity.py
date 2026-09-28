"""Byte-bound source/wheel/installation checks; no release or legal approval.

This module deliberately uses only the standard library. The qualification
harness executes this file with the installed interpreter's -I flag, before
importing the application, so a checkout import cannot disguise a stale wheel.
"""
from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import re
import stat
import sys
import sysconfig
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 10000
PACKAGES = ('app', 'legal', 'nh_family_law_llm')
_DEVICE = re.compile(r'(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$')


class WheelIntegrityError(ValueError):
    """A non-secret error code, never archive contents or local paths."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise WheelIntegrityError(code)


def _regular_bytes(path: Path, maximum: int) -> bytes:
    for component in (path, *path.parents):
        metadata = component.lstat()
        _require(not stat.S_ISLNK(metadata.st_mode) and not
                 (getattr(metadata, 'st_file_attributes', 0) & 0x400), 'linked_path_refused')
    metadata = path.stat()
    _require(stat.S_ISREG(metadata.st_mode), 'regular_file_required')
    _require(metadata.st_size <= maximum, 'file_size_limit_exceeded')
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    _require(len(data) <= maximum, 'file_size_limit_exceeded')
    return data


def _safe_name(name: str) -> None:
    parts = name.split('/')
    _require(bool(name) and not PurePosixPath(name).is_absolute() and '\\' not in name
             and ':' not in name and not any(ord(c) < 32 or ord(c) == 127 for c in name)
             and all(part not in {'', '.', '..'} and part.casefold() != '.git'
                     and part.rstrip(' .') == part and not _DEVICE.fullmatch(part)
                     for part in parts), 'unsafe_wheel_path')


def _read_wheel(wheel: Path) -> tuple[dict[str, bytes], str, Any, str]:
    raw = _regular_bytes(wheel.absolute(), MAX_ARCHIVE_BYTES)
    wheel_hash = hashlib.sha256(raw).hexdigest()
    members: dict[str, bytes] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        _require(0 < len(entries) <= MAX_MEMBERS, 'wheel_member_count_invalid')
        _require(sum(info.file_size for info in entries) <= MAX_EXPANDED_BYTES, 'wheel_expansion_limit')
        for info in entries:
            # ZipInfo may normalize Windows separators or truncate a NUL.
            # Validate the original central-directory name before accepting
            # the normalized lookup name, even with a self-consistent RECORD.
            name = info.orig_filename
            _safe_name(name)
            _require(name == info.filename, 'unsafe_wheel_path')
            _require(not name.lower().endswith(('.pfx', '.p12', '.pvk', '.snk', '.ttf', '.otf', '.woff', '.woff2')), 'private_key_or_font_in_wheel')
            _require(name.casefold() not in seen, 'duplicate_wheel_member')
            seen.add(name.casefold())
            mode = stat.S_IFMT(info.external_attr >> 16)
            _require(mode in {0, stat.S_IFREG} and not info.is_dir(), 'nonregular_wheel_member')
            _require(not info.flag_bits & 1, 'encrypted_wheel_member_refused')
            _require(info.file_size <= MAX_MEMBER_BYTES, 'wheel_member_size_limit')
            members[name] = archive.read(info)
    dist_roots = {name.split('/')[0] for name in members if name.split('/')[0].endswith('.dist-info')}
    _require(len(dist_roots) == 1, 'wheel_distribution_identity_ambiguous')
    dist_root = dist_roots.pop()
    _require(all(name.split('/')[0] in {*PACKAGES, dist_root} for name in members), 'unexpected_wheel_root')
    metadata = BytesParser().parsebytes(members[dist_root + '/METADATA'])
    _require(len(metadata.get_all('Name', [])) == len(metadata.get_all('Version', [])) == 1,
             'wheel_metadata_identity_invalid')
    normalized = re.sub(r'[-_.]+', '-', metadata['Name']).lower()
    _require(normalized == 'nh-family-law-llm', 'wheel_project_identity_mismatch')
    _require(dist_root == 'nh_family_law_llm-' + metadata['Version'] + '.dist-info', 'wheel_dist_info_mismatch')
    wheel_meta = BytesParser().parsebytes(members[dist_root + '/WHEEL'])
    _require(wheel_meta.get('Root-Is-Purelib', '').lower() == 'true', 'purelib_wheel_required')
    record_name = dist_root + '/RECORD'
    rows = list(csv.reader(io.StringIO(members[record_name].decode('utf-8'), newline='')))
    _require(all(len(row) == 3 for row in rows), 'wheel_record_invalid')
    records = {row[0]: row[1:] for row in rows}
    _require(len(records) == len(rows) and set(records) == set(members), 'wheel_record_inventory_mismatch')
    for name, data in members.items():
        digest, size = records[name]
        if name == record_name:
            _require(digest == size == '', 'wheel_record_self_hash_invalid')
            continue
        expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
        _require(digest == expected and size == str(len(data)), 'wheel_record_digest_mismatch')
    return members, dist_root, metadata, wheel_hash


def _source_members(root: Path) -> dict[str, Path]:
    expected: dict[str, Path] = {}
    for base, name in ((root, 'app'), (root, 'legal'), (root / 'src', 'nh_family_law_llm')):
        _require((base / name / '__init__.py').is_file(), 'source_package_missing')
        for path in (base / name).rglob('*.py'):
            expected[path.relative_to(base).as_posix()] = path
    config = tomllib.loads(_regular_bytes(root / 'pyproject.toml', MAX_MEMBER_BYTES).decode('utf-8'))
    for package, patterns in config['tool']['setuptools']['package-data'].items():
        _require(package == 'nh_family_law_llm', 'package_data_contract_unsupported')
        for pattern in patterns:
            _require(not PurePosixPath(pattern).is_absolute() and '..' not in pattern.split('/'),
                     'source_package_data_path_unsafe')
            for path in (root / 'src' / package).glob(pattern):
                if path.is_file():
                    expected[path.relative_to(root / 'src').as_posix()] = path
    return expected


def audit_wheel(wheel: str | Path, *, source_root: str | Path | None = None,
                installed: bool = False, expected_sha256: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        'schema': 'nhfl.wheel_integrity.v1', 'status': 'fail', 'wheel_sha256': None,
        'scope': 'installed_wheel_bytes' if installed else 'source_to_wheel_bytes',
        'package_file_count': 0, 'checked_file_count': 0, 'blockers': [],
        'production_ready': False, 'legal_review_verified': False, 'msix_qualified': False,
    }
    try:
        _require(installed != (source_root is not None), 'exactly_one_integrity_scope_required')
        members, dist_root, metadata, digest = _read_wheel(Path(wheel))
        result.update(wheel_sha256=digest, package_version=metadata['Version'],
                      member_count=len(members))
        if expected_sha256 is not None:
            _require(bool(re.fullmatch(r'[a-f0-9]{64}', expected_sha256)) and digest == expected_sha256,
                     'wheel_sha256_mismatch')
        payload = {name: data for name, data in members.items() if name.split('/')[0] in PACKAGES}
        result['package_file_count'] = len(payload)
        if source_root is not None:
            root = Path(source_root).absolute()
            expected = _source_members(root)
            _require(set(payload) == set(expected), 'wheel_source_inventory_mismatch')
            project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
            _require(metadata['Version'] == project['version'], 'wheel_source_version_mismatch')
            entries = configparser.ConfigParser(interpolation=None)
            entries.read_string(members[dist_root + '/entry_points.txt'].decode('utf-8'))
            _require(dict(entries['console_scripts']) == project['scripts'], 'wheel_entry_points_mismatch')
            for name, data in payload.items():
                _require(_regular_bytes(expected[name], MAX_MEMBER_BYTES) == data, 'wheel_source_bytes_mismatch')
                result['checked_file_count'] += 1
        else:
            purelib = Path(sysconfig.get_path('purelib')).absolute()
            distribution = importlib.metadata.distribution('nh-family-law-llm')
            _require(Path(distribution.locate_file('')).resolve() == purelib.resolve(), 'installed_distribution_outside_interpreter')
            _require(distribution.version == metadata['Version'], 'installed_version_mismatch')
            for package in PACKAGES:
                spec = importlib.util.find_spec(package)
                _require(spec is not None and spec.origin is not None and
                         Path(spec.origin).absolute() == purelib / package / '__init__.py',
                         'installed_package_origin_mismatch')
            # Pip rewrites RECORD and adds installer metadata/entry-point launchers.
            # Original application/resource bytes and wheel metadata must not change.
            for name, data in members.items():
                if name == dist_root + '/RECORD':
                    continue
                target = purelib.joinpath(*PurePosixPath(name).parts)
                _require(_regular_bytes(target, MAX_MEMBER_BYTES) == data, 'installed_wheel_bytes_mismatch')
                result['checked_file_count'] += 1
            for package in PACKAGES:
                for path in (purelib / package).rglob('*.py'):
                    _require(path.relative_to(purelib).as_posix() in payload, 'unexpected_installed_python_module')
            result['interpreter_isolated'] = bool(sys.flags.isolated)
            _require(bool(sys.flags.isolated), 'isolated_interpreter_required')
        result['status'] = 'pass'
    except WheelIntegrityError as exc:
        result['blockers'].append(str(exc))
    except (OSError, ValueError, KeyError, ImportError, zipfile.BadZipFile, RuntimeError,
            configparser.Error, csv.Error) as exc:
        result['blockers'].append('wheel_integrity_unavailable:' + type(exc).__name__)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', required=True, type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--installed', action='store_true')
    args = parser.parse_args()
    report = audit_wheel(args.wheel, source_root=args.source_root, installed=args.installed,
                         expected_sha256=args.expected_sha256)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
