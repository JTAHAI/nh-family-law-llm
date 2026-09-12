from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.security import review_response
from legal.nh_family_law import (
    AuthoritySnapshotUnavailable,
    InvalidLegalBehaviorInput,
    NewHampshireLegalBehaviorEngine,
)

router = APIRouter(tags=["nh-legal-behavior"])


class LegalBehaviorRequest(BaseModel):
    """Open fact envelope; the deterministic engine validates issue-specific fields."""

    model_config = ConfigDict(extra="allow")

    as_of_date: str | None = None
    question: str = Field(default="", max_length=20_000)
    parenting: dict[str, Any] | None = None
    support: dict[str, Any] | None = None
    support_order: dict[str, Any] | None = None
    interstate: dict[str, Any] | None = None
    safety: dict[str, Any] | bool | None = None
    draft_text: str | None = Field(default=None, max_length=50_000)


@router.post(
    "/legal-behavior/analyze",
    summary="Run source-gated New Hampshire parenting and support issue spotting",
)
def analyze_legal_behavior(payload: LegalBehaviorRequest):
    try:
        report = NewHampshireLegalBehaviorEngine().analyze(
            payload.model_dump(exclude_none=True)
        )
    except InvalidLegalBehaviorInput as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_nh_legal_behavior_input",
                "message": str(exc),
                "review_required": True,
            },
        ) from exc
    except AuthoritySnapshotUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "nh_authority_snapshot_unavailable",
                "message": "The configured NH snapshot could not be verified. Check the manifest and source hashes locally.",
                "review_required": True,
            },
        ) from exc
    return review_response(
        "POST /api/legal-behavior/analyze",
        "nh_legal_behavior_analysis",
        report.to_dict(),
    )
