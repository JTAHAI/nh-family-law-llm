"""Synthetic DOCX trust-boundary checks; not visual, Word or legal qualification."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from legal.documents import docx_engine as engine
from legal.documents.workspace import DocumentWorkspaceError


@pytest.fixture
def source(tmp_path):
    sources, outputs = tmp_path / "sources", tmp_path / "exports"
    sources.mkdir()
    outputs.mkdir()
    doc = Document()
    doc.add_paragraph("Fictional original paragraph.")
    stream = io.BytesIO()
    doc.save(stream)
    path = sources / "original.docx"
    path.write_bytes(stream.getvalue())
    return path, sources, outputs


@pytest.fixture
def backend(monkeypatch):
    state = {"opens": [], "hook": None, "error": None}

    class FakeDocument:
        @classmethod
        def open(cls, path, **kwargs):
            state["opens"].append((Path(path), Path(kwargs["workspace_dir"])))
            if state["error"] is not None:
                raise state["error"]
            if state["hook"]:
                state["hook"](Path(path), Path(kwargs["workspace_dir"]))
            return cls()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def list_paragraphs_structured(self, **kwargs):
            return [SimpleNamespace(index=1, ref="P1#abcd", text="Fictional original paragraph.")]

        def paragraph_count(self):
            return 1

        def replace(self, *args, **kwargs):
            return "P1#abcd"

        def save(self):
            return None

    monkeypatch.setitem(sys.modules, "docx_editor", SimpleNamespace(Document=FakeDocument))
    return state


def listing(source):
    path, root, _ = source
    return engine.list_docx_paragraphs(source_path=path, allowed_source_root=root)


def editing(source, **kwargs):
    path, root, outputs = source
    return engine.tracked_edit_copy(source_path=path, allowed_source_root=root,
        output_path=outputs / "new.docx", allowed_output_root=outputs,
        operations=[{"action": "replace", "paragraph": "P1#abcd", "find": "original",
                     "replace_with": "revised", "occurrence": 0}], **kwargs)


def rewrite_member(path, name, data=b"fictional", *, wire_name=None):
    with zipfile.ZipFile(path) as archive:
        rows = {item.filename: archive.read(item) for item in archive.infolist()}
    rows[name] = data
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, raw in rows.items():
            info = zipfile.ZipInfo()
            info.filename = info.orig_filename = wire_name if key == name and wire_name is not None else key
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)


@pytest.mark.parametrize("value", [True, False, 0.5, 1.9, "0", "1", None, float("inf")])
def test_occurrence_is_an_exact_integer_not_coerced(value):
    with pytest.raises(DocumentWorkspaceError) as caught:
        engine._normalize_operations([{"action": "replace", "paragraph": "P1#abcd",
                                      "find": "old", "replace_with": "new", "occurrence": value}])
    assert caught.value.code == "invalid_docx_occurrence"


@pytest.mark.parametrize("field,value", [("find", 123), ("replace_with", False),
    ("find", None), ("replace_with", "new\x00text"), ("find", "old\x01text")])
def test_edit_text_is_not_silently_changed(field, value):
    operation = {"action": "replace", "paragraph": "P1#abcd", "find": "old", "replace_with": "new"}
    operation[field] = value
    with pytest.raises(DocumentWorkspaceError):
        engine._normalize_operations([operation])


def test_unknown_selector_typo_is_rejected():
    with pytest.raises(DocumentWorkspaceError):
        engine._normalize_operations([{"action": "replace", "paragraph": "P1#abcd",
            "find": "old", "replace_with": "new", "occurence": 1}])


def test_operation_limit_bounds_iteration_not_just_finished_list():
    consumed = []

    def rows():
        for number in range(engine.MAX_EDIT_OPERATIONS + 2):
            consumed.append(number)
            if number > engine.MAX_EDIT_OPERATIONS:
                pytest.fail("Unbounded operation iterable consumed")
            yield {"action": "replace", "paragraph": "P1#abcd", "find": "old", "replace_with": "new"}

    with pytest.raises(DocumentWorkspaceError) as caught:
        engine._normalize_operations(rows())
    assert caught.value.code == "too_many_docx_edits"
    assert len(consumed) == engine.MAX_EDIT_OPERATIONS + 1


@pytest.mark.parametrize("operation", [
    {"action": "replace", "paragraph": "P1#abcd", "replace_with": "new"},
    {"action": "delete", "paragraph": "P1#abcd"},
    {"action": "add_comment", "comment": "review"},
    {"action": "add_comment", "find": "old", "comment": "review", "paragraph": "P1#abcd"},
])
def test_missing_or_unsupported_selectors_fail_before_open(source, backend, operation):
    path, root, outputs = source
    with pytest.raises(DocumentWorkspaceError):
        engine.tracked_edit_copy(source_path=path, allowed_source_root=root,
            output_path=outputs / "new.docx", allowed_output_root=outputs, operations=[operation])
    assert backend["opens"] == []
    assert list(outputs.iterdir()) == []


@pytest.mark.parametrize("runner", [listing, editing])
def test_each_engine_operation_uses_a_private_copy_and_cleans_it(source, backend, runner):
    original, _, outputs = source
    before = original.read_bytes()
    old_scratch = original.parent / ".docx-editor-workspaces"
    old_scratch.mkdir()
    sentinel = old_scratch / "owner-work.txt"
    sentinel.write_text("preserve unrelated existing work", encoding="utf-8")
    result = runner(source)
    opened, workspace = backend["opens"][0]
    assert opened != original
    assert not opened.exists() and not workspace.exists()
    assert original.read_bytes() == before
    assert sentinel.read_text(encoding="utf-8") == "preserve unrelated existing work"
    assert not list(original.parent.glob(".nhfl-docx-*"))
    assert not list(outputs.glob(".nhfl-docx-*"))
    if runner is editing:
        assert result["filing_ready"] is False and result["review_required"] is True


@pytest.mark.parametrize("runner", [listing, editing])
def test_backend_failure_is_sanitized_and_cleans_owned_scratch(source, backend, runner):
    backend["error"] = ValueError("fictional private-client text at C:/confidential/matter")
    with pytest.raises(DocumentWorkspaceError) as caught:
        runner(source)
    assert caught.value.code == "docx_processing_failed"
    assert "private-client" not in str(caught.value)
    opened, workspace = backend["opens"][0]
    assert not opened.exists() and not workspace.exists()
    assert not (source[2] / "new.docx").exists()


@pytest.mark.parametrize("runner", [listing, editing])
def test_legacy_scratch_link_is_not_followed_or_deleted(source, backend, runner, tmp_path):
    parent = source[0].parent if runner is listing else source[2]
    target = tmp_path / "owner-existing-work"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    link = parent / ".docx-editor-workspaces"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    runner(source)
    _, workspace = backend["opens"][0]
    assert workspace != link and not workspace.is_relative_to(target)
    assert link.is_symlink() and sentinel.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("kind", ["source_ancestor", "output_ancestor", "output_dangling"])
def test_lexical_links_are_rejected_before_engine_open(source, backend, tmp_path, kind):
    path, root, outputs = source
    link = tmp_path / "linked"
    try:
        if kind == "source_ancestor":
            link.symlink_to(root, target_is_directory=True)
            path, root = link / path.name, link
        elif kind == "output_ancestor":
            link.symlink_to(outputs, target_is_directory=True)
            outputs = link
        else:
            (outputs / "new.docx").symlink_to(tmp_path / "missing-target")
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(DocumentWorkspaceError):
        editing((path, root, outputs))
    assert backend["opens"] == []


@pytest.mark.parametrize("runner", [listing, editing])
def test_zip_name_aliases_fail_before_backend(source, backend, runner):
    path = source[0]
    rewrite_member(path, "word/unsafe.xml", b"<x/>", wire_name="word/unsafe.xml\x00hidden")
    with pytest.raises(DocumentWorkspaceError) as caught:
        runner(source)
    assert caught.value.code == "unsafe_docx_archive"
    assert backend["opens"] == []


@pytest.mark.parametrize("name", ["../escape", r"word\alias.xml", "word/CON", "word/x:stream",
                                "word/a./x.xml", "word/./x.xml", "word//x.xml"])
def test_unsafe_zip_members_fail_before_backend(source, backend, name):
    rewrite_member(source[0], name)
    with pytest.raises(DocumentWorkspaceError) as caught:
        listing(source)
    assert caught.value.code == "unsafe_docx_archive"
    assert backend["opens"] == []


@pytest.mark.parametrize("kind", ["duplicate", "case_alias", "missing_document", "invalid_xml", "xml_entity", "not_zip"])
def test_ambiguous_or_malformed_docx_is_not_opened(source, backend, kind):
    path = source[0]
    if kind == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate"):
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("word/document.xml", b"<x/>")
    elif kind == "case_alias":
        rewrite_member(path, "word/Document.xml", b"<x/>")
    elif kind == "missing_document":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/missing.xml", b"<x/>")
    elif kind in {"invalid_xml", "xml_entity"}:
        data = b"<unclosed>" if kind == "invalid_xml" else b'<!DOCTYPE x [<!ENTITY y "fictional">]><x>&y;</x>'
        rewrite_member(path, "word/document.xml", data)
    else:
        path.write_bytes(b"not a zip archive")
    with pytest.raises(DocumentWorkspaceError) as caught:
        listing(source)
    assert caught.value.code == "unsafe_docx_archive"
    assert backend["opens"] == []


def test_archive_expansion_limit_blocks_before_backend(source, backend, monkeypatch):
    monkeypatch.setattr(engine, "MAX_DOCX_EXPANDED_BYTES", 1, raising=False)
    with pytest.raises(DocumentWorkspaceError) as caught:
        listing(source)
    assert caught.value.code == "docx_archive_too_large"
    assert backend["opens"] == []


def test_existing_export_is_never_replaced(source, backend):
    target = source[2] / "new.docx"
    target.write_bytes(b"owner existing output")
    with pytest.raises(DocumentWorkspaceError):
        editing(source)
    assert target.read_bytes() == b"owner existing output"
    assert backend["opens"] == []


def test_export_created_during_processing_is_never_overwritten(source, backend):
    target = source[2] / "new.docx"
    backend["hook"] = lambda *_: target.write_bytes(b"owner concurrent output")
    with pytest.raises(DocumentWorkspaceError) as caught:
        editing(source)
    assert caught.value.code == "docx_output_conflict"
    assert target.read_bytes() == b"owner concurrent output"


def test_source_changed_during_processing_blocks_publication_without_undo(source, backend):
    backend["hook"] = lambda *_: source[0].write_bytes(b"owner independently updated source")
    with pytest.raises(DocumentWorkspaceError) as caught:
        editing(source)
    assert caught.value.code == "docx_source_changed"
    assert source[0].read_bytes() == b"owner independently updated source"
    assert not (source[2] / "new.docx").exists()


def test_new_text_export_refuses_existing_owner_file(source):
    target = source[2] / "new.docx"
    target.write_bytes(b"owner existing output")
    with pytest.raises(DocumentWorkspaceError) as caught:
        engine.create_docx_from_text(title="Fictional", content="Fictional body",
            output_path=target, allowed_output_root=source[2])
    assert caught.value.code == "docx_output_conflict"
    assert target.read_bytes() == b"owner existing output"


@pytest.mark.parametrize("action,fields", [
    ("replace", {"find": "original", "replace_with": "revised"}),
    ("delete", {"text": "original"}),
    ("insert_after", {"find": "original", "text": " added"}),
    ("rewrite_paragraph", {"text": "Fictional replacement paragraph."}),
    ("add_comment", {"find": "original", "comment": "Fictional review comment."}),
])
def test_real_backend_actions_preserve_source_and_clean_scratch(source, action, fields):
    import hashlib
    from defusedxml import ElementTree
    # This test intentionally requires the declared engine. A stub or an
    # unavailable engine cannot qualify the real tracked-editing path.
    import docx_editor
    assert getattr(docx_editor, "__file__", None)
    path, root, outputs = source
    original = path.read_bytes()
    paragraph = listing(source)["paragraphs"][0]["ref"]
    operation = {"action": action, **fields}
    if action != "add_comment":
        operation["paragraph"] = paragraph
    result = engine.tracked_edit_copy(source_path=path, allowed_source_root=root,
        output_path=outputs / "real.docx", allowed_output_root=outputs,
        operations=[operation], author="Fictional reviewer")
    assert path.read_bytes() == original
    assert result["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert result["sha256"] == hashlib.sha256(result["path"].read_bytes()).hexdigest()
    assert result["tracked_changes"] is True and result["filing_ready"] is False
    assert result["review_required"] is True
    with zipfile.ZipFile(result["path"]) as archive:
        xml = ElementTree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        if action == "add_comment":
            assert b"Fictional review comment" in archive.read("word/comments.xml")
        else:
            revisions = xml.findall(".//w:ins", ns) + xml.findall(".//w:del", ns)
            assert revisions, "The real engine must emit tracked revisions, not just changed plain text"
    assert not list(root.glob(".nhfl-docx-*")) and not list(outputs.glob(".nhfl-docx-*"))


def test_real_backend_stale_reference_is_sanitized_without_export(source):
    path, root, outputs = source
    original = path.read_bytes()
    with pytest.raises(DocumentWorkspaceError) as caught:
        engine.tracked_edit_copy(source_path=path, allowed_source_root=root,
            output_path=outputs / "stale.docx", allowed_output_root=outputs,
            operations=[{"action": "replace", "paragraph": "P1#00000000",
                         "find": "original", "replace_with": "wrong"}])
    assert caught.value.code == "docx_processing_failed"
    assert "Fictional original" not in str(caught.value)
    assert path.read_bytes() == original and not list(outputs.iterdir())


@pytest.mark.parametrize("limit", ["MAX_DOCX_MEMBERS", "MAX_DOCX_MEMBER_BYTES"])
def test_per_part_and_entry_count_limits_block_before_backend(source, backend, monkeypatch, limit):
    monkeypatch.setattr(engine, limit, 1)
    with pytest.raises(DocumentWorkspaceError) as caught:
        listing(source)
    assert caught.value.code == "docx_archive_too_large"
    assert backend["opens"] == []


def test_invalid_processed_copy_cannot_be_published(source, backend):
    before = source[0].read_bytes()
    backend["hook"] = lambda path, _: path.write_bytes(b"fictional invalid backend output")
    with pytest.raises(DocumentWorkspaceError):
        editing(source)
    assert source[0].read_bytes() == before
    assert not list(source[2].iterdir())


def test_unavailable_atomic_publication_has_no_overwrite_fallback(source, backend, monkeypatch):
    def refused(*args, **kwargs):
        raise OSError("fictional filesystem without atomic hardlinks")
    monkeypatch.setattr(engine.os, "link", refused)
    with pytest.raises(DocumentWorkspaceError) as caught:
        editing(source)
    assert caught.value.code == "docx_output_unavailable"
    assert not list(source[2].iterdir())


def test_qualification_workflow_uses_owned_state_and_exact_source_snapshot():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".github/workflows/nh-pass12-docx-qualification.yml").read_text(encoding="utf-8")
    assert "'dist' / 'pass12-ci'" in text
    assert "'clone', '--no-hardlinks', '--no-checkout'" in text
    assert "tree != original_tree" in text
    assert "cwd=work / 'source'" in text and "work / 'full-pytest'" in text
    assert "tests/test_pass71_tracked_docx_workflow_acceptance.py" in text
    assert "'pytest', 'tests'" in text
    assert "continue-on-error" not in text
    assert "run-public-source-preflight.py --index --require-ready" in text


def test_whole_paragraph_rewrite_does_not_silently_ignore_occurrence():
    operation = {"action": "rewrite_paragraph", "paragraph": "P1#abcd", "text": "Fictional replacement"}
    assert engine._normalize_operations([{**operation, "occurrence": 0}])[0]["occurrence"] == 0
    with pytest.raises(DocumentWorkspaceError) as caught:
        engine._normalize_operations([{**operation, "occurrence": 1}])
    assert caught.value.code == "invalid_docx_occurrence"
