from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from legal.ops import SupplyChainAuditor
from legal.release import AttributionKitBuilder, PublicRepoReadinessAuditor


def test_attribution_kit_generates_required_public_files(tmp_path: Path) -> None:
    root = tmp_path / "source"
    (root / "configs").mkdir(parents=True)
    catalog = Path("configs/nh_enterprise_resource_catalog.json")
    shutil.copyfile(Path(__file__).resolve().parents[1] / catalog, root / catalog)
    report = AttributionKitBuilder(project_root=root).build(write=True)
    assert report.status == "pass"
    assert report.resource_count >= 10
    assert report.official_source_count >= 10
    for file_name in ["LICENSE.md", "NOTICE.md", "ATTRIBUTION.md", "CITATION.cff"]:
        assert (root / file_name).is_file()
    assert "not legal advice" in (root / "LICENSE.md").read_text(encoding="utf-8")
    assert "Do not cite this repository as legal authority" in (root / "CITATION.cff").read_text(encoding="utf-8")


def test_supply_chain_auditor_builds_source_sbom_and_keeps_legal_readiness_blocked(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    report = SupplyChainAuditor(project_root=root).audit(write_sbom=True, output_path=tmp_path / "source_sbom.json")
    assert report.status == "pass"
    assert report.production_legal_ready is False
    assert report.script_count >= 20
    assert report.workflow_count >= 1
    assert (tmp_path / "source_sbom.json").is_file()
    sbom = json.loads((tmp_path / "source_sbom.json").read_text(encoding="utf-8"))
    assert sbom["source_only"] is True
    assert sbom["production_legal_ready"] is False
    assert any(component["type"] == "enterprise-resource-catalog" for component in sbom["components"])


def test_public_readiness_requires_attribution_kit_and_still_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [root / name for name in ("LICENSE.md", "NOTICE.md", "ATTRIBUTION.md", "CITATION.cff")]
    before = [path.read_bytes() for path in paths]
    AttributionKitBuilder(project_root=root).build(write=True)
    assert [path.read_bytes() for path in paths] == before
    report = PublicRepoReadinessAuditor(project_root=root).audit()
    assert report.status == "pass"
    assert report.public_source_ready is True
    assert report.production_legal_ready is False


def test_public_readiness_ignores_workbench_cache() -> None:
    root = Path(__file__).resolve().parents[1]
    cache_dir = root / ".nhfl_work" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="audit-fixture-", dir=cache_dir) as fixture:
        (Path(fixture) / "fixture.metadata.json").write_text('{"token": "not-a-secret-cache"}', encoding="utf-8")
        report = PublicRepoReadinessAuditor(project_root=root).audit()

    assert report.status == "pass"
    assert not any(".nhfl_work" in finding.path for finding in report.findings)
