"""Pass 10 request-boundary and external-evaluation-root regressions.

All paths, payloads, and service outputs in this module are synthetic. These
checks are engineering controls, not legal-authority or release qualification.
"""
from __future__ import annotations

import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import authority
from legal.evals import external_eval_root as roots


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic-source-project"
    root.mkdir()
    return root


def test_authority_boolean_is_validated_before_service_construction(monkeypatch) -> None:
    def forbidden_constructor():
        raise AssertionError("service construction must not precede request validation")

    monkeypatch.setattr(authority, "AuthorityProductService", forbidden_constructor)
    with pytest.raises(HTTPException) as caught:
        authority.verify_active_authority_output({"auto_extract_claims": "true"})
    assert caught.value.status_code == 422
    assert caught.value.detail == {
        "error": "strict_json_boolean_required",
        "field": "auto_extract_claims",
    }


@pytest.mark.parametrize("invalid", [1, 0, None, [], {}, "false"])
def test_authority_boolean_rejects_non_boolean_values_before_storage(monkeypatch, invalid) -> None:
    constructed = False

    def forbidden_constructor():
        nonlocal constructed
        constructed = True
        raise OSError("synthetic private path must not be exposed")

    monkeypatch.setattr(authority, "AuthorityProductService", forbidden_constructor)
    with pytest.raises(HTTPException) as caught:
        authority.verify_active_authority_output({"auto_extract_claims": invalid})
    assert caught.value.status_code == 422
    assert constructed is False


@pytest.mark.parametrize("value", [True, False])
def test_authority_boolean_preserves_exact_values(monkeypatch, value) -> None:
    observed: dict[str, object] = {}

    class FakeService:
        def verify_output(self, **kwargs):
            observed.update(kwargs)
            return {"status": "blocked", "review_required": True}

    monkeypatch.setattr(authority, "AuthorityProductService", FakeService)
    result = authority.verify_active_authority_output({"auto_extract_claims": value})
    assert observed["auto_extract_claims"] is value
    assert result["review_required"] is True


def test_default_resolution_without_create_has_no_side_effect(project, tmp_path, monkeypatch) -> None:
    home = tmp_path / "safe-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    expected = home / ".codex" / roots.DEFAULT_EVAL_DIRNAME / project.name
    resolved = roots.resolve_external_eval_root(None, project_root=project, create=False)
    assert resolved == expected
    assert not home.exists()


def test_default_creation_occurs_only_after_validation(project, tmp_path, monkeypatch) -> None:
    home = tmp_path / "safe-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    expected = home / ".codex" / roots.DEFAULT_EVAL_DIRNAME / project.name
    assert roots.default_external_eval_root(project) == expected
    assert expected.is_dir()


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_default_inside_checkout_is_rejected_without_creation(project, monkeypatch, configured) -> None:
    home = project / "synthetic-profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(configured, project_root=project, create=True)
    assert caught.value.code == "external_root_inside_source_repo"
    assert not home.exists()


def test_explicit_inside_checkout_is_rejected_without_creation(project) -> None:
    candidate = project / "evals"
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(candidate, project_root=project, create=True)
    assert caught.value.code == "external_root_inside_source_repo"
    assert not candidate.exists()


@pytest.mark.parametrize("raw", ["../escape", r"..\escape", r"C:\safe\..\escape", "safe/../escape"])
def test_cross_platform_traversal_is_rejected(project, raw) -> None:
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(raw, project_root=project)
    assert caught.value.code == "external_eval_root_path_traversal"


@pytest.mark.parametrize("kind", ["root", "ancestor", "dangling"])
def test_linked_paths_are_refused_without_touching_targets(project, tmp_path, kind) -> None:
    target = tmp_path / "separate-target"
    if kind != "dangling":
        target.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    candidate = link / "evals" if kind == "ancestor" else link
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(candidate, project_root=project, create=True)
    assert caught.value.code == "external_eval_root_symlink_refused"
    if kind == "ancestor":
        assert not (target / "evals").exists()
    if kind == "dangling":
        assert not target.exists()


def test_reparse_point_is_rejected_before_resolve(project, tmp_path, monkeypatch) -> None:
    junction = tmp_path / "synthetic-junction"
    real = Path.lstat

    def metadata(path: Path, *args, **kwargs):
        if path == junction:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(junction / "evals", project_root=project, create=True)
    assert caught.value.code == "external_eval_root_symlink_refused"
    assert not junction.exists()


@pytest.mark.parametrize("leaf", ["data", "priv", "matter", "system", "normal-profile"])
def test_harmless_partial_segments_do_not_reverse_match(project, tmp_path, leaf) -> None:
    candidate = tmp_path / leaf / "external-evals"
    # "matter" is not protected by this eval-root policy; matter_store is.
    assert roots.resolve_external_eval_root(candidate, project_root=project) == candidate
    assert not candidate.exists()


@pytest.mark.parametrize(
    "segment",
    ["private", "matter_store", "eval_data", "msix", "staging", "WindowsApps", "ProgramData", "system32"],
)
def test_protected_segments_are_rejected_before_creation(project, tmp_path, segment) -> None:
    candidate = tmp_path / segment / "evals"
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(candidate, project_root=project, create=True)
    assert caught.value.code == "external_eval_root_inside_forbidden_root"
    assert not candidate.parent.exists()


def test_layout_rejects_linked_child_before_creating_siblings(project, tmp_path) -> None:
    root = tmp_path / "safe-evals"
    target = tmp_path / "separate-reviews"
    root.mkdir()
    target.mkdir()
    try:
        (root / "reviews").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.external_eval_root_layout(root, project_root=project, create=True)
    assert caught.value.code == "external_eval_root_symlink_refused"
    assert not (root / "annotation_queue").exists()
    assert not list(target.iterdir())



def test_eval_root_cannot_contain_the_source_checkout(project) -> None:
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(project.parent, project_root=project, create=False)
    assert caught.value.code == "external_root_contains_forbidden_root"


@pytest.mark.parametrize("raw", ["\x00", "~synthetic-user-that-does-not-exist/evals"])
def test_invalid_eval_paths_are_sanitized(project, raw) -> None:
    with pytest.raises(roots.ExternalEvalRootError) as caught:
        roots.resolve_external_eval_root(raw, project_root=project, create=False)
    assert caught.value.code == "external_eval_root_path_invalid"
    assert raw not in str(caught.value)

def test_pass10_readiness_metadata_matches_active_version() -> None:
    import json

    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / "configs/nh_ga_shipment_readiness_policy.json").read_text(encoding="utf-8"))
    assert policy["product_version"] == "8.0.10"
    assert policy["application_may_claim_store_approval"] is False
    assert policy["application_may_claim_ga_shipment"] is False


def test_sample_evidence_manifest_is_explicitly_nonproduction() -> None:
    import json

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "docs/sample-evidence/manifest.json").read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": "nhfl.sample_evidence_manifest.v1",
        "files": ["local_smoke_report.json"],
        "production_evidence": False,
        "review_required": True,
    }


def test_pass10_workflows_keep_full_and_focused_gates_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    focused = (root / ".github/workflows/nh-pass10-boundary-hardening.yml").read_text(encoding="utf-8")
    full = (root / ".github/workflows/nh-pass10-full-regression.yml").read_text(encoding="utf-8")
    assert "tests/test_pass10_boundary_inputs.py" in focused
    assert "run-public-source-preflight.py" in focused
    assert "python -m pytest" in focused
    assert "pytest', 'tests'" in full
    assert "xvfb-run" in full
    assert "continue-on-error" not in focused + full
    assert "if: always()" in focused and "if: always()" in full
