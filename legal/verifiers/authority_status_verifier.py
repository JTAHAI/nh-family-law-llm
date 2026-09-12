from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

AuthorityVerificationStatus = Literal[
    "verified_official_nh",
    "verified_nh_supreme_court",
    "verified_federal",
    "verified_public_api",
    "user_provided_only",
    "stale_unknown",
    "not_found",
    "contradicted",
    "overruled_or_negative_treatment_unknown",
    "jurisdiction_mismatch",
]

OFFICIAL_NH_DOMAINS = {
    "gc.nh.gov",
    "www.gc.nh.gov",
    "courts.nh.gov",
    "www.courts.nh.gov",
    "dhhs.nh.gov",
    "www.dhhs.nh.gov",
    "sos.nh.gov",
    "www.sos.nh.gov",
    "doj.nh.gov",
    "www.doj.nh.gov",
    "education.nh.gov",
    "www.education.nh.gov",
    "state.nh.us",
    "www.state.nh.us",
}
FEDERAL_DOMAINS = {
    "uscode.house.gov",
    "www.law.cornell.edu",
    "www.supremecourt.gov",
    "supremecourt.gov",
    "www.uscourts.gov",
    "uscourts.gov",
    "www.nhd.uscourts.gov",
    "nhd.uscourts.gov",
}


@dataclass(frozen=True)
class AuthorityStatusResult:
    status: AuthorityVerificationStatus
    verified: bool
    source_id: str | None = None
    url: str | None = None
    freshness_status: str = "unknown"
    jurisdiction: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verified": self.verified,
            "source_id": self.source_id,
            "url": self.url,
            "freshness_status": self.freshness_status,
            "jurisdiction": self.jurisdiction,
            "message": self.message,
        }


class AuthorityStatusVerifier:
    """Verify authority class, jurisdiction, and freshness metadata."""

    def verify(self, url: str) -> AuthorityVerificationStatus:
        return self.verify_url(url).status

    def verify_url(self, url: str) -> AuthorityStatusResult:
        host = (urlparse(url).hostname or "").lower()
        if host in OFFICIAL_NH_DOMAINS or host.endswith(".nh.gov") or host.endswith(".state.nh.us"):
            path = urlparse(url).path.lower()
            if host.endswith("courts.nh.gov") and (
                "/supreme-court/" in path
                or "/orders-and-opinions" in path
                or "/opinions" in path
            ):
                return AuthorityStatusResult(
                    status="verified_nh_supreme_court",
                    verified=True,
                    url=url,
                    freshness_status="unknown",
                    jurisdiction="nh",
                    message="official New Hampshire Judicial Branch Supreme Court source",
                )
            return AuthorityStatusResult(
                status="verified_official_nh",
                verified=True,
                url=url,
                freshness_status="unknown",
                jurisdiction="nh",
                message="official New Hampshire government authority domain",
            )
        if host in FEDERAL_DOMAINS or host.endswith(".uscourts.gov"):
            return AuthorityStatusResult(
                status="verified_federal",
                verified=True,
                url=url,
                freshness_status="unknown",
                jurisdiction="federal",
                message="recognized federal authority domain",
            )
        return AuthorityStatusResult(
            status="stale_unknown",
            verified=False,
            url=url,
            freshness_status="unknown",
            message="source is not an admitted official authority domain",
        )

    def verify_source(
        self,
        source: dict[str, Any],
        *,
        expected_jurisdiction: str = "nh",
        max_age_days: int | None = None,
    ) -> AuthorityStatusResult:
        if not source:
            return AuthorityStatusResult(
                status="not_found",
                verified=False,
                message="source was not found in the registry",
            )

        source_id = source.get("source_id")
        url = source.get("url") or source.get("url_or_path")
        jurisdiction = (source.get("jurisdiction") or "").lower()
        authority_status = source.get("authority_status") or source.get("status")
        freshness_status = source.get("freshness_status") or "unknown"

        if jurisdiction and jurisdiction != expected_jurisdiction.lower() and jurisdiction != "federal":
            return AuthorityStatusResult(
                status="jurisdiction_mismatch",
                verified=False,
                source_id=source_id,
                url=url,
                freshness_status=freshness_status,
                jurisdiction=jurisdiction,
                message="source jurisdiction does not match requested New Hampshire scope",
            )

        if freshness_status in {"stale", "unknown", "stale_unknown"}:
            status: AuthorityVerificationStatus = "stale_unknown"
            verified = False
        elif authority_status in {
            "verified_official_nh",
            "verified_nh_supreme_court",
            "verified_federal",
        }:
            status = authority_status
            verified = True
        elif authority_status == "contradicted":
            status = "contradicted"
            verified = False
        elif authority_status == "overruled_or_negative_treatment_unknown":
            status = "overruled_or_negative_treatment_unknown"
            verified = False
        else:
            status = "stale_unknown"
            verified = False

        retrieved_at = source.get("retrieved_at")
        if max_age_days is not None and retrieved_at:
            parsed = _parse_datetime(retrieved_at)
            if parsed is None or (datetime.now(timezone.utc) - parsed).days > max_age_days:
                status = "stale_unknown"
                verified = False
                freshness_status = "stale"

        return AuthorityStatusResult(
            status=status,
            verified=verified,
            source_id=source_id,
            url=url,
            freshness_status=freshness_status,
            jurisdiction=jurisdiction or None,
            message="authority metadata verified" if verified else "authority metadata requires review",
        )


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
