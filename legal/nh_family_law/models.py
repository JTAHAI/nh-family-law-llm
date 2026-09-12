from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

FindingStatus = Literal[
    "supported_by_reported_facts",
    "possible_requires_evidence",
    "not_supported_by_reported_facts",
    "not_applicable",
    "blocked_missing_authority",
    "blocked_missing_fact",
]
Severity = Literal["information", "warning", "blocker"]


@dataclass(frozen=True, slots=True)
class AuthorityReference:
    authority_id: str
    citation: str
    title: str
    source_url: str
    status: str = "current_verified"
    retrieval_eligible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Finding:
    finding_id: str
    title: str
    status: FindingStatus
    explanation: str
    severity: Severity = "information"
    authority_ids: tuple[str, ...] = ()
    evidence_needed: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["authority_ids"] = list(self.authority_ids)
        payload["evidence_needed"] = list(self.evidence_needed)
        payload["caveats"] = list(self.caveats)
        return payload


@dataclass(frozen=True, slots=True)
class RouteRecommendation:
    route_id: str
    label: str
    status: str
    explanation: str
    authority_ids: tuple[str, ...] = ()
    next_documents: tuple[str, ...] = ()
    form_categories_to_verify: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["authority_ids"] = list(self.authority_ids)
        payload["next_documents"] = list(self.next_documents)
        payload["form_categories_to_verify"] = list(self.form_categories_to_verify)
        return payload


@dataclass(slots=True)
class LegalBehaviorReport:
    as_of_date: str
    issues: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    routes: list[RouteRecommendation] = field(default_factory=list)
    authority_references: list[AuthorityReference] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    evidence_checklist: list[str] = field(default_factory=list)
    form_categories_to_verify: list[str] = field(default_factory=list)
    drafting_controls: list[str] = field(default_factory=list)
    authority_gaps: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    review_required: bool = True
    filing_ready: bool = False
    legal_advice: bool = False
    existing_order_remains_in_effect: bool = True

    def add_authorities(self, refs: list[AuthorityReference]) -> None:
        existing = {row.authority_id for row in self.authority_references}
        for ref in refs:
            if ref.authority_id not in existing:
                self.authority_references.append(ref)
                existing.add(ref.authority_id)

    def deduplicate(self) -> None:
        self.issues = list(dict.fromkeys(self.issues))
        self.missing_facts = list(dict.fromkeys(self.missing_facts))
        self.evidence_checklist = list(dict.fromkeys(self.evidence_checklist))
        self.form_categories_to_verify = list(dict.fromkeys(self.form_categories_to_verify))
        self.drafting_controls = list(dict.fromkeys(self.drafting_controls))
        self.authority_gaps = list(dict.fromkeys(self.authority_gaps))
        self.notices = list(dict.fromkeys(self.notices))
        finding_keys: set[tuple[str, str]] = set()
        deduped_findings: list[Finding] = []
        for finding in self.findings:
            key = (finding.finding_id, finding.status)
            if key not in finding_keys:
                deduped_findings.append(finding)
                finding_keys.add(key)
        self.findings = deduped_findings
        route_ids: set[str] = set()
        deduped_routes: list[RouteRecommendation] = []
        for route in self.routes:
            if route.route_id not in route_ids:
                deduped_routes.append(route)
                route_ids.add(route.route_id)
        self.routes = deduped_routes

    def to_dict(self) -> dict[str, Any]:
        self.deduplicate()
        blocker_count = sum(row.severity == "blocker" for row in self.findings)
        warning_count = sum(row.severity == "warning" for row in self.findings)
        status = "blocked" if blocker_count or self.authority_gaps else "review_required"
        return {
            "schema": "nh_family_law_llm.legal_behavior_report.v1",
            "status": status,
            "summary": {
                "blocker_count": blocker_count,
                "warning_count": warning_count,
                "authority_gap_count": len(self.authority_gaps),
                "issue_count": len(self.issues),
                "route_count": len(self.routes),
            },
            "as_of_date": self.as_of_date,
            "issues": self.issues,
            "findings": [row.to_dict() for row in self.findings],
            "routes": [row.to_dict() for row in self.routes],
            "authority_references": [row.to_dict() for row in self.authority_references],
            "missing_facts": self.missing_facts,
            "evidence_checklist": self.evidence_checklist,
            "form_categories_to_verify": self.form_categories_to_verify,
            "drafting_controls": self.drafting_controls,
            "authority_gaps": self.authority_gaps,
            "notices": self.notices,
            "review_required": self.review_required,
            "filing_ready": self.filing_ready,
            "legal_advice": self.legal_advice,
            "existing_order_remains_in_effect": self.existing_order_remains_in_effect,
        }
