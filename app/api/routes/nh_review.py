"""Read-only authority inspection for the bundled NH review desk.

These routes inherit the enterprise role/tenant dependency and production
loopback protection. They cannot import files, change a case, or promote law.
"""
from __future__ import annotations

from datetime import date
import re

from fastapi import APIRouter, HTTPException

from app.api.security import review_response
from legal.nh_family_law.authorities import AuthorityGate
from nh_family_law_llm.version import VERSION

router = APIRouter(tags=["nh-review-desk"])


def _gate(as_of_date: date | None) -> AuthorityGate:
    try:
        return AuthorityGate(as_of=as_of_date or date.today())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Never return a configured path, OS diagnostic, or private file name.
        raise HTTPException(503, detail={
            "error": "nh_authority_snapshot_unavailable", "review_required": True,
            "message": "The configured NH snapshot could not be verified. Check its manifest and source hashes locally.",
        }) from exc


@router.get("/nh-review/status")
def status(as_of_date: date | None = None):
    payload = _gate(as_of_date).desktop_status()
    payload["version"] = VERSION
    return review_response("GET /api/nh-review/status", "nh_review_status", payload)


@router.get("/nh-review/sources/{authority_id}")
def source(authority_id: str, as_of_date: date | None = None):
    if not re.fullmatch(r"NH-[A-Z0-9]{4,12}", authority_id):
        raise HTTPException(404, detail={"error": "source_not_found", "review_required": True})
    gate = _gate(as_of_date)
    try:
        payload = gate.source_capsule(authority_id)
    except KeyError as exc:
        raise HTTPException(404, detail={"error": "source_not_found", "review_required": True}) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(409, detail={
            "error": "source_not_active_or_verified", "review_required": True,
            "message": "This source is unavailable for the requested date or failed integrity checks.",
        }) from exc
    return review_response("GET /api/nh-review/sources/{authority_id}", "nh_source_capsule_review", payload)
