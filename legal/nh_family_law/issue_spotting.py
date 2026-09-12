from __future__ import annotations

from dataclasses import dataclass

from .utils import clean_text


@dataclass(frozen=True, slots=True)
class IssueRule:
    issue: str
    phrases: tuple[str, ...]


RULES: tuple[IssueRule, ...] = (
    IssueRule("parenting_modification", ("50/50", "50-50", "half the week", "equal parenting", "modify parenting", "custody modification", "change custody", "parenting time")),
    IssueRule("parenting_plan", ("parenting plan", "holiday schedule", "school week", "exchange", "transportation")),
    IssueRule("decision_making", ("decision-making", "decision making", "medical decisions", "school decisions", "legal custody")),
    IssueRule(
        "parenting_enforcement",
        (
            "denied parenting time",
            "parenting time was denied",
            "withholding the child",
            "interference",
            "family access",
            "not following the parenting plan",
            "parenting plan was not followed",
        ),
    ),
    IssueRule("relocation", ("relocate", "relocation", "move away", "moving out of")),
    IssueRule("child_support_modification", ("lower support", "reduce support", "modify child support", "child support", "support amount", "support worksheet")),
    IssueRule("administrative_support", ("dhhs", "bcss", "dcss", "administrative support", "administrative order", "income withholding")),
    IssueRule("uccjea", ("uccjea", "home state", "custody order from another state", "parenting order from another state", "child moved to new hampshire")),
    IssueRule("uifsa", ("uifsa", "support order from another state", "interstate support", "register support order")),
    IssueRule("safety", ("abuse", "domestic violence", "threat", "unsafe", "emergency", "pfa", "protection order")),
    IssueRule("self_representation", ("pro se", "self represented", "self-represented", "without a lawyer", "forms")),
)


def spot_issues(question: str, payload: dict) -> list[str]:
    text = clean_text(question).casefold()
    issues: list[str] = []
    for rule in RULES:
        if any(phrase in text for phrase in rule.phrases):
            issues.append(rule.issue)
    if "parenting" in payload and payload.get("parenting") is not None:
        issues.append("parenting_modification")
    if "support" in payload and payload.get("support") is not None:
        issues.append("child_support_modification")
    if "support_order" in payload and payload.get("support_order") is not None:
        issues.append("administrative_support")
    interstate = payload.get("interstate") or {}
    if interstate:
        parenting_fields = {
            "parenting_order_state",
            "child_present_in_nh",
            "mistreatment_abuse_or_abandonment_emergency",
            "proceeding_pending_elsewhere",
            "child_residence_history",
        }
        if parenting_fields.intersection(interstate):
            issues.append("uccjea")
        if interstate.get("support_order_state"):
            issues.append("uifsa")
    if payload.get("safety"):
        issues.append("safety")
    return list(dict.fromkeys(issues)) or ["general_nh_family_law"]
