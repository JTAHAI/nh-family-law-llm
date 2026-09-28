"""Restored portable bundle integrity tests with exclusively fictional content."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.knowledge_bundle import (
    KnowledgeBundleError, KnowledgeConcept, build_bundle, concept_path,
    parse_concept_id, read_concept, validate_bundle,
)
from legal.knowledge_bundle.frontmatter import split_document


def concept(identifier="fictional/example"):
    return KnowledgeConcept(identifier, "synthetic_note", "Fictional α note", "Fictional body 🧪",
                            tags=("synthetic",), citations=("fictional-source",),
                            metadata={"review_required": True})


def test_bundle_roundtrip_preserves_metadata_and_manifest_hash(tmp_path):
    root = tmp_path / "bundle"
    original = concept()
    report = build_bundle(root, [original])
    assert report.status == "pass" and report.concept_count == 1
    assert read_concept(root, concept_path(root, original.concept_id)) == original
    assert validate_bundle(root) == report
    assert len(report.manifest_sha256) == 64
    assert build_bundle(root, [original]) == report


def test_tampered_concept_is_not_accepted(tmp_path):
    root = tmp_path / "bundle"
    build_bundle(root, [concept()])
    path = concept_path(root, concept().concept_id)
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    report = validate_bundle(root)
    assert report.status == "fail" and any("hash mismatch" in e for e in report.errors)


@pytest.mark.parametrize("identifier", ["", "/", "/leading", "trailing/", "double//slash", "../escape", "a/../escape", r"C:\escape", "C:/escape"])
def test_concept_ids_cannot_alias_paths(identifier):
    with pytest.raises(KnowledgeBundleError):
        parse_concept_id(identifier)


def test_duplicate_ids_and_stale_files_are_rejected_without_deletion(tmp_path):
    root = tmp_path / "bundle"
    with pytest.raises(KnowledgeBundleError, match="duplicate"):
        build_bundle(root, [concept(), concept()])
    build_bundle(root, [concept()])
    before = concept_path(root, concept().concept_id).read_bytes()
    with pytest.raises(KnowledgeBundleError, match="stale"):
        build_bundle(root, [concept("different/item")])
    assert concept_path(root, concept().concept_id).read_bytes() == before


@pytest.mark.parametrize("name,raw", [("extra.bin", b"fictional"), ("extra.md", b"not a concept")])
def test_unmanifested_files_fail_validation(tmp_path, name, raw):
    root = tmp_path / "bundle"
    build_bundle(root, [concept()])
    (root / name).write_bytes(raw)
    assert validate_bundle(root).status == "fail"


def test_absent_manifest_does_not_count_as_review(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    assert validate_bundle(root).status == "fail"


def test_manifest_traversal_is_rejected(tmp_path):
    root = tmp_path / "bundle"
    build_bundle(root, [concept()])
    path = root / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["concepts"][0]["path"] = "../private.md"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert validate_bundle(root).status == "fail"


def test_symlinked_concept_is_not_followed(tmp_path):
    root = tmp_path / "bundle"
    build_bundle(root, [concept()])
    target = tmp_path / "separate.md"
    target.write_text("fictional secret", encoding="utf-8")
    link = root / "linked.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert validate_bundle(root).status == "fail"
    with pytest.raises(KnowledgeBundleError):
        read_concept(root, link)
    assert target.read_text(encoding="utf-8") == "fictional secret"


@pytest.mark.parametrize("header", ['title: "a"\ntitle: "b"', 'title: {"object":true}', 'title: [1]'])
def test_frontmatter_duplicate_or_object_values_are_rejected(header):
    with pytest.raises(KnowledgeBundleError):
        split_document("---\n" + header + "\n---\nfictional body")
