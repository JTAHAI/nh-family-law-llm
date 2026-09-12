from __future__ import annotations

from typing import Any

from .models import LegalBehaviorReport

BASE_FORM_CATEGORIES = {
    "parenting_modification": ("motion to modify parental rights and responsibilities", "proposed parenting plan"),
    "parenting_enforcement": ("family access motion",),
    "child_support_modification": ("child-support modification filing", "current child-support guidelines worksheet", "Uniform Support Order", "financial affidavit"),
    "administrative_support": ("DHHS administrative hearing/modification materials",),
    "uccjea": ("UCCJEA child-residence/proceeding disclosure",),
    "uifsa": ("UIFSA registration/enforcement/modification filing",),
    "relocation": ("relocation request or objection", "proposed parenting plan"),
    "decision_making": ("motion addressing decision-making responsibility", "proposed parenting plan"),
}


def select_form_categories(issues: list[str], payload: dict[str, Any], report: LegalBehaviorReport) -> None:
    for issue in issues:
        report.form_categories_to_verify.extend(BASE_FORM_CATEGORIES.get(issue, ()))
    report.form_categories_to_verify.extend(
        category
        for route in report.routes
        for category in route.form_categories_to_verify
    )
    report.notices.append("Form names are categories until the live NH Judicial Branch form catalog, revision date, and filing instructions are verified. This engine does not invent NHJB form numbers.")
