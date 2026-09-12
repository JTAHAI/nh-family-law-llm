from __future__ import annotations

from typing import Any

from .models import Finding, LegalBehaviorReport, RouteRecommendation
from .utils import number, tri

BEST_INTEREST_FACTORS = (
    "relationship with each parent and each parent's nurturing/guidance ability",
    "food, clothing, shelter, medical care, and safe environment",
    "developmental needs now and in the future",
    "school/community adjustment and effect of change",
    "ability and disposition to foster frequent and continuing contact",
    "actual support for the child's contact with the other parent",
    "support for the child's relationship with the other parent",
    "relationships with other significant people",
    "parental communication, cooperation, and joint decision-making ability",
    "evidence of abuse and its impact",
    "incarceration circumstances, if applicable",
    "state policy favoring stable and meaningful involvement and approximately equal time when in the child's best interest",
    "other relevant child-specific factors",
)

GATE_MAP = (
    ("agreement", "I(a)", "The parties agree to the modification.", ("written agreement or on-record agreement",)),
    ("repeated_interference", "I(b)", "Repeated, intentional, and unwarranted interference with the other parent's residential responsibilities is reported.", ("dated parenting-time log", "complete communications", "existing parenting plan", "proof that interference lacked good cause")),
    ("detrimental_environment", "I(c)", "Reported facts may implicate a detrimental present environment and the clear-and-convincing-evidence gate.", ("admissible records showing physical, mental, or emotional detriment", "evidence comparing benefit of change against disruption harm")),
    ("substantially_equal_not_working", "I(d)", "The present allocation is reported to involve substantially equal residential periods and to be unworkable.", ("signed order", "actual schedule calendar", "specific evidence of why the allocation is not working")),
    ("mature_child_preference", "I(e)", "A mature child's preference is reported and may require clear and convincing evidence of maturity and freedom from improper influence.", ("age and maturity facts", "neutral evidence of preference", "facts addressing potential influence")),
    ("minimal_change", "I(f)", "The requested modification is reported as minimal or not changing the allocation of parenting time.", ("redline of current and proposed schedules",)),
    ("travel_change", "I(g)", "The original allocation reportedly depended on travel time that materially changed.", ("prior and current travel times", "school/exchange logistics", "proof the original order relied on travel")),
    ("work_schedule_change", "I(h)", "The original allocation reportedly depended on a work schedule that substantially changed.", ("old and new work schedules", "proof the original order relied on work availability", "proposed school-week logistics")),
    ("young_age_after_five_years", "I(i)", "The original allocation reportedly depended on the child's young age and at least five years have elapsed.", ("order language tying schedule to young age", "order date", "current developmental and school facts")),
)


