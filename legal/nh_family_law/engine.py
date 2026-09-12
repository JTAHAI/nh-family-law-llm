from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .authorities import AuthorityGate
from .drafting import apply_drafting_controls
from .errors import AuthoritySnapshotUnavailable, InvalidLegalBehaviorInput
from .forms import select_form_categories
from .interstate import analyze_interstate
from .issue_spotting import spot_issues
from .jurisdiction import apply_jurisdiction_controls
from .models import Finding, LegalBehaviorReport, RouteRecommendation
from .parenting import analyze_parenting
from .support import analyze_support
from .support_authority import analyze_support_order_authority
from .utils import clean_text, parse_date


class NewHampshireLegalBehaviorEngine:
    """Source-gated issue spotter for NH parenting and child-support workflows."""

    def __init__(self, *, manifest_path: str | Path | None = None) -> None:
        self.manifest_path = manifest_path

    @staticmethod
    def _validate_and_normalize(payload: dict[str, Any]) -> tuple[dict[str, Any], date]:
        if not isinstance(payload, dict):
            raise InvalidLegalBehaviorInput("input must be a JSON object")

        for field in ("parenting", "support", "support_order", "interstate"):
            value = payload.get(field)
            if value is not None and not isinstance(value, dict):
                raise InvalidLegalBehaviorInput(f"{field} must be an object")
        safety = payload.get("safety")
        if safety is not None and not isinstance(safety, (bool, dict)):
            raise InvalidLegalBehaviorInput("safety must be a boolean or object")

        raw_as_of = payload.get("as_of_date")
        as_of = parse_date(raw_as_of) if raw_as_of not in (None, "") else date.today()
        if as_of is None:
            raise InvalidLegalBehaviorInput("as_of_date must use YYYY-MM-DD")

        normalized = dict(payload)
        for field, limit in (("question", 20_000), ("draft_text", 50_000)):
            value = normalized.get(field)
            if value is None:
                if field == "question":
                    normalized[field] = ""
                continue
            if not isinstance(value, str):
                raise InvalidLegalBehaviorInput(f"{field} must be a string")
            if len(value) > limit:
                raise InvalidLegalBehaviorInput(f"{field} exceeds {limit} characters")
            normalized[field] = clean_text(value, limit=limit) if field == "question" else value
        return normalized, as_of

    def analyze(self, payload: dict[str, Any]) -> LegalBehaviorReport:
        normalized, as_of = self._validate_and_normalize(payload)
        question = normalized["question"]
        report = LegalBehaviorReport(as_of_date=as_of.isoformat())
        report.issues = spot_issues(question, normalized)
        apply_jurisdiction_controls(normalized, report)

        required_keys: list[str] = []
        if any(issue in report.issues for issue in ("parenting_modification", "parenting_plan", "decision_making", "parenting_enforcement", "relocation")):
            required_keys.extend(analyze_parenting(normalized, report))
        if "child_support_modification" in report.issues:
            required_keys.extend(analyze_support(normalized, report, as_of=as_of))
        if "administrative_support" in report.issues or normalized.get("support_order"):
            required_keys.extend(analyze_support_order_authority(normalized, report))
        if "uccjea" in report.issues or "uifsa" in report.issues:
            required_keys.extend(analyze_interstate(normalized, report))

        if "self_representation" in report.issues:
            report.routes.append(
                RouteRecommendation(
                    route_id="self_representation_preparation",
                    label="Self-representation preparation",
                    status="official_forms_and_rules_must_be_verified",
                    explanation=(
                        "A self-represented party should verify the current NH Judicial Branch "
                        "form, revision date, filing fee or waiver, service method, financial "
                        "disclosures, mediation requirements, and hearing instructions before filing."
                    ),
                    next_documents=(
                        "complete signed orders",
                        "current court docket",
                        "official current form packet",
                        "financial affidavit and guideline worksheet when support is at issue",
                    ),
                    form_categories_to_verify=(
                        "motion or petition matching the requested relief",
                        "appearance and service materials",
                        "fee-waiver materials if needed",
                    ),
                )
            )
            report.authority_gaps.append(
                "Current NH Judicial Branch forms and procedural rules are not promoted in the core capsule snapshot"
            )

        if "safety" in report.issues:
            report.findings.append(Finding(
                finding_id="safety_escalation",
                title="Safety issue requires immediate human triage",
                status="possible_requires_evidence",
                explanation="Safety allegations affect parenting, decision-making, mediation, confidentiality, and emergency-jurisdiction analysis. The engine does not determine whether abuse occurred.",
                severity="blocker",
                authority_ids=("NH-V0014", "NH-V0015", "NH-V0029"),
                evidence_needed=("current protection orders", "law-enforcement or medical records if any", "safe contact and address-handling needs"),
            ))
            required_keys.extend(["decision_making", "best_interest", "uccjea_emergency"])

        apply_drafting_controls(normalized, report)
        select_form_categories(report.issues, normalized, report)

        try:
            gate = AuthorityGate(as_of=as_of, manifest_path=self.manifest_path)
            refs, gaps = gate.resolve(dict.fromkeys(required_keys))
        except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
            raise AuthoritySnapshotUnavailable(
                f"NH authority snapshot could not be verified: {exc}"
            ) from exc
        report.add_authorities(refs)
        report.authority_gaps.extend(gaps)
        unavailable = {ref.authority_id for ref in refs if not ref.retrieval_eligible}
        if unavailable:
            report.findings.append(Finding(
                finding_id="required_authority_unavailable",
                title="One or more required authorities are not active",
                status="blocked_missing_authority",
                explanation="The engine will not convert an unverified, future-effective, missing, or hash-invalid source into a legal conclusion.",
                severity="blocker",
                authority_ids=tuple(sorted(unavailable)),
            ))

        report.notices.extend([
            "This report is legal information and issue spotting, not legal advice or a prediction of outcome.",
            "Reported facts are not treated as proven facts; preserve complete source records and identify disputes.",
            "The court or authorized administrative tribunal—not this engine—determines legal standards, credibility, relief, and support amounts.",
        ])
        report.deduplicate()
        return report
