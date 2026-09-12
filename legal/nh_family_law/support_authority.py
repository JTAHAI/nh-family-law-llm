from __future__ import annotations

from typing import Any

from .models import Finding, LegalBehaviorReport, RouteRecommendation
from .utils import tri


def analyze_support_order_authority(payload: dict[str, Any], report: LegalBehaviorReport) -> list[str]:
    facts = payload.get("support_order") or payload.get("support") or {}
    court_order = tri(facts.get("has_signed_court_support_order"))
    admin_notice = tri(facts.get("has_rsa_161_c_notice_of_hearing"))
    admin_decision = tri(facts.get("has_rsa_161_c_hearing_decision"))
    collection_only = tri(facts.get("dhhs_only_collects_or_withholds"))
    required = ["administrative_order_definition", "support_modification"]

    if court_order == "yes":
        required.append("administrative_collection")
        report.routes.append(RouteRecommendation(
            route_id="court_support_order_controls",
            label="Court-issued support order",
            status="court_order_reported",
            explanation="A signed court support order points to the court as the issuing tribunal. DHHS payment processing, withholding, or collection does not by itself make DHHS the issuer of the amount.",
            authority_ids=("NH-V0022", "NH-V0008"),
            next_documents=("signed Uniform Support Order", "court docket and order date", "DHHS account/collection notices"),
            form_categories_to_verify=("court child-support modification filing", "guidelines worksheet", "Uniform Support Order"),
        ))
        if admin_decision == "yes":
            report.findings.append(Finding(
                finding_id="court_admin_overlap",
                title="Court and administrative documents both reported",
                status="possible_requires_evidence",
                explanation="A later legal support order supersedes an RSA 161-C decision to the extent the amounts differ, but dates and exact terms must be compared.",
                severity="warning",
                authority_ids=("NH-V0024",),
                evidence_needed=("administrative decision", "later court order", "effective dates and payment ledger"),
            ))
    elif admin_decision == "yes":
        required.extend(["administrative_establishment", "administrative_hearing"])
        report.routes.append(RouteRecommendation(
            route_id="rsa_161_c_administrative_order",
            label="DHHS administrative support order",
            status="administrative_decision_reported",
            explanation="A served RSA 161-C hearing decision is an enforceable administrative support order. Modification is directed to the issuing department unless and until a later legal support order supersedes it to the extent different.",
            authority_ids=("NH-V0023", "NH-V0024", "NH-V0008"),
            next_documents=("notice of hearing and finding of financial responsibility", "served hearing decision", "proof of service", "any later court order"),
            form_categories_to_verify=("DHHS administrative modification request",),
        ))
    elif admin_notice == "yes":
        required.extend(["administrative_establishment", "administrative_hearing"])
        report.routes.append(RouteRecommendation(
            route_id="rsa_161_c_pending_establishment",
            label="Pending RSA 161-C administrative establishment",
            status="administrative_hearing_notice_reported",
            explanation="When no legal support order exists, DHHS may use the RSA 161-C notice-and-hearing process. The notice and hearing date require prompt review; a payment demand alone should not be mistaken for the final decision.",
            authority_ids=("NH-V0023", "NH-V0024"),
            next_documents=("complete notice", "service date", "hearing date", "income/property evidence", "proof of other dependents and support obligations"),
            form_categories_to_verify=("DHHS hearing response or modification materials",),
        ))
    elif collection_only == "yes":
        required.append("administrative_collection")
        report.findings.append(Finding(
            finding_id="dhhs_collection_not_issuer",
            title="DHHS collection activity does not identify the issuer",
            status="possible_requires_evidence",
            explanation="Income withholding or payment through DHHS may administer a court order or an administrative order. The original signed order or served decision is needed to determine who can modify the amount.",
            severity="blocker",
            authority_ids=("NH-V0022", "NH-V0008"),
            evidence_needed=("signed court order or served RSA 161-C decision",),
        ))
        report.missing_facts.append("The original document establishing the support amount")
    else:
        required.extend(["administrative_collection", "administrative_establishment", "administrative_hearing"])
        report.findings.append(Finding(
            finding_id="support_issuer_unknown",
            title="Support-order issuer is unknown",
            status="blocked_missing_fact",
            explanation="The engine cannot route a modification from a payment ledger, wage-withholding notice, or text summary alone.",
            severity="blocker",
            authority_ids=("NH-V0008", "NH-V0022", "NH-V0023", "NH-V0024"),
            evidence_needed=("signed Uniform Support Order", "RSA 161-C notice and hearing decision", "all later modification orders"),
        ))
        report.missing_facts.append("Whether the amount was established by a court order or an RSA 161-C administrative decision")

    report.notices.append("Do not stop paying or self-adjust the amount based on this routing report. Existing enforceable orders remain in effect until modified, stayed, or superseded by authorized process.")
    return required