def analyze_parenting(payload: dict[str, Any], report: LegalBehaviorReport) -> list[str]:
    parenting = payload.get("parenting") or {}
    required_authorities = ["parenting_policy", "parenting_procedure", "parenting_plan", "best_interest", "parenting_modification"]
    permanent = tri(parenting.get("permanent_order"))
    if permanent == "no":
        report.routes.append(RouteRecommendation(
            route_id="establish_parenting_order",
            label="Establish parental rights and responsibilities",
            status="reported_posture_is_establishment",
            explanation="The reported facts do not identify a permanent parenting order, so establishment—not modification—is the starting posture.",
            authority_ids=("NH-V0011", "NH-V0012", "NH-V0015"),
            next_documents=("any existing temporary order", "five-year child residence history", "proposed parenting plan"),
            form_categories_to_verify=("parenting petition or divorce filing", "parenting plan", "UCCJEA/residence-history disclosure"),
        ))
    elif permanent == "unknown":
        report.findings.append(Finding(
            finding_id="parenting_order_status_unknown",
            title="Signed parenting order is required",
            status="blocked_missing_fact",
            explanation="The engine cannot choose an establishment or modification route without the complete signed order and parenting plan.",
            severity="blocker",
            authority_ids=("NH-V0011", "NH-V0017"),
            evidence_needed=("complete signed order", "incorporated parenting plan", "all later modifications"),
        ))
        report.missing_facts.append("Whether a permanent parenting order already exists")
    else:
        report.routes.append(RouteRecommendation(
            route_id="modify_parental_rights",
            label="Review modification of parental rights and responsibilities",
            status="statutory_gate_required",
            explanation="A material parenting-time change requires a reported-fact path through RSA 461-A:11 plus a best-interest record; the equal-parenting policy does not erase the modification gate.",
            authority_ids=("NH-V0010", "NH-V0015", "NH-V0017"),
            next_documents=("complete signed order", "current and proposed parenting schedules", "evidence supporting at least one RSA 461-A:11 gate"),
            form_categories_to_verify=("motion to modify parental rights and responsibilities", "proposed parenting plan"),
        ))

    request_scope = str(parenting.get("requested_change_scope") or "unknown").strip().casefold()
    if request_scope in {"major", "substantial", "eow_to_equal", "equal_parenting"}:
        report.findings.append(Finding(
            finding_id="major_schedule_change",
            title="Requested schedule change is not treated as minimal",
            status="supported_by_reported_facts",
            explanation="A reported move from limited parenting time to approximately equal time is analyzed as a major allocation change, not the minimal-change gate.",
            severity="warning",
            authority_ids=("NH-V0017",),
            caveats=("The court—not this tool—determines how the request fits the statute.",),
        ))
        parenting = dict(parenting)
        parenting["minimal_change"] = False

    gate_yes = 0
    gate_unknown = 0
    for field, paragraph, explanation, evidence in GATE_MAP:
        value = tri(parenting.get(field))
        if field == "young_age_after_five_years":
            if value == "unknown":
                based_on_age = tri(parenting.get("order_based_on_young_age"))
                elapsed = number(parenting.get("years_since_order"))
                if based_on_age == "yes" and elapsed is not None:
                    value = "yes" if elapsed >= 5 else "no"
        if value == "yes":
            gate_yes += 1
            report.findings.append(Finding(
                finding_id=f"parenting_gate_{field}",
                title=f"Possible RSA 461-A:11 {paragraph} gate",
                status="supported_by_reported_facts",
                explanation=explanation,
                severity="information",
                authority_ids=("NH-V0017",),
                evidence_needed=evidence,
                caveats=("This is issue spotting, not a prediction that the court will find the statutory standard met.",),
            ))
        elif value == "unknown":
            gate_unknown += 1
    if permanent == "yes" and gate_yes == 0:
        report.findings.append(Finding(
            finding_id="no_parenting_modification_gate_identified",
            title="No modification gate is established by the supplied facts",
            status="possible_requires_evidence" if gate_unknown else "not_supported_by_reported_facts",
            explanation="Approximately equal parenting is a state policy and best-interest consideration, but a permanent-order modification still requires a route recognized by RSA 461-A:11.",
            severity="blocker" if gate_unknown == 0 else "warning",
            authority_ids=("NH-V0010", "NH-V0017"),
            evidence_needed=("facts tied to one or more statutory modification gates",),
        ))

    if tri(parenting.get("decision_making_change")) == "yes":
        required_authorities.append("decision_making")
        report.findings.append(Finding(
            finding_id="decision_making_separate_review",
            title="Decision-making responsibility requires separate analysis",
            status="possible_requires_evidence",
            explanation="A request to change decision-making responsibility is not interchangeable with a schedule change and must be reviewed under the decision-making provisions, including abuse-related safeguards.",
            severity="warning",
            authority_ids=("NH-V0014", "NH-V0017"),
            evidence_needed=("current decision-making order", "specific decision categories at issue", "communication/cooperation evidence", "any abuse findings or allegations"),
        ))

    if tri(parenting.get("relocation")) == "yes":
        required_authorities.append("relocation")
        report.routes.append(RouteRecommendation(
            route_id="relocation_review",
            label="Separate relocation review",
            status="separate_statutory_route",
            explanation="A relocation request follows RSA 461-A:12 and should not be collapsed into the ordinary modification-gate analysis.",
            authority_ids=("NH-V0018",),
            next_documents=("current residence and school district", "proposed address area", "notice given or proposed", "safety basis if shorter notice is claimed"),
            form_categories_to_verify=("relocation request/objection filing", "proposed parenting plan"),
        ))

    if tri(parenting.get("denied_or_interfered_parenting_time")) == "yes":
        required_authorities.append("family_access")
        report.routes.append(RouteRecommendation(
            route_id="family_access_enforcement",
            label="Review family-access enforcement separately",
            status="possible_enforcement_route",
            explanation="Substantial and material noncompliance with an approved parenting plan may support a family access motion; enforcement and modification should not be silently merged.",
            authority_ids=("NH-V0013",),
            next_documents=("signed parenting plan", "specific dates and provisions violated", "complete communications", "proof of good-cause explanations offered"),
            form_categories_to_verify=("family access motion",),
        ))

    report.evidence_checklist.extend([
        "Complete signed parenting order and incorporated parenting plan",
        "Neutral calendar comparing ordered and actual parenting time",
        "Detailed proposed school-week, holiday, vacation, transportation, and exchange schedule",
        "Housing, work-schedule, school, childcare, transportation, and medical logistics",
        "Historical caregiving and participation in school, medical, and activity decisions",
        "Complete communications showing cooperation, proposed solutions, or documented interference",
        "Child-specific evidence addressing each material best-interest factor",
    ])
    report.notices.append("The best-interest analysis is child-specific; it is not a parent popularity or financial-resources contest.")
    report.notices.append("Approximately equal parenting is encouraged when in the child's best interest, but it is not an automatic outcome and does not automatically modify child support.")
    for factor in BEST_INTEREST_FACTORS:
        report.evidence_checklist.append(f"Best-interest evidence: {factor}")
    return required_authorities
