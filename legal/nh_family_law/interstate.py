from __future__ import annotations

from typing import Any

from .models import Finding, LegalBehaviorReport, RouteRecommendation
from .utils import clean_text, tri


def analyze_interstate(payload: dict[str, Any], report: LegalBehaviorReport) -> list[str]:
    facts = payload.get("interstate") or {}
    required = ["uccjea_initial", "uccjea_continuing", "uccjea_modify", "uccjea_emergency", "uccjea_notice", "uccjea_parallel", "uccjea_forum", "uccjea_conduct", "uccjea_disclosure"]
    issuing_state = clean_text(facts.get("parenting_order_state"), limit=64).upper()
    child_present_nh = tri(facts.get("child_present_in_nh"))
    emergency = tri(facts.get("mistreatment_abuse_or_abandonment_emergency"))
    proceeding_elsewhere = tri(facts.get("proceeding_pending_elsewhere"))

    if emergency == "yes" and child_present_nh == "yes":
        report.routes.append(RouteRecommendation(
            route_id="uccjea_temporary_emergency",
            label="Temporary emergency jurisdiction review",
            status="emergency_facts_reported",
            explanation="The reported facts may support temporary emergency jurisdiction while ordinary jurisdiction remains with the appropriate state; court-to-court communication and time limits may be required.",
            authority_ids=("NH-V0029", "NH-V0031"),
            next_documents=("existing out-of-state order", "current safety evidence", "child's location", "other-state docket and contact information"),
            form_categories_to_verify=("emergency parenting filing", "confidential address/safety filing if needed"),
        ))

    if issuing_state and issuing_state not in {"NH", "NEW HAMPSHIRE"}:
        report.routes.append(RouteRecommendation(
            route_id="uccjea_modify_other_state_order",
            label="Interstate parenting-order modification review",
            status="issuing_state_jurisdiction_must_be_resolved",
            explanation="New Hampshire may not ordinarily modify another state's parenting determination merely because a parent or child moved. NH jurisdiction plus loss or relinquishment of the issuing state's continuing jurisdiction must be established.",
            authority_ids=("NH-V0027", "NH-V0028"),
            next_documents=("certified issuing-state order", "all later orders", "residence history for child and both parents", "orders or findings about continuing jurisdiction"),
            form_categories_to_verify=("registration/enforcement materials", "UCCJEA residence-history affidavit", "motion addressing jurisdiction"),
        ))
    elif issuing_state in {"NH", "NEW HAMPSHIRE"}:
        report.routes.append(RouteRecommendation(
            route_id="uccjea_nh_continuing_jurisdiction",
            label="Review New Hampshire continuing jurisdiction",
            status="nh_issuing_state_reported",
            explanation="A New Hampshire court that made a compliant determination generally retains exclusive continuing jurisdiction until the statutory connection/residence conditions are judicially resolved.",
            authority_ids=("NH-V0027",),
            next_documents=("NH order", "current residences", "evidence location and child connections"),
            form_categories_to_verify=("motion in the existing NH case", "UCCJEA residence-history disclosure"),
        ))
    else:
        report.missing_facts.append("State that issued any existing parenting order")

    if proceeding_elsewhere == "yes":
        report.findings.append(Finding(
            finding_id="uccjea_parallel_proceeding",
            title="Parallel custody proceeding requires disclosure",
            status="supported_by_reported_facts",
            explanation="A pending proceeding in another state must be disclosed; the courts may need to communicate and the NH matter may need to be stayed or limited.",
            severity="blocker",
            authority_ids=("NH-V0031", "NH-V0034"),
            evidence_needed=("other-state docket", "pleadings and orders", "hearing dates", "contact information for the other tribunal"),
        ))

    report.evidence_checklist.extend([
        "Child's present location and complete five-year residence history",
        "Every prior or pending parenting/custody proceeding and order",
        "Current residences of both parents and anyone acting as a parent",
        "Location of school, medical, witness, and other substantial evidence",
        "Any safety facts requiring protected address handling",
    ])

    if facts.get("support_order_state") or "uifsa" in str(payload.get("question") or "").casefold():
        required.append("uifsa")
        report.routes.append(RouteRecommendation(
            route_id="uifsa_review",
            label="Interstate support jurisdiction review",
            status="blocked_pending_current_uifsa_authority",
            explanation="Interstate support uses RSA 546-B rather than the UCCJEA. The current repository has only an unverified chapter seed, so it will not decide registration, controlling-order, or modification jurisdiction until the relevant sections are promoted.",
            authority_ids=("NH-0027",),
            next_documents=("certified support order and modifications", "payment/arrears record", "residences of child and parties", "any written jurisdiction consents", "registration papers"),
            form_categories_to_verify=("UIFSA registration or modification filing",),
        ))
        report.authority_gaps.append("RSA 546-B UIFSA sections are inventoried but not promoted as current retrieval authority")
    return required
