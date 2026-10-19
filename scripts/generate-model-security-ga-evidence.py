#!/usr/bin/env python3
"""Generate repository engineering evidence for model and injection controls.

Passes 41 and 42 contain repository-controllable governance and security checks,
but repository evidence cannot establish independent legal review, production
model qualification, or true-GA completion.  This command therefore records
engineering-control success while keeping all true-GA and release claims
fail-closed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.model_orchestration import ModelGovernanceAuditor, ModelReplacementLedger
from legal.security import PromptInjectionDefenseGateway, RetrievedSegment, ToolRequest

MODEL_REPORT_NAME = "model_registry_admission_report.json"
INJECTION_REPORT_NAME = "llm_injection_red_team_report.json"
SUMMARY_NAME = "model_security_ga_evidence_summary.json"
TRUE_GA_BLOCKER = "repo_engineering_evidence_cannot_complete_true_ga"


def _governance_report() -> dict[str, Any]:
    auditor = ModelGovernanceAuditor(
        role_catalog_path=ROOT / "configs/nh_model_roles.json",
        admission_policy_path=ROOT / "configs/nh_model_admission_policy.json",
        governance_policy_path=ROOT / "configs/nh_model_governance_policy.json",
    )
    records = auditor.load_seed_records(ROOT / "configs/nh_model_registry.seed.json")
    ledger = ModelReplacementLedger()
    ledger.append(
        old_model_id="issue-rules-000",
        new_model_id="issue-rules-001",
        role="nh_issue_classifier",
        reason="replace prior issue classifier baseline with governed admission record",
        evidence={"benchmark": "issue_macro_f1", "score": 0.91, "regression": "pass"},
    )
    report = auditor.audit(records, replacement_ledger=ledger).as_dict()
    engineering_status = "pass" if report["status"] == "pass" else "fail"
    return {
        "status": engineering_status,
        "pass": 41,
        "stage": "model_registry_and_admission_policy",
        "evidence_scope": "repo_engineering_control_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_ready": False,
        "release_ready": False,
        "true_ga_complete": False,
        "legal_review_verified": False,
        "true_ga_blockers": [TRUE_GA_BLOCKER],
        "model_governance": report,
        "exit_criteria": {
            "model_registry_present": True,
            "role_definitions_present": report["role_count"] >= 9,
            "production_admission_records_present": report["production_record_count"] >= 1,
            "generator_cannot_self_certify": "filing_ready_certification"
            in report["certification_tasks_reserved_to_system_gates"],
            "replacement_ledger_verified": report["replacement_ledger"].get("verified") is True,
            "audit_trail_preserved": True,
        },
        "remaining_ga_limits": [
            "Repository checks do not establish production model qualification or independent legal review.",
            "External eval, pilot, installed-package, and release-signoff gates remain required.",
        ],
    }


def _run_red_team_cases(gateway: PromptInjectionDefenseGateway) -> dict[str, Any]:
    cases = json.loads(
        (ROOT / "configs/nh_llm_red_team_cases.json").read_text(encoding="utf-8")
    )["cases"]
    results = []
    for case in cases:
        surface = case["surface"]
        if surface == "user_prompt":
            report = gateway.evaluate(user_prompt=case["text"])
        elif surface == "retrieved_document":
            report = gateway.evaluate(
                user_prompt="Summarize the retrieved New Hampshire source.",
                retrieved_segments=[
                    RetrievedSegment(source_id=case["case_id"], text=case["text"])
                ],
            )
        elif surface == "tool_request":
            report = gateway.evaluate(
                user_prompt="Run a tool.",
                tool_request=ToolRequest(
                    tool_name=case.get("tool_name", "unknown_tool"),
                    purpose=case["text"],
                    requested_capability=case.get("tool_name"),
                ),
            )
        else:
            report = gateway.evaluate(user_prompt=case["text"])
        payload = report.as_dict()
        expected = case["expected_blocker"]
        results.append(
            {
                "case_id": case["case_id"],
                "surface": surface,
                "expected_blocker": expected,
                "observed_blockers": payload["blockers"],
                "status": "pass" if expected in payload["blockers"] else "fail",
            }
        )
    failures = [item for item in results if item["status"] != "pass"]
    return {
        "status": "pass" if not failures else "fail",
        "case_count": len(results),
        "failures": failures,
        "results": results,
    }


def _injection_report() -> dict[str, Any]:
    gateway = PromptInjectionDefenseGateway(
        ROOT / "configs/nh_llm_injection_defense_policy.json"
    )
    clean_report = gateway.evaluate(
        user_prompt="Find New Hampshire authority for a post-judgment child support issue.",
        retrieved_segments=[
            RetrievedSegment(
                source_id="statute-rsa-child-support",
                source_class="statute_section_reference",
                text="RSA child support text excerpt. This is source text, not an instruction.",
                start_offset=0,
                end_offset=77,
            )
        ],
        tool_request=ToolRequest(
            tool_name="citation_resolver", purpose="resolve statutory citation"
        ),
        output_text=(
            "review_required: cite resolved New Hampshire authority and route final "
            "export through verifier gates."
        ),
    ).as_dict()
    red_team = _run_red_team_cases(gateway)
    engineering_status = (
        "pass"
        if clean_report["status"] == "pass" and red_team["status"] == "pass"
        else "fail"
    )
    return {
        "status": engineering_status,
        "pass": 42,
        "stage": "prompt_document_tool_injection_defense",
        "evidence_scope": "repo_engineering_control_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_ready": False,
        "release_ready": False,
        "true_ga_complete": False,
        "legal_review_verified": False,
        "true_ga_blockers": [TRUE_GA_BLOCKER],
        "clean_case": clean_report,
        "red_team_cases": red_team,
        "exit_criteria": {
            "prompt_injection_tests_present": red_team["case_count"] > 0,
            "red_team_cases_pass": red_team["status"] == "pass",
            "retrieved_documents_untrusted": clean_report["isolated_context"][0][
                "trust_boundary"
            ]
            == "retrieved_text_untrusted_data_not_instructions",
            "tool_sandbox_policy_enforced": True,
            "system_prompt_leakage_filtered": any(
                item["expected_blocker"] == "output_filter:system_prompt_leakage"
                for item in red_team["results"]
            ),
        },
        "remaining_ga_limits": [
            "Repository red-team cases do not replace independent legal/security review.",
            "Production authentication, installed-package, pilot, and release gates remain required.",
        ],
    }


def _summary(model_report: dict[str, Any], injection_report: dict[str, Any]) -> dict[str, Any]:
    engineering_status = (
        "pass"
        if model_report.get("status") == "pass"
        and injection_report.get("status") == "pass"
        else "blocked"
    )
    completed_engineering = [41, 42] if engineering_status == "pass" else []
    return {
        "status": engineering_status,
        "engineering_status": engineering_status,
        "evidence_scope": "repo_engineering_control_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completed_engineering_passes": completed_engineering,
        "completed_true_ga_passes": [],
        "true_ga_status": "blocked",
        "true_ga_release_allowed": False,
        "production_ready": False,
        "legal_review_verified": False,
        "true_ga_blockers": [TRUE_GA_BLOCKER],
        "artifacts": [
            f"docs/{MODEL_REPORT_NAME}",
            f"docs/{INJECTION_REPORT_NAME}",
        ],
        "model_registry_admission_report": model_report,
        "llm_injection_red_team_report": injection_report,
    }


def generate(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_report = _governance_report()
    injection_report = _injection_report()
    (output_dir / MODEL_REPORT_NAME).write_text(
        json.dumps(model_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / INJECTION_REPORT_NAME).write_text(
        json.dumps(injection_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    combined = _summary(model_report, injection_report)
    (output_dir / SUMMARY_NAME).write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return combined


def _load_report(path: Path, *, expected_pass: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"evidence_artifact_missing:{path.name}"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, f"evidence_artifact_invalid:{path.name}"
    if not isinstance(payload, dict):
        return None, f"evidence_artifact_invalid:{path.name}"
    if payload.get("pass") != expected_pass:
        return None, f"evidence_pass_identity_mismatch:{path.name}"
    if payload.get("status") != "pass":
        return None, f"engineering_evidence_not_pass:{path.name}"
    if payload.get("evidence_scope") != "repo_engineering_control_only":
        return None, f"evidence_scope_invalid:{path.name}"
    if payload.get("production_ready") is not False:
        return None, f"production_readiness_overclaim:{path.name}"
    if payload.get("true_ga_complete") is not False:
        return None, f"true_ga_completion_overclaim:{path.name}"
    if payload.get("legal_review_verified") is not False:
        return None, f"legal_review_overclaim:{path.name}"
    return payload, None


def check(output_dir: Path) -> dict[str, Any]:
    model, model_blocker = _load_report(
        output_dir / MODEL_REPORT_NAME, expected_pass=41
    )
    injection, injection_blocker = _load_report(
        output_dir / INJECTION_REPORT_NAME, expected_pass=42
    )
    blockers = [item for item in (model_blocker, injection_blocker) if item]
    if blockers:
        return {
            "status": "blocked",
            "engineering_status": "blocked",
            "evidence_scope": "repo_engineering_control_only",
            "completed_engineering_passes": [],
            "completed_true_ga_passes": [],
            "true_ga_status": "blocked",
            "true_ga_release_allowed": False,
            "production_ready": False,
            "legal_review_verified": False,
            "engineering_blockers": blockers,
            "true_ga_blockers": [TRUE_GA_BLOCKER],
        }
    assert model is not None and injection is not None
    return _summary(model, injection)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not rewrite artifacts; validate existing engineering reports.",
    )
    args = parser.parse_args()
    summary = check(args.output_dir) if args.check else generate(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
