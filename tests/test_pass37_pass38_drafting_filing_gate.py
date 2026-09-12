"""Shared fictional filing-gate fixtures for migrated NH regression tests.

The original New Hampshire test module was removed with the New Hampshire authority corpus, but
several jurisdiction-neutral regression tests import ``_complete_payload``.
This compatibility fixture contains no executable test cases and no New Hampshire law.
"""

from __future__ import annotations

__test__ = False


def _authority() -> dict:
    return {
        "source_id": "rsa-461-a-6",
        "citation": "RSA 461-A:6",
        "title": "Best-interest factors",
        "jurisdiction": "nh",
        "authority_status": "verified_official_nh",
        "freshness_status": "fresh",
        "score": 1.0,
    }


def _complete_payload() -> dict:
    return {
        "review_required": True,
        "human_review_complete": True,
        "privacy_review_complete": True,
        "authority_matrix": [_authority()],
        "citation_report": [
            {"citation": "RSA 461-A:6", "source_id": "rsa-461-a-6", "status": "resolved"}
        ],
        "quote_report": [
            {
                "quoted_text": "best interests of the child",
                "source_id": "rsa-461-a-6",
                "match_type": "exact",
                "start_offset": 10,
                "end_offset": 37,
            }
        ],
        "claim_support_report": {
            "claims": [
                {
                    "claim_id": "claim-1",
                    "claim": "The court evaluates the child's best interests.",
                    "support_status": "supported",
                    "source_id": "rsa-461-a-6",
                }
            ]
        },
        "fact_to_evidence_map": [
            {
                "fact_id": "fact-1",
                "fact": "The child changed schools on 01/03/2026.",
                "source_document_id": "doc-1",
                "span": {"start_offset": 0, "end_offset": 43},
                "confidence": 0.91,
            }
        ],
        "procedure_posture_report": {"status": "checked", "procedural_posture": "post_judgment"},
        "forms_report": {"status": "checked", "stale_forms": [], "unknown_forms": []},
    }
