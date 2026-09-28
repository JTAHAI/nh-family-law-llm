"""Fixture isolation never exempts the real source tree from storage policy."""
from __future__ import annotations

from pathlib import Path

import pytest

from legal.data_boundaries.storage_layout import ensure_external_authority_root
from legal.resources import EnterpriseResourceCollector
from test_enterprise_resource_collection import tiny_catalog
from test_external_audit_cli_fail_closed import _run_script

ROOT = Path(__file__).resolve().parents[1]


def test_real_checkout_still_rejects_repository_owned_authority_data(tmp_path):
    assert tmp_path.is_relative_to(ROOT / "dist"), "run with repository-owned --basetemp"
    data = tmp_path / "must-not-be-created"
    with pytest.raises(ValueError, match="outside the source repository"):
        ensure_external_authority_root(data, project_root=ROOT)
    assert not data.exists()


def test_synthetic_identity_accepts_only_its_external_sibling(synthetic_source_project):
    sibling = synthetic_source_project.parent / "synthetic-data"
    assert ensure_external_authority_root(sibling) == sibling
    with pytest.raises(ValueError, match="outside the source repository"):
        ensure_external_authority_root(synthetic_source_project / "forbidden-data")
    assert not sibling.exists()
    assert not (synthetic_source_project / "forbidden-data").exists()


def test_bound_api_service_still_rejects_its_source_tree(synthetic_authority_services):
    from nh_family_law_llm import api

    path = synthetic_authority_services / "forbidden-data"
    with pytest.raises(ValueError, match="outside the source repository"):
        api.AuthorityLibraryService(data_root=path)
    assert not path.exists()


def test_collector_keeps_in_source_rejection_with_synthetic_identity(synthetic_source_project):
    data = synthetic_source_project / "forbidden-data"
    with pytest.raises(ValueError, match="inside source repo"):
        EnterpriseResourceCollector(
            project_root=synthetic_source_project, data_root=data,
            catalog=tiny_catalog("https://example.invalid/synthetic"),
        ).collect(dry_run=True)
    assert not data.exists()


def test_synthetic_cli_keeps_default_source_boundary(synthetic_source_project):
    import json

    data = synthetic_source_project / "forbidden-data"
    result = _run_script(
        "audit-authority-build.py", "--data-root", data,
        project_root=synthetic_source_project,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["production_ready"] is False
    assert "external_data_root_inside_repo" in payload["blockers"]
    assert not data.exists()
    for name in ("scripts/audit-authority-build.py", "configs/nh_authority_build_policy.json"):
        assert (synthetic_source_project / name).read_bytes() == (ROOT / name).read_bytes()


@pytest.mark.parametrize("workflow", ["nh-storage-hardening.yml", "nh-wheel-qualification.yml"])
def test_combined_wheel_workflows_preserve_integrity_and_owned_outputs(workflow):
    text = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    assert "--bdist-dir" in text
    assert "artifacts/pass-08/source-gate.json" not in text
    assert "'--installed', '--wheel', str(wheel)" in text or (
        "'--installed',\n              '--wheel', str(wheel)" in text)
    assert "'--output', str(work /" in text
    assert "continue-on-error" not in text
