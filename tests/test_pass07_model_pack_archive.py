"""Original ZIP names must be safe before any signed pack is inspected.

All archives contain tiny synthetic bytes. No actual model is downloaded,
loaded, or admitted by these regression tests.
"""
from __future__ import annotations

import zipfile

import pytest

from app.services.model_pack_service import METADATA, ModelPackError, _bounded_zip
from test_fast_interchange_model_packs import pack_store, upload  # noqa: F401
from test_fast_interchange_artifact_registry import admitted  # noqa: F401


def write_raw_archive(path, entries, *, wire_names=None):
    # Assign after construction: ZipInfo otherwise changes the deliberately
    # hostile negative-fixture name on Windows or truncates NUL characters.
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in entries.items():
            info = zipfile.ZipInfo()
            info.filename = info.orig_filename = (wire_names or {}).get(name, name)
            archive.writestr(info, raw)
    return path


def test_canonical_uncompressed_archive_still_passes_bounded_preflight(tmp_path):
    entries = {**{name: b'{}' for name in METADATA}, 'base/model.safetensors': b'fictional'}
    path = write_raw_archive(tmp_path / 'fictional.zip', entries)
    with _bounded_zip(path) as archive:
        assert set(archive.namelist()) == set(entries)
        assert archive.read('base/model.safetensors') == b'fictional'


@pytest.mark.parametrize('original', [r'base\model.safetensors', 'base/model.safetensors\x00hidden'])
def test_normalized_alias_is_rejected_before_metadata_or_payload_read(tmp_path, monkeypatch, original):
    canonical = 'base/model.safetensors'
    entries = {**{name: b'{}' for name in METADATA}, canonical: b'fictional'}
    path = write_raw_archive(tmp_path / 'fictional.zip', entries, wire_names={canonical: original})
    base = zipfile.ZipInfo

    class WindowsNormalizedInfo(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.filename = self.filename.replace('\\', '/')

    monkeypatch.setattr(zipfile, 'ZipInfo', WindowsNormalizedInfo)
    with zipfile.ZipFile(path) as archive:
        info = next(row for row in archive.infolist() if row.orig_filename == original)
        assert info.filename == canonical
        assert archive.read(info) == entries[canonical]
    with pytest.raises(ModelPackError, match='model_pack_archive_path_invalid'):
        with _bounded_zip(path):
            pass


def test_signed_pack_with_hidden_nul_filename_cannot_reach_activation(pack_store, tmp_path):  # noqa: F811
    pack = pack_store
    canonical = 'base/model.safetensors'
    with zipfile.ZipFile(pack['path']) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    path = write_raw_archive(tmp_path / 'ambiguous.model-pack.zip', entries,
                             wire_names={canonical: canonical + '\x00hidden'})
    row = upload(pack, path)
    with pytest.raises(ModelPackError, match='model_pack_archive_path_invalid'):
        pack['store'].inspect(row['job_id'], scope=pack['scope'], audit=pack['audit'])
    assert pack['store'].status(row['job_id'], scope=pack['scope'])['status'] == 'failed'
    assert not (pack['store'].root / 'active.json').exists()
    assert not any(event[0] == 'model_pack_verified' for event in pack['events'])
    assert pack['path'].exists() and path.exists()
