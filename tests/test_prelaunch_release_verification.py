from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-prelaunch-release.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_prelaunch_release", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_resolution_stays_within_the_checkout() -> None:
    module = _load_module()
    candidate = module._resolve_candidate("dist/candidate/msix/example.msix")
    assert candidate == ROOT / "dist" / "candidate" / "msix" / "example.msix"

    try:
        module._resolve_candidate(r"C:\outside\candidate.msix")
    except ValueError as exc:
        assert "inside the repository" in str(exc)
    else:
        raise AssertionError("outside package candidate must be rejected")


def test_readiness_receipt_binds_to_the_selected_candidate() -> None:
    module = _load_module()
    candidate = ROOT / "dist" / "candidate" / "msix" / "example.msix"
    report = module.build_report(package=candidate)
    assert report["artifact"]["path"] == "dist/candidate/msix/example.msix"
    assert report["artifact"]["exists"] is False
    assert report["candidate_evidence"]["build_summary"]["status"] == "blocked"
    assert report["candidate_evidence"]["wack"]["hash_matches_candidate"] is False
    assert report["overall_status"] == "NOT_READY"


def test_candidate_evidence_rejects_a_build_receipt_from_another_package(tmp_path) -> None:
    module = _load_module()
    candidate = tmp_path / "candidate" / "msix" / "example.msix"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"fictional-msix")
    evidence = candidate.parent.parent / "evidence"
    evidence.mkdir()
    (evidence / "test-summary.txt").write_text(
        "MSIX build: PASS\nPackage SHA-256: " + "0" * 64 + "\n", encoding="utf-8"
    )

    report = module._candidate_evidence(candidate)
    assert report["build_summary"]["status"] == "blocked"
