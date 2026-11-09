"""Synthetic download faults; no live network or real model is used."""
import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def downloader(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('pinned_input_test', ROOT / 'scripts/fetch_pinned_build_input.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    return module, tmp_path / 'dist' / 'input.bin'


def response(raw=b'synthetic verified native input', url='https://example.invalid/input'):
    value = BytesIO(raw)
    value.geturl = lambda: url
    return value


DIGEST = hashlib.sha256(b'synthetic verified native input').hexdigest()
URL = 'https://example.invalid/input'


def test_timeout_retry_publishes_only_complete_verified_input(downloader, monkeypatch):
    module, destination = downloader
    calls = []
    def open_request(*args, **kwargs):
        calls.append(1)
        assert not destination.exists()
        if len(calls) == 1:
            raise HTTPError(URL, 504, 'synthetic', {}, None)
        return response()
    monkeypatch.setattr(module, 'build_opener', lambda *args: SimpleNamespace(open=open_request))
    module.acquire(URL, destination, DIGEST)
    assert len(calls) == 2 and hashlib.sha256(destination.read_bytes()).hexdigest() == DIGEST
    assert list(destination.parent.glob('.pinned-input-*')) == []


@pytest.mark.parametrize('code,attempts', [(504,3),(429,3),(403,1),(404,1)])
def test_retry_budget_and_http_errors_never_publish_partial_file(downloader, monkeypatch, code, attempts):
    module, destination = downloader
    calls=[]
    def fail(*args, **kwargs):
        calls.append(1)
        raise HTTPError(URL, code, 'synthetic', {}, None)
    monkeypatch.setattr(module, 'build_opener', lambda *args: SimpleNamespace(open=fail))
    with pytest.raises(module.BuildInputError, match='download_unavailable'):
        module.acquire(URL, destination, DIGEST)
    assert len(calls) == attempts and not destination.exists()
    assert not list(destination.parent.glob('.pinned-input-*'))


@pytest.mark.parametrize('raw,url,maximum', [(b'wrong',URL,100),(b'x'*101,URL,100),(b'ok','http://example.invalid',100)])
def test_bad_bytes_oversize_and_downgrade_are_blocked(downloader, monkeypatch, raw,url,maximum):
    module,destination=downloader
    monkeypatch.setattr(module, 'MAX_BYTES', maximum)
    monkeypatch.setattr(module, 'build_opener', lambda *args: SimpleNamespace(open=lambda *a,**k: response(raw,url)))
    with pytest.raises(module.BuildInputError):
        module.acquire(URL,destination,DIGEST)
    assert not destination.exists() and not list(destination.parent.glob('.pinned-input-*'))


@pytest.mark.parametrize('raw,accepted', [(b'synthetic verified native input',True),(b'owner bytes',False)])
def test_existing_cache_is_read_only_and_requires_digest(downloader,monkeypatch,raw,accepted):
    module,destination=downloader
    destination.parent.mkdir();destination.write_bytes(raw)
    monkeypatch.setattr(module,'build_opener',lambda *a: pytest.fail('Existing cache must not download'))
    if accepted:
        module.acquire(URL,destination,DIGEST)
    else:
        with pytest.raises(module.BuildInputError, match='existing_build_input_digest_mismatch'):
            module.acquire(URL,destination,DIGEST)
    assert destination.read_bytes()==raw


def test_concurrent_destination_is_never_overwritten(downloader,monkeypatch):
    module,destination=downloader
    def fetch(*a,**k):
        destination.write_bytes(b'owner race')
        return response()
    monkeypatch.setattr(module,'build_opener',lambda *a:SimpleNamespace(open=fetch))
    with pytest.raises(module.BuildInputError,match='concurrent_build_input_conflict'):
        module.acquire(URL,destination,DIGEST)
    assert destination.read_bytes()==b'owner race'


def test_linked_destination_refused_before_network(downloader,monkeypatch):
    module,destination=downloader
    destination.parent.mkdir();destination.symlink_to(destination.parent/'missing')
    monkeypatch.setattr(module,'build_opener',lambda *a:pytest.fail('No network allowed'))
    with pytest.raises(module.BuildInputError,match='linked_build_input_refused'):
        module.acquire(URL,destination,DIGEST)


def test_outside_dist_refused(downloader):
    module,destination=downloader
    with pytest.raises(module.BuildInputError,match='outside_owned_dist'):
        module.acquire(URL,destination.parent.parent/'not-dist.bin',DIGEST)
