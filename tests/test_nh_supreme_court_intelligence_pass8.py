from legal.nh_supreme_court import NHSupremeCourtIntelligenceExtractor


def test_nh_supreme_court_intelligence_extracts_appellate_signals():
    extractor = NHSupremeCourtIntelligenceExtractor()
    text = (
        "The mother appeals from a post-judgment order concerning parental rights and "
        "responsibilities. We review for abuse of discretion and clear error. "
        "We vacate and remand because the court failed to make findings required by "
        "Rule 52 and did not address the best interest factors. The record includes "
        "no transcript, and the order delegated contact decisions to a therapist."
    )

    brief = extractor.extract_case_brief(text, source_id="source-2025-nh-1", citation="2025 N.H. 1")

    assert brief["procedural_posture"] == "post_judgment_appeal"
    assert brief["standard_of_review"] == "mixed"
    assert brief["disposition"] == "remanded"
    assert "findings_of_fact" in brief["issue_labels"]
    assert "best_interest_factor_gap" in brief["issue_labels"]
    assert "transcript_record_issue" in brief["issue_labels"]
    assert "therapist_non_delegation" in brief["issue_labels"]
    assert "missing or insufficient findings of fact" in brief["red_flags"]
    assert "therapist or third-party delegated contact decision" in brief["red_flags"]


def test_nh_supreme_court_intelligence_extracts_affirmance_and_holding():
    extractor = NHSupremeCourtIntelligenceExtractor()
    text = (
        "The father appeals a final parental rights judgment. "
        "We affirm the judgment because the court made supported best interest findings."
    )

    brief = extractor.extract_case_brief(text, source_id="source-2025-nh-2", citation="2025 N.H. 2")

    assert brief["disposition"] == "affirmed"
    assert brief["holding"].startswith("We affirm")
    assert "parental_rights_responsibilities" in brief["issue_labels"]
