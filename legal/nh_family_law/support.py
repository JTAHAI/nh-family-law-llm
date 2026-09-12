from __future__ import annotations

from datetime import date
from typing import Any

from .models import Finding, LegalBehaviorReport, RouteRecommendation
from .utils import number, parse_date, tri, years_between

DEDUCTION_FIELDS = (
    "court-ordered or administratively ordered support actually paid to others",
    "50 percent of actual self-employment tax paid",
    "mandatory, non-discretionary retirement contributions",
    "actual state income taxes paid",
    "allowable work-related child-care expenses actually paid by the obligor for the children in the order",
    "medical-support obligation actually paid by the obligor for the children in the order",
)

DEVIATION_FACTORS = (
    "ongoing extraordinary medical, dental, educational, or special-needs expenses",
    "significantly high or low income",
    "economic consequences of stepparents, stepchildren, or other natural/adopted children",
    "reasonable expenses incurred by the obligor while exercising parental rights, if the children's needs in the obligee home can still be met",
    "economic consequences of disposition of the marital home for the child",
    "federal and state tax consequences",
    "parenting schedule and specified cost-sharing conditions",
    "voluntary or court-ordered postsecondary expenses",
    "other special circumstances needed to avoid an unreasonably low or confiscatory order",
)


def _schedule_category(support: dict[str, Any]) -> str:
    left = number(support.get("parenting_percent_obligor"))
    right = number(support.get("parenting_percent_obligee"))
    if left is None or right is None:
        return "unknown"
    if not (0 <= left <= 100 and 0 <= right <= 100):
        return "invalid"
    if left > 40 and right > 40:
        return "approximately_equal"
    if left > 35 and right > 35:
        return "substantially_shared"
    return "not_shared_under_statutory_definitions"


