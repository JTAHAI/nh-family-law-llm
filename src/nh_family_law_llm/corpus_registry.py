"""Auditable source registry for the New Hampshire Family Law LLM.

The registry identifies the official sources that the external corpus builder must
acquire and review.  A registry entry is not, by itself, proof that the text is
current.  Raw snapshots, checksums, effective-date review, and promotion into the
CURRENT_AUTHORITY lane are separate release gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .source_manifest import SourceManifestEntry, validate_manifest

RETRIEVED_AT = "2026-09-11T00:00:00Z"


@dataclass(frozen=True)
class CorpusRequirement:
    id: str
    title: str
    source_type: str
    jurisdiction: str
    official: bool
    url: str
    effective_date: str
    version_label: str
    citation_hint: str
    source_priority: int
    authority_class: str
    corpus_lane: str
    parser: str
    citation_aliases: tuple[str, ...] = ()
    notes: str = ""
    required_for_ga: bool = True

    def to_manifest_entry(self) -> SourceManifestEntry:
        return SourceManifestEntry(
            id=self.id,
            title=self.title,
            source_type=self.source_type,
            jurisdiction=self.jurisdiction,
            official=self.official,
            url=self.url,
            effective_date=self.effective_date,
            retrieved_at=RETRIEVED_AT,
            version_label=self.version_label,
            citation_hint=self.citation_hint,
            license_or_terms_note=(
                "Official public legal source. Preserve the source URL, retrieval timestamp, "
                "checksum, and effective-date review before user-facing retrieval."
            ),
            source_priority=self.source_priority,
            notes=self.notes,
            authority_class=self.authority_class,
            corpus_lane=self.corpus_lane,
            citation_aliases=self.citation_aliases,
            parser=self.parser,
            freshness_status="needs_live_fetch_and_review",
            required_for_ga=self.required_for_ga,
            completion_status="manifested",
        )


def _r(
    id: str,
    title: str,
    source_type: str,
    jurisdiction: str,
    url: str,
    citation_hint: str,
    source_priority: int,
    authority_class: str,
    corpus_lane: str,
    parser: str,
    *,
    effective_date: str = "verify-from-official-source",
    version_label: str = "manifested; live official snapshot and legal review required",
    citation_aliases: Iterable[str] = (),
    notes: str = "",
    official: bool = True,
    required_for_ga: bool = True,
) -> CorpusRequirement:
    return CorpusRequirement(
        id=id,
        title=title,
        source_type=source_type,
        jurisdiction=jurisdiction,
        official=official,
        url=url,
        effective_date=effective_date,
        version_label=version_label,
        citation_hint=citation_hint,
        source_priority=source_priority,
        authority_class=authority_class,
        corpus_lane=corpus_lane,
        parser=parser,
        citation_aliases=tuple(citation_aliases),
        notes=notes,
        required_for_ga=required_for_ga,
    )


def _rsa(chapter: str, title_roman: str, title: str, *, priority: int = 10, aliases: Iterable[str] = ()) -> CorpusRequirement:
    return _r(
        f"nh-rsa-{chapter.lower()}",
        title,
        "statute",
        "New Hampshire",
        f"https://gc.nh.gov/rsa/html/{title_roman}/{chapter}/{chapter}-mrg.htm",
        f"RSA {chapter}",
        priority,
        "official_nh_statute",
        "nh_primary_and_related_statutes",
        "nh_general_court_chapter_index",
        citation_aliases=(f"RSA {chapter}", *tuple(aliases)),
        notes="Chapter-level acquisition target; expand into section-level records with source spans.",
    )


FULL_CORPUS_REQUIREMENTS: tuple[CorpusRequirement, ...] = (
    # Core and overlapping New Hampshire statutes.
    _rsa("21-M", "I", "RSA 21-M Department of Justice and related family-safety overlap", priority=24),
    _rsa("126-A", "X", "RSA 126-A Department of Health and Human Services", priority=18),
    _rsa("132", "X", "RSA 132 maternity, parentage, and birth-related provisions", priority=23),
    _rsa("135-C", "X", "RSA 135-C mental-health services and minor/parent overlap", priority=25),
    _rsa("141-C", "X", "RSA 141-C communicable-disease and minor/parent overlap", priority=30),
    _rsa("161-B", "XII", "RSA 161-B child-support services", priority=8, aliases=("BCSS", "DCSS", "Title IV-D")),
    _rsa("161-C", "XII", "RSA 161-C administrative support enforcement", priority=7, aliases=("administrative support order",)),
    _rsa("167", "XII", "RSA 167 public assistance and family-support cooperation", priority=21),
    _rsa("169-B", "XII", "RSA 169-B delinquent children", priority=20),
    _rsa("169-C", "XII", "RSA 169-C child protection act", priority=9, aliases=("abuse", "neglect", "DCYF")),
    _rsa("169-D", "XII", "RSA 169-D children in need of services", priority=19),
    _rsa("170-A", "XII", "RSA 170-A interstate compact on placement of children", priority=18, aliases=("ICPC",)),
    _rsa("170-B", "XII", "RSA 170-B adoption", priority=12),
    _rsa("170-C", "XII", "RSA 170-C termination of parental rights", priority=11, aliases=("TPR",)),
    _rsa("173-B", "XII", "RSA 173-B protection of persons from domestic violence", priority=6, aliases=("protective order", "domestic violence")),
    _rsa("457", "XLIII", "RSA 457 marriages", priority=14),
    _rsa("457-A", "XLIII", "RSA 457-A civil unions", priority=18),
    _rsa("458", "XLIII", "RSA 458 annulment, divorce, and separation", priority=4, aliases=("divorce", "alimony", "property division")),
    _rsa("458-A", "XLIII", "RSA 458-A Uniform Child Custody Jurisdiction and Enforcement Act", priority=5, aliases=("UCCJEA",)),
    _rsa("458-B", "XLIII", "RSA 458-B income assignment", priority=6, aliases=("income withholding",)),
    _rsa("458-C", "XLIII", "RSA 458-C child support guidelines", priority=3, aliases=("child support", "guidelines", "deviation")),
    _rsa("458-D", "XLIII", "RSA 458-D parental-rights and child-support impact seminars", priority=16),
    _rsa("458-E", "XLIII", "RSA 458-E Military Parents' Rights Act", priority=13, aliases=("military parent",)),
    _rsa("459", "XLIII", "RSA 459 Uniform Divorce Recognition Law", priority=24),
    _rsa("460", "XLIII", "RSA 460 spouses and marital rights", priority=23),
    _rsa("461", "XLIII", "RSA 461 adoption and related provisions", priority=20),
    _rsa("461-A", "XLIII", "RSA 461-A parental rights and responsibilities", priority=2, aliases=("parenting plan", "residential responsibility", "parenting schedule")),
    _rsa("461-B", "XLIII", "RSA 461-B emancipation", priority=14),
    _rsa("463", "XLIII", "RSA 463 guardianship of minors", priority=10),
    _rsa("464-A", "XLIII", "RSA 464-A guardians and conservators", priority=17),
    _rsa("490-C", "LI", "RSA 490-C Guardian ad Litem Board", priority=17, aliases=("GAL",)),
    _rsa("490-D", "LI", "RSA 490-D Judicial Branch Family Division", priority=8, aliases=("Family Division jurisdiction",)),
    _rsa("546-B", "LIII", "RSA 546-B Uniform Interstate Family Support Act", priority=5, aliases=("UIFSA",)),

    # New Hampshire court rules, forms, opinions, and official guidance.
    _r(
        "nh-family-division-rules",
        "New Hampshire Circuit Court Family Division Rules",
        "court_rule",
        "New Hampshire",
        "https://www.courts.nh.gov/rules-comment/rules-circuit-court-state-new-hampshire-family-division",
        "N.H. R. Cir. Ct. Fam. Div.",
        4,
        "official_nh_family_division_rule",
        "nh_court_rules",
        "nh_rules_index",
        citation_aliases=("Family Division Rules", "N.H. Circuit Court Family Division Rules"),
    ),
    _r(
        "nh-rules-evidence",
        "New Hampshire Rules of Evidence",
        "evidence_rule",
        "New Hampshire",
        "https://www.courts.nh.gov/rules-comment/new-hampshire-rules-evidence",
        "N.H. R. Evid.",
        12,
        "official_nh_evidence_rule",
        "nh_court_rules",
        "nh_rules_index",
    ),
    _r(
        "nh-supreme-court-rules",
        "Rules of the Supreme Court of New Hampshire",
        "appellate_rule",
        "New Hampshire",
        "https://www.courts.nh.gov/rules-comment/supreme-court-rules",
        "N.H. Sup. Ct. R.",
        11,
        "official_nh_appellate_rule",
        "nh_court_rules",
        "nh_rules_index",
        citation_aliases=("appeal", "motion for reconsideration"),
    ),
    _r(
        "nh-court-records-rules",
        "New Hampshire Judicial Branch court-record access and confidentiality rules",
        "court_rule",
        "New Hampshire",
        "https://www.courts.nh.gov/rules-comment",
        "N.H. Ct. R.",
        16,
        "official_nh_court_records_rule",
        "nh_court_rules",
        "nh_rules_index",
        citation_aliases=("court records", "confidentiality", "redaction"),
    ),
    _r(
        "nh-rules-civil-procedure",
        "New Hampshire Rules of Civil Procedure",
        "court_rule",
        "New Hampshire",
        "https://www.courts.nh.gov/rules-comment/new-hampshire-rules-civil-procedure",
        "N.H. R. Civ. P.",
        14,
        "official_nh_civil_rule",
        "nh_court_rules",
        "nh_rules_index",
    ),
    _r(
        "nh-guardian-ad-litem-authorities",
        "New Hampshire Guardian ad Litem Board authorities and standards",
        "attorney_regulation",
        "New Hampshire",
        "https://www.courts.nh.gov/committees/guardian-ad-litem-board",
        "N.H. GAL Board Rules",
        17,
        "official_nh_gal_rule",
        "nh_gal_and_professional_standards",
        "html_guidance_parser",
        citation_aliases=("guardian ad litem", "GAL"),
    ),
    _r(
        "nh-professional-conduct-rules",
        "New Hampshire Rules of Professional Conduct",
        "professional_conduct_rule",
        "New Hampshire",
        "https://www.courts.nh.gov/rules-comment/supreme-court-rules",
        "N.H. R. Prof. Conduct",
        35,
        "official_nh_professional_conduct",
        "nh_ethics_and_regulation",
        "nh_rules_index",
    ),
    _r(
        "nh-family-division-forms",
        "New Hampshire Circuit Court Family Division forms",
        "court_form",
        "New Hampshire",
        "https://www.courts.nh.gov/our-courts/circuit-court/family-division/forms",
        "NHJB Family Division forms",
        13,
        "official_nh_form",
        "nh_forms_and_instructions",
        "nh_forms_index",
        citation_aliases=("NHJB", "petition", "motion to modify", "uniform support order"),
    ),
    _r(
        "nh-judicial-branch-self-help",
        "New Hampshire Judicial Branch Self-Help Center",
        "judicial_branch_guide",
        "New Hampshire",
        "https://www.courts.nh.gov/self-help",
        "NH Judicial Branch Self-Help Center",
        42,
        "official_nh_public_guidance",
        "nh_self_help_and_procedure",
        "html_guidance_parser",
    ),
    _r(
        "nh-court-mediation",
        "New Hampshire Judicial Branch mediation information",
        "judicial_branch_guide",
        "New Hampshire",
        "https://www.courts.nh.gov/resources/mediation",
        "NH Judicial Branch mediation guidance",
        43,
        "official_nh_public_guidance",
        "nh_self_help_and_procedure",
        "html_guidance_parser",
        citation_aliases=("mediation", "ADR"),
        required_for_ga=False,
    ),
    _r(
        "nh-supreme-court-opinions-index",
        "Supreme Court of New Hampshire orders and opinions",
        "supreme_court_opinion_index",
        "New Hampshire",
        "https://www.courts.nh.gov/our-courts/supreme-court/orders-and-opinions",
        "N.H. Supreme Court opinions",
        7,
        "nh_supreme_court_opinion",
        "nh_case_law",
        "nh_supreme_court_opinion_index",
        citation_aliases=("N.H.", "New Hampshire Supreme Court"),
    ),
    _r(
        "nh-general-court-rsa-index",
        "New Hampshire Revised Statutes Online index and currentness notice",
        "judicial_branch_guide",
        "New Hampshire",
        "https://gc.nh.gov/rsa/html/indexes/default.aspx",
        "New Hampshire Revised Statutes Online",
        9,
        "official_nh_statute_index",
        "nh_primary_and_related_statutes",
        "html_guidance_parser",
        citation_aliases=("RSA index", "List of Sections Affected"),
    ),
    _r(
        "nh-session-laws-and-bills",
        "New Hampshire General Court legislation and session-law index",
        "rulemaking_notice",
        "New Hampshire",
        "https://gc.nh.gov/legislation/",
        "N.H. Laws",
        15,
        "official_nh_session_law",
        "nh_legislative_history_and_updates",
        "html_guidance_parser",
    ),

    # Administrative implementation and support-service sources.
    _r(
        "nh-admin-rules-index",
        "New Hampshire administrative rules index",
        "admin_order",
        "New Hampshire",
        "https://gc.nh.gov/rules/",
        "N.H. Admin. R.",
        18,
        "official_nh_administrative_rule_index",
        "nh_administrative_rules",
        "html_guidance_parser",
    ),
    _r(
        "nh-admin-rules-he-w",
        "New Hampshire DHHS He-W rules",
        "court_rule",
        "New Hampshire",
        "https://gc.nh.gov/rules/state_agencies/he-w.html",
        "N.H. Admin. R. He-W",
        14,
        "official_nh_administrative_rule",
        "nh_administrative_rules",
        "nh_rules_index",
        citation_aliases=("child support services", "public assistance"),
    ),
    _r(
        "nh-admin-rules-he-c",
        "New Hampshire DHHS He-C rules",
        "court_rule",
        "New Hampshire",
        "https://gc.nh.gov/rules/state_agencies/he-c.html",
        "N.H. Admin. R. He-C",
        17,
        "official_nh_administrative_rule",
        "nh_administrative_rules",
        "nh_rules_index",
        citation_aliases=("child care", "child protection"),
    ),
    _r(
        "nh-bcss-child-support-services",
        "New Hampshire Bureau of Child Support Services official information",
        "child_support_guidance",
        "New Hampshire",
        "https://www.dhhs.nh.gov/programs-services/childcare-parenting-childbirth/child-support-services",
        "NH DHHS BCSS guidance",
        25,
        "official_nh_agency_guidance",
        "nh_child_support_administration",
        "html_guidance_parser",
        citation_aliases=("BCSS", "DCSS", "child support services"),
    ),

    # Federal overlay directly relevant to state family-law matters and federal procedure.
    _r(
        "district-nh-local-rules",
        "U.S. District Court for the District of New Hampshire Local Rules",
        "federal_court_rule",
        "Federal - District of New Hampshire",
        "https://www.nhd.uscourts.gov/local-rules-0",
        "D.N.H. Local Rules",
        21,
        "official_federal_district_nh_local_rules",
        "federal_nh_intake_and_relief",
        "federal_rules_index_parser",
    ),
    _r(
        "district-nh-pro-se-guidance",
        "U.S. District Court for the District of New Hampshire pro se information",
        "federal_court_guide",
        "Federal - District of New Hampshire",
        "https://www.nhd.uscourts.gov/local-and-federal-rules",
        "D.N.H. pro se guidance",
        45,
        "official_federal_district_nh_pro_se_guidance",
        "federal_nh_intake_and_relief",
        "html_guidance_parser",
        required_for_ga=False,
    ),
    _r(
        "district-nh-rules-orders",
        "U.S. District Court for the District of New Hampshire rules and orders",
        "federal_court_rule",
        "Federal - District of New Hampshire",
        "https://www.nhd.uscourts.gov/court-info/local-rules-and-orders",
        "D.N.H. Rules and Orders",
        22,
        "official_federal_district_nh_local_rules",
        "federal_nh_intake_and_relief",
        "federal_rules_index_parser",
    ),
    _r(
        "first-circuit-opinions-index",
        "United States Court of Appeals for the First Circuit opinions",
        "first_circuit_opinion",
        "Federal - First Circuit",
        "https://www.ca1.uscourts.gov/opinions",
        "1st Cir. opinions",
        20,
        "first_circuit_binding",
        "federal_binding_case_law",
        "first_circuit_opinion_index_parser",
    ),
    _r(
        "supreme-court-opinions-index",
        "Supreme Court of the United States opinions",
        "us_supreme_court_opinion",
        "Federal - U.S. Supreme Court",
        "https://www.supremecourt.gov/opinions/opinions.aspx",
        "U.S. Supreme Court opinions",
        5,
        "us_supreme_court_binding",
        "federal_binding_case_law",
        "supreme_court_opinion_index_parser",
    ),
    _r(
        "federal-rules-current-index",
        "U.S. Courts current rules of practice and procedure",
        "federal_rule",
        "United States",
        "https://www.uscourts.gov/forms-rules/current-rules-practice-procedure",
        "Federal Rules of Practice and Procedure",
        6,
        "federal_rules_primary",
        "federal_rules_and_statutes",
        "federal_rules_index_parser",
    ),
    _r(
        "uscode-28-1915-ifp",
        "28 U.S.C. section 1915 proceedings in forma pauperis",
        "federal_statute",
        "United States",
        "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1915&num=0&edition=prelim",
        "28 U.S.C. § 1915",
        6,
        "federal_statute_primary",
        "federal_rules_and_statutes",
        "uscode_section_parser",
        citation_aliases=("IFP", "in forma pauperis"),
    ),
    _r(
        "uscode-28-1738a-pkpa",
        "28 U.S.C. section 1738A full faith and credit for child-custody determinations",
        "federal_statute",
        "United States",
        "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1738A&num=0&edition=prelim",
        "28 U.S.C. § 1738A",
        6,
        "federal_statute_primary",
        "federal_family_law_overlay",
        "uscode_section_parser",
        citation_aliases=("PKPA",),
    ),
    _r(
        "uscode-28-1738b-ffccsoa",
        "28 U.S.C. section 1738B full faith and credit for child-support orders",
        "federal_statute",
        "United States",
        "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1738B&num=0&edition=prelim",
        "28 U.S.C. § 1738B",
        6,
        "federal_statute_primary",
        "federal_family_law_overlay",
        "uscode_section_parser",
        citation_aliases=("FFCCSOA",),
    ),
)


AUTHORITY_RANKING = (
    "us_supreme_court_binding",
    "constitutional_authority",
    "federal_statute_primary",
    "federal_rules_primary",
    "first_circuit_binding",
    "official_nh_statute",
    "nh_supreme_court_opinion",
    "official_nh_family_division_rule",
    "official_nh_evidence_rule",
    "official_nh_appellate_rule",
    "official_nh_civil_rule",
    "official_nh_administrative_rule",
    "official_standing_order",
    "official_nh_form",
    "official_nh_agency_guidance",
    "official_nh_public_guidance",
    "official_federal_district_nh_local_rules",
    "official_federal_district_nh_pro_se_guidance",
    "legal_aid_plain_language",
    "licensed_secondary",
)

REQUIRED_INDEXES = (
    "exact_citation_index",
    "statute_section_lookup",
    "rule_lookup",
    "case_name_lookup",
    "case_citation_lookup",
    "form_id_lookup",
    "bm25_lexical_index",
    "vector_index_optional",
    "hybrid_retrieval_index",
    "source_card_index",
    "authority_graph",
    "freshness_index",
)

REQUIRED_ATTORNEY_REVIEWED_EVALS = {
    "nh_rag_retrieval_gold.jsonl": 500,
    "nh_citation_validity_gold.jsonl": 500,
    "nh_quote_span_gold.jsonl": 500,
    "nh_hallucination_negative_cases.jsonl": 250,
    "nh_forms_freshness_gold.jsonl": 100,
    "nh_drafting_review_gold.jsonl": 100,
    "nh_issue_classification_gold.jsonl": 250,
    "nh_posture_classification_gold.jsonl": 150,
    "nh_authority_ranking_gold.jsonl": 250,
    "nh_fact_to_evidence_gold.jsonl": 250,
    "nh_supreme_court_holding_gold.jsonl": 150,
    "nh_findings_gap_gold.jsonl": 100,
    "federal_nh_intake_relief_gold.jsonl": 150,
    "federal_jurisdiction_blockers_gold.jsonl": 150,
}

FEDERAL_JURISDICTION_WARNINGS = (
    "domestic_relations_exception",
    "rooker_feldman",
    "younger_abstention",
    "anti_injunction_act",
    "sovereign_immunity",
    "judicial_immunity",
    "quasi_judicial_immunity",
    "qualified_immunity",
    "claim_preclusion",
    "issue_preclusion",
    "ifp_screening",
    "service_defect",
)


def full_corpus_manifest_entries() -> list[SourceManifestEntry]:
    return validate_manifest([requirement.to_manifest_entry() for requirement in FULL_CORPUS_REQUIREMENTS])


def corpus_summary() -> dict[str, object]:
    entries = full_corpus_manifest_entries()
    lanes = sorted({entry.corpus_lane for entry in entries})
    authority_classes = sorted({entry.authority_class for entry in entries})
    return {
        "schema": "nh_family_law_llm.full_corpus_registry.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "registry_ready_review_pending",
        "source_count": len(entries),
        "required_for_ga_count": sum(1 for entry in entries if entry.required_for_ga),
        "lanes": lanes,
        "authority_classes": authority_classes,
        "required_indexes": list(REQUIRED_INDEXES),
        "attorney_reviewed_eval_minimums": dict(REQUIRED_ATTORNEY_REVIEWED_EVALS),
        "federal_jurisdiction_warnings": list(FEDERAL_JURISDICTION_WARNINGS),
        "currentness_notice": (
            "Manifest inclusion does not make a source current or retrieval eligible. "
            "Official snapshot acquisition, checksum capture, effective-date review, and promotion are required."
        ),
    }
