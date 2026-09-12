from __future__ import annotations

import re
from typing import Any

from .models import Finding, LegalBehaviorReport

FORBIDDEN_OUTCOME_PATTERNS = (
    re.compile(
        r"\b(the court will|the judge (?:will|must)|guaranteed|automatic(?:ally)? get|"
        r"entitled to 50[/ -]?50|court has to give)\b",
        re.I,
    ),
    re.compile(
        r"\b(stop paying|withhold support|self[- ]adjust|ignore the order|"
        r"pay less before (?:an|the) order changes)\b",
        re.I,
    ),
    re.compile(
        r"\b(child support (?:will|must) be (?:reduced|zero)|support automatically "
        r"(?:drops|ends)|dhhs (?:can|will) override the court)\b",
        re.I,
    ),
)

REQUIRED_CONTROLS = (
    "Separate reported facts from legal standards and requested relief.",
    "State the specific RSA 461-A:11 modification gate before arguing best interests for a permanent-order schedule change.",
    "Do not state that the 2025 approximately-equal-parenting policy automatically reopens or changes an existing order.",
    "Treat parenting-time modification and child-support modification as separate requested relief.",
    "Do not calculate a support amount without the current official guideline table, worksheet inputs, and source date.",
    "Identify whether the support amount was issued by the court or by DHHS under RSA 161-C before naming the modification forum.",
    "Do not treat DHHS collection or withholding as proof that DHHS issued the underlying amount.",
    "Do not give an interstate conclusion without the child's residence history, existing orders, party residences, and pending-proceeding facts.",
    "Every material legal proposition must map to an active, hash-valid authority record and the supported capsule scope.",
    "Every material factual statement must map to evidence or be labeled allegation, estimate, or unknown.",
    "Existing orders remain enforceable unless modified, stayed, or superseded through authorized process.",
    "All drafts remain review-required and not filing-ready until form, service, deadline, citation, evidence, and human-review gates pass.",
)


def apply_drafting_controls(payload: dict[str, Any], report: LegalBehaviorReport) -> None:
    report.drafting_controls.extend(REQUIRED_CONTROLS)
    draft_text = str(payload.get("draft_text") or payload.get("requested_draft") or "")
    for index, pattern in enumerate(FORBIDDEN_OUTCOME_PATTERNS, start=1):
        if pattern.search(draft_text):
            report.findings.append(Finding(
                finding_id=f"draft_overclaim_{index}",
                title="Draft contains prohibited outcome or noncompliance language",
                status="not_supported_by_reported_facts",
                explanation="The proposed text overstates an outcome or suggests unilateral noncompliance. It must be rewritten as a source-grounded, review-required request.",
                severity="blocker",
                evidence_needed=("revised neutral draft",),
            ))