def analyze_support(payload: dict[str, Any], report: LegalBehaviorReport, *, as_of: date) -> list[str]:
    support = payload.get("support") or {}
    required = ["support_income", "support_formula", "support_worksheet", "support_presumption", "support_deviation", "support_modification", "support_duration"]

    issuer = str(support.get("order_issuer") or "unknown").strip().casefold()
    order_facts = payload.get("support_order") or {}
    if issuer == "unknown":
        if tri(order_facts.get("has_signed_court_support_order")) == "yes":
            issuer = "court"
        elif tri(order_facts.get("has_rsa_161_c_hearing_decision")) == "yes":
            issuer = "administrative"
    if issuer in {"court", "family_division", "circuit_court"}:
        route = "court"
    elif issuer in {"dhhs", "bcss", "rsa_161_c", "administrative"}:
        route = "dhhs"
        required.extend(["administrative_establishment", "administrative_hearing"])
    else:
        route = "unknown"
        report.missing_facts.append("Who issued the existing support order: a court or DHHS under RSA 161-C")

    order_date = parse_date(support.get("last_support_order_date"))
    years = years_between(order_date, as_of) if order_date else None
    changed = tri(support.get("substantial_change_of_circumstances"))
    if years is not None and years >= 3:
        route_status = "three_year_review_route_reported"
        explanation = "At least three years are reported to have elapsed since the last support order, so the statute permits an application without showing a substantial change of circumstances."
    elif changed == "yes":
        route_status = "substantial_change_route_reported"
        explanation = "A substantial change is reported; the application may be made before three years, but the asserted change and financial evidence still require review."
    elif years is None:
        route_status = "order_date_required"
        explanation = "The date of the last support order is missing, so the three-year route cannot be assessed."
        report.missing_facts.append("Date of the last child-support order")
    else:
        route_status = "no_modification_basis_identified"
        explanation = "Fewer than three years are reported and no substantial change is established by the supplied facts."

    report.routes.append(RouteRecommendation(
        route_id="child_support_modification",
        label="Child-support modification review",
        status=route_status,
        explanation=explanation + (" The reported issuer points to the Family Division/court." if route == "court" else " The reported issuer points to DHHS's RSA 161-C process." if route == "dhhs" else " The issuer must be determined from the signed order or administrative decision."),
        authority_ids=("NH-V0008", "NH-V0019"),
        next_documents=("signed Uniform Support Order or RSA 161-C decision", "worksheet used for the existing order", "financial affidavits", "proof of service/notice date", "current income and expense records"),
        form_categories_to_verify=("child-support modification filing", "current child-support guidelines worksheet", "Uniform Support Order", "financial affidavit"),
    ))

    if route_status == "no_modification_basis_identified":
        report.findings.append(Finding(
            finding_id="support_modification_timing",
            title="No timing/change route is established",
            status="not_supported_by_reported_facts",
            explanation=explanation,
            severity="blocker",
            authority_ids=("NH-V0008",),
            evidence_needed=("last order date", "documented substantial change since that order"),
        ))

    schedule = _schedule_category(support)
    if schedule == "invalid":
        report.findings.append(Finding(
            finding_id="support_parenting_percent_invalid",
            title="Parenting percentages are invalid",
            status="blocked_missing_fact",
            explanation="Each supplied parenting percentage must be between 0 and 100 and tied to the ordered annual schedule.",
            severity="blocker",
            authority_ids=("NH-V0002",),
        ))
    elif schedule == "unknown":
        report.missing_facts.append("Each parent's percentage of the annual ordered parenting schedule")
    else:
        report.findings.append(Finding(
            finding_id="support_parenting_schedule_category",
            title="Parenting-schedule category for support review",
            status="supported_by_reported_facts",
            explanation={
                "approximately_equal": "Both reported percentages are greater than 40 percent, matching the child-support definition of an approximately equal parenting schedule.",
                "substantially_shared": "Both reported percentages are greater than 35 percent, matching the child-support definition of a substantially shared parenting schedule.",
                "not_shared_under_statutory_definitions": "The reported percentages do not place both parents above the statutory thresholds for approximately equal or substantially shared schedules.",
            }[schedule],
            authority_ids=("NH-V0002", "NH-V0006"),
            caveats=("This classification uses the supplied ordered percentages; the court controls disputed schedule facts.",),
        ))
        left = number(support.get("parenting_percent_obligor"))
        right = number(support.get("parenting_percent_obligee"))
        if left is not None and right is not None and abs((left + right) - 100.0) > 0.5:
            report.findings.append(Finding(
                finding_id="support_parenting_percent_total",
                title="Parenting percentages require reconciliation",
                status="blocked_missing_fact",
                explanation="The supplied annual parenting percentages do not total approximately 100 percent. Recalculate them from the signed schedule before applying a statutory category.",
                severity="blocker",
                authority_ids=("NH-V0002",),
                evidence_needed=("signed annual parenting schedule", "neutral day/hour calculation"),
            ))

    similar = tri(support.get("substantially_similar_incomes"))
    obligor_gross = number(support.get("gross_monthly_income_obligor"))
    obligee_gross = number(support.get("gross_monthly_income_obligee"))
    if similar == "unknown" and obligor_gross is not None and obligee_gross is not None:
        higher = max(obligor_gross, obligee_gross)
        if higher <= 0:
            similar = "yes" if obligor_gross == obligee_gross else "no"
        else:
            similar = "yes" if abs(obligor_gross - obligee_gross) <= higher * 0.10 else "no"
    costs = [
        tri(support.get("each_pays_half_eligible_childcare")),
        tri(support.get("each_pays_half_uninsured_medical")),
        tri(support.get("each_pays_half_agreed_extracurricular")),
    ]
    cost_sharing = "yes" if all(x == "yes" for x in costs) else "no" if any(x == "no" for x in costs) else "unknown"
    extraordinary = tri(support.get("extraordinary_circumstances"))

    if schedule in {"approximately_equal", "substantially_shared"}:
        if similar == "unknown":
            report.missing_facts.append("Whether gross monthly incomes meet the statutory substantially-similar-income definition")
        if cost_sharing == "unknown":
            report.missing_facts.append("Whether each parent will pay 50 percent of eligible childcare, uninsured medical, and agreed extracurricular costs")
        if extraordinary == "unknown":
            report.missing_facts.append("Whether extraordinary circumstances affect the parenting-schedule deviation analysis")

    deviation_message = None
    deviation_status = "possible_requires_evidence"
    if cost_sharing == "yes" and extraordinary == "no":
        if similar == "yes" and schedule == "approximately_equal":
            deviation_message = "Reported facts match the statutory prerequisites for the rebuttable presumption that a $0 support obligation is appropriate."
        elif similar == "yes" and schedule == "substantially_shared":
            deviation_message = "Reported facts match the statutory prerequisites for a rebuttable presumption that deviation from the guidelines is appropriate."
        elif similar == "no" and schedule in {"approximately_equal", "substantially_shared"}:
            deviation_message = "With dissimilar incomes and a shared/equal schedule, the guideline amount may or may not be appropriate; the lower-earning parent's ability to meet child-rearing costs in a similar or approximately equal style is central."
        elif similar == "no" and schedule == "not_shared_under_statutory_definitions":
            deviation_message = "With dissimilar incomes and no shared/equal schedule, the reported facts align with the rebuttable presumption favoring the guideline calculation."
            deviation_status = "supported_by_reported_facts"
    if deviation_message:
        report.findings.append(Finding(
            finding_id="support_parenting_schedule_deviation",
            title="Parenting-schedule deviation path",
            status=deviation_status,
            explanation=deviation_message,
            severity="information",
            authority_ids=("NH-V0005", "NH-V0006"),
            caveats=("The presumption is rebuttable and must be evaluated in the children's best interests.", "A schedule change does not change the payment amount until the issuing tribunal enters a modified order."),
        ))
    elif schedule in {"approximately_equal", "substantially_shared"}:
        report.findings.append(Finding(
            finding_id="support_parenting_schedule_deviation_missing_preconditions",
            title="Shared-schedule deviation preconditions are incomplete",
            status="possible_requires_evidence",
            explanation="A shared or approximately equal schedule alone does not establish the statutory parenting-schedule presumption; income similarity, specified 50/50 cost sharing, extraordinary circumstances, and best interests still matter.",
            severity="warning",
            authority_ids=("NH-V0006",),
        ))

    report.findings.append(Finding(
        finding_id="support_guideline_presumption",
        title="Guideline calculation remains the starting point",
        status="supported_by_reported_facts",
        explanation="The guideline amount is presumptively correct unless a supported RSA 458-C:5 special circumstance justifies a written deviation finding.",
        authority_ids=("NH-V0005", "NH-V0006"),
    ))
    report.findings.append(Finding(
        finding_id="support_no_automatic_reduction",
        title="Parenting time does not automatically rewrite support",
        status="supported_by_reported_facts",
        explanation="A new schedule and a support modification are separate forms of relief. The existing amount remains enforceable until the issuing tribunal modifies it.",
        severity="warning",
        authority_ids=("NH-V0008", "NH-V0019"),
    ))

    notice_date = parse_date(support.get("notice_of_modification_date"))
    report.findings.append(Finding(
        finding_id="support_prospective_only",
        title="Modification is prospective from statutory notice",
        status="supported_by_reported_facts" if notice_date else "possible_requires_evidence",
        explanation=(f"The reported notice date is {notice_date.isoformat()}; any effective-date argument must be measured against statutory notice requirements." if notice_date else "The notice/service date is missing. The statute bars a child-support modification from becoming effective before notice of the petition to the respondent."),
        severity="warning",
        authority_ids=("NH-V0008", "NH-V0019"),
        evidence_needed=(() if notice_date else ("proof of service or qualifying certified-mail acceptance",)),
    ))

    report.evidence_checklist.extend([
        "Complete signed Uniform Support Order and all later modifications",
        "Guideline worksheet that produced the ordered amount",
        "Current official guideline table and worksheet verified from an official source",
        "Recent pay stubs, tax returns, W-2/1099 records, benefit records, and business records if applicable",
        "Proof of court/admin support actually paid to others",
        "Proof of self-employment taxes, mandatory retirement, state income tax, eligible childcare, and medical-support payments",
        "Ordered annual parenting schedule and neutral actual-time calendar",
        "Invoices and payment proof for childcare, uninsured medical, extraordinary child expenses, and agreed extracurricular costs",
        "Proof of service or acceptance establishing the modification notice date",
    ])
    for item in DEDUCTION_FIELDS:
        report.evidence_checklist.append(f"Adjusted-gross-income review: {item}")
    for item in DEVIATION_FACTORS:
        report.evidence_checklist.append(f"Potential deviation evidence: {item}")
    report.notices.append("Ordinary rent, car payments, consumer debt, and general living expenses are not automatic adjusted-gross-income deductions under the enumerated definition; a claimed hardship must be tied to a recognized deviation theory and evidence.")
    report.notices.append("The engine audits inputs and statutory routes; it does not calculate an enforceable child-support amount or substitute for the current official worksheet/table.")
    return required
