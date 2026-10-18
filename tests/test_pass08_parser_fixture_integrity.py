"""Synthetic corpus bytes must survive checkout; no fixture is legal authority."""
from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal.connectors import parser_regression as corpus

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'data/fixtures/parser_regression'


def git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
                            capture_output=True, timeout=30, check=True)
    return result.stdout


@pytest.mark.parametrize('autocrlf,eol', [('true', 'crlf'), ('false', 'crlf'),
                                        ('false', 'lf'), ('input', 'lf')])
def test_exact_fixture_bytes_survive_git_checkout(tmp_path, autocrlf, eol):
    checkout = tmp_path / 'fictional-checkout'
    checkout.mkdir()
    git(checkout, 'init', '-q')
    git(checkout, 'config', 'core.autocrlf', autocrlf)
    git(checkout, 'config', 'core.eol', eol)
    files = {'.gitattributes': (ROOT / '.gitattributes').read_bytes()}
    files.update({path.relative_to(ROOT).as_posix(): path.read_bytes()
                  for path in FIXTURES.iterdir() if path.is_file()})
    # Feed canonical repository blobs, not add-filtered worktree bytes.
    rows = []
    for name, raw in files.items():
        oid = git(checkout, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
        rows.append(f'100644 {oid}\t{name}\n')
    git(checkout, 'update-index', '--index-info', data=''.join(rows).encode())
    git(checkout, 'checkout-index', '--all')
    for name, raw in files.items():
        if name != '.gitattributes':
            assert (checkout / name).read_bytes() == raw, name
    report = corpus.ParserRegressionCorpus(checkout / 'data/fixtures/parser_regression').run()
    assert report['status'] == 'passed' and report['passed_count'] == 6, report
    assert report['network_used'] is report['can_support_legal_claim'] is False


@pytest.fixture
def fixture_root(tmp_path):
    root = tmp_path / 'fictional-corpus'
    shutil.copytree(FIXTURES, root)
    return root


def read_manifest(root):
    return json.loads((root / 'manifest.json').read_text(encoding='utf-8'))


def write_manifest(root, value):
    (root / 'manifest.json').write_text(json.dumps(value), encoding='utf-8')


def refuse_parser(monkeypatch):
    monkeypatch.setattr(corpus.ParserRegressionCorpus, '_run_parser',
                        lambda *a: pytest.fail('unverified bytes reached parser'))


def link(source, target, *, directory=False):
    try:
        source.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip('symlink creation unavailable')


def test_changed_newlines_are_still_tampering_not_normalized(fixture_root, monkeypatch):
    path = fixture_root / 'rules_footnote_v1.txt'
    path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
    refuse_parser(monkeypatch)
    result = corpus.ParserRegressionCorpus(fixture_root).run_fixture('rules-footnote-v1')
    assert result['status'] == 'blocked'
    assert result['blockers'] == ['fixture_content_hash_mismatch']
    assert result['fixture_sha256'] is None and result['extracted_count'] == 0


@pytest.mark.parametrize('kind', ['file', 'ancestor'])
def test_same_hash_link_within_corpus_is_not_accepted(fixture_root, monkeypatch, kind):
    manifest = read_manifest(fixture_root)
    item = manifest['fixtures'][0]
    if kind == 'file':
        linked = fixture_root / 'alias.html'
        link(linked, fixture_root / item['content_file'])
        item['content_file'] = linked.name
    else:
        linked = fixture_root / 'alias'
        link(linked, fixture_root, directory=True)
        item['content_file'] = 'alias/' + item['content_file']
    write_manifest(fixture_root, manifest)
    refuse_parser(monkeypatch)
    result = corpus.ParserRegressionCorpus(fixture_root).run_fixture(item['fixture_id'])
    assert result['status'] == 'blocked'
    assert result['fixture_sha256'] is None
    assert result['blockers'] == ['parser_regression_linked_path_refused']


@pytest.mark.parametrize('kind', ['root', 'ancestor'])
def test_linked_corpus_root_cannot_hide_in_resolve(fixture_root, tmp_path, monkeypatch, kind):
    alias = tmp_path / 'linked'
    if kind == 'root':
        link(alias, fixture_root, directory=True)
        selected = alias
    else:
        link(alias, tmp_path, directory=True)
        selected = alias / fixture_root.name
    refuse_parser(monkeypatch)
    with pytest.raises(ValueError, match='parser_regression_linked_path_refused'):
        corpus.ParserRegressionCorpus(selected).run()


def test_reparse_ancestor_is_refused_without_parsing(fixture_root, monkeypatch):
    original = Path.lstat
    def metadata(path, *args, **kwargs):
        if path == fixture_root:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', metadata)
    refuse_parser(monkeypatch)
    with pytest.raises(ValueError, match='parser_regression_linked_path_refused'):
        corpus.ParserRegressionCorpus(fixture_root).run()


@pytest.mark.parametrize('name', ['../fictional-corpus/rsa_chapter_index_v1.html',
                                  './rsa_chapter_index_v1.html',
                                  'sub/../rsa_chapter_index_v1.html'])
def test_path_alias_cannot_bypass_manifest_identity(fixture_root, monkeypatch, name):
    manifest = read_manifest(fixture_root)
    manifest['fixtures'][0]['content_file'] = name
    write_manifest(fixture_root, manifest)
    refuse_parser(monkeypatch)
    result = corpus.ParserRegressionCorpus(fixture_root).run_fixture(manifest['fixtures'][0]['fixture_id'])
    assert result['status'] == 'blocked'
    assert result['blockers'] == ['parser_regression_fixture_path_invalid']


@pytest.mark.parametrize('problem', ['empty', 'non_object', 'duplicate_id', 'duplicate_file',
                                    'negative_minimum', 'boolean_minimum', 'string_minimum',
                                    'unknown_parser', 'unknown_status', 'missing_hash'])
def test_invalid_manifest_cannot_return_success(fixture_root, monkeypatch, problem):
    manifest = read_manifest(fixture_root)
    if problem == 'empty': manifest['fixtures'] = []
    elif problem == 'non_object': manifest['fixtures'] = ['invalid']
    elif problem == 'duplicate_id': manifest['fixtures'][1]['fixture_id'] = manifest['fixtures'][0]['fixture_id']
    elif problem == 'duplicate_file': manifest['fixtures'][1]['content_file'] = manifest['fixtures'][0]['content_file']
    elif problem == 'negative_minimum': manifest['fixtures'][0]['expected']['minimum_extracted_count'] = -1
    elif problem == 'boolean_minimum': manifest['fixtures'][0]['expected']['minimum_extracted_count'] = True
    elif problem == 'string_minimum': manifest['fixtures'][0]['expected']['minimum_extracted_count'] = '2'
    elif problem == 'unknown_parser': manifest['fixtures'][0]['parser_name'] = 'unknown'
    elif problem == 'unknown_status': manifest['fixtures'][0]['expected']['status'] = 'green'
    else: del manifest['fixtures'][0]['content_sha256']
    write_manifest(fixture_root, manifest)
    refuse_parser(monkeypatch)
    with pytest.raises(ValueError, match='parser_regression_manifest_invalid'):
        corpus.ParserRegressionCorpus(fixture_root).run()


def test_duplicate_json_keys_are_not_interpreted_as_one_manifest(fixture_root, monkeypatch):
    path = fixture_root / 'manifest.json'
    raw = path.read_text(encoding='utf-8')
    path.write_text(raw.replace('"fixtures":', '"fixtures": [], "fixtures":', 1), encoding='utf-8')
    refuse_parser(monkeypatch)
    with pytest.raises(ValueError, match='parser_regression_manifest_invalid'):
        corpus.ParserRegressionCorpus(fixture_root).run()


def test_fixture_size_limit_blocks_before_read_and_parse(fixture_root, monkeypatch):
    monkeypatch.setattr(corpus, 'MAX_FIXTURE_BYTES', 1, raising=False)
    refuse_parser(monkeypatch)
    result = corpus.ParserRegressionCorpus(fixture_root).run_fixture('forms-table-v1')
    assert result['status'] == 'blocked'
    assert result['blockers'] == ['fixture_file_unavailable_or_oversized']
    assert result['fixture_sha256'] is None
