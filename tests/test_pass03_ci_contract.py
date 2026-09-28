"""Guard the restored CI targets and the deliberately blocking legacy audit."""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_restored_targets_exist_and_contain_real_tests():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    block = text.split("- name: Targeted tests", 1)[1].split("- name:", 1)[0]
    targets = re.findall(r"tests/[\w/]+\.py", block)
    assert len(targets) >= 19 and len(targets) == len(set(targets))
    required = {"tests/test_canonical_document_model.py", "tests/test_retrieval_stack_pass5.py",
                "tests/test_v510_knowledge_bundle.py", "tests/test_pass03_chat_quarantine.py"}
    assert required.issubset(targets)
    for target in targets:
        tree = ast.parse((ROOT / target).read_text(encoding="utf-8"))
        assert any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
                   for node in ast.walk(tree)), target
    assert "continue-on-error" not in text
    assert "!cancelled()" in block
    assert "run-chat-library-evidence.py --require-ready" in text


def test_legacy_evidence_cannot_pass_on_fixture_grounding_alone(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("legacy_chat_evidence_pass03", ROOT / "scripts/run-chat-library-evidence.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    # All original samples/UI checks still execute through the real source
    # app. Only the output path is fictional and owned by this test.
    output = tmp_path / "legacy-evidence.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--require-ready", "--output", str(output)])
    monkeypatch.setenv("NHFL_RUNTIME_MODE", "source")
    monkeypatch.setenv("NHFL_USE_ACTIVE_AUTHORITY_IN_SOURCE", "0")
    assert script.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "blocked" and report["production_legal_ready"] is False
    assert report["scope"] == "development_fixture_chat_and_ui_only"
    assert "legacy_chat_requires_independent_nh_review" in report["blockers"]
    assert report["sample_results"]
    capsys.readouterr()
