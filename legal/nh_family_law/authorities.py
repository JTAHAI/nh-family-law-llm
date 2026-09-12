from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from nh_family_law_llm.authority_snapshot import (
    AuthorityRecord,
    active_records,
    default_manifest_path,
    load_payload,
    snapshot_root_for_manifest,
    verify_record_file,
    read_verified_record,
)

from .models import AuthorityReference


@dataclass(frozen=True, slots=True)
class CatalogAuthority:
    key: str
    authority_id: str
    citation: str
    title: str
    source_url: str
    required_status: str = "current_verified"

    def public_reference(self, *, status: str | None = None, eligible: bool = True) -> AuthorityReference:
        return AuthorityReference(
            authority_id=self.authority_id,
            citation=self.citation,
            title=self.title,
            source_url=self.source_url,
            status=status or self.required_status,
            retrieval_eligible=eligible,
        )


CATALOG: dict[str, CatalogAuthority] = {
    "parenting_policy": CatalogAuthority("parenting_policy", "NH-V0010", "RSA 461-A:2", "State Policy on Parental Involvement and Approximately Equal Time", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-2.htm"),
    "parenting_procedure": CatalogAuthority("parenting_procedure", "NH-V0011", "RSA 461-A:3", "Procedure and Jurisdiction for Parenting and Support", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-3.htm"),
    "parenting_plan": CatalogAuthority("parenting_plan", "NH-V0012", "RSA 461-A:4", "Parenting Plans", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-4.htm"),
    "family_access": CatalogAuthority("family_access", "NH-V0013", "RSA 461-A:4-a", "Family Access Motion", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-4-a.htm"),
    "decision_making": CatalogAuthority("decision_making", "NH-V0014", "RSA 461-A:5", "Decision-Making Responsibility", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-5.htm"),
    "best_interest": CatalogAuthority("best_interest", "NH-V0015", "RSA 461-A:6", "Best-Interest Factors", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-6.htm"),
    "mediation": CatalogAuthority("mediation", "NH-V0016", "RSA 461-A:7", "Mediation of Cases Involving Children", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-7.htm"),
    "parenting_modification": CatalogAuthority("parenting_modification", "NH-V0017", "RSA 461-A:11", "Modification of Parental Rights and Responsibilities", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-11.htm"),
    "relocation": CatalogAuthority("relocation", "NH-V0018", "RSA 461-A:12", "Relocation of a Child Residence", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-12.htm"),
    "support_duration": CatalogAuthority("support_duration", "NH-V0019", "RSA 461-A:14", "Support, Duration, Medical Support, and Enforcement", "https://gc.nh.gov/rsa/html/XLIII/461-A/461-A-14.htm"),
    "support_income": CatalogAuthority("support_income", "NH-V0002", "RSA 458-C:2", "Child-Support Definitions and Income", "https://gc.nh.gov/rsa/html/XLIII/458-C/458-C-2.htm"),
    "support_formula": CatalogAuthority("support_formula", "NH-V0003", "RSA 458-C:3", "Child-Support Formula", "https://gc.nh.gov/rsa/html/XLIII/458-C/458-C-3.htm"),
    "support_worksheet": CatalogAuthority("support_worksheet", "NH-V0004", "RSA 458-C:3-a", "Child-Support Guidelines Worksheet", "https://gc.nh.gov/rsa/html/XLIII/458-C/458-C-3-a.htm"),
    "support_presumption": CatalogAuthority("support_presumption", "NH-V0005", "RSA 458-C:4", "Application and Presumption of Guidelines", "https://gc.nh.gov/rsa/html/XLIII/458-C/458-C-4.htm"),
    "support_deviation": CatalogAuthority("support_deviation", "NH-V0006", "RSA 458-C:5", "Adjustments Under Special Circumstances", "https://gc.nh.gov/rsa/html/XLIII/458-C/458-C-5.htm"),
    "support_modification": CatalogAuthority("support_modification", "NH-V0008", "RSA 458-C:7", "Modification of Child-Support Order", "https://gc.nh.gov/rsa/html/XLIII/458-C/458-C-7.htm"),
    "administrative_order_definition": CatalogAuthority("administrative_order_definition", "NH-V0021", "RSA 161-C:2", "Administrative Support — Definition of Legal Order", "https://gc.nh.gov/rsa/html/XII/161-C/161-C-2.htm"),
    "administrative_collection": CatalogAuthority("administrative_collection", "NH-V0022", "RSA 161-C:7", "DHHS Notice When a Court Support Order Exists", "https://gc.nh.gov/rsa/html/XII/161-C/161-C-7.htm"),
    "administrative_establishment": CatalogAuthority("administrative_establishment", "NH-V0023", "RSA 161-C:8", "Administrative Establishment When No Legal Order Exists", "https://gc.nh.gov/rsa/html/XII/161-C/161-C-8.htm"),
    "administrative_hearing": CatalogAuthority("administrative_hearing", "NH-V0024", "RSA 161-C:9", "Administrative Hearings, Modification, and Court Supersession", "https://gc.nh.gov/rsa/html/XII/161-C/161-C-9.htm"),
    "uccjea_initial": CatalogAuthority("uccjea_initial", "NH-V0026", "RSA 458-A:12", "UCCJEA Initial Jurisdiction", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-12.htm"),
    "uccjea_continuing": CatalogAuthority("uccjea_continuing", "NH-V0027", "RSA 458-A:13", "UCCJEA Exclusive Continuing Jurisdiction", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-13.htm"),
    "uccjea_modify": CatalogAuthority("uccjea_modify", "NH-V0028", "RSA 458-A:14", "UCCJEA Modification of Another State's Order", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-14.htm"),
    "uccjea_emergency": CatalogAuthority("uccjea_emergency", "NH-V0029", "RSA 458-A:15", "UCCJEA Temporary Emergency Jurisdiction", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-15.htm"),
    "uccjea_notice": CatalogAuthority("uccjea_notice", "NH-V0030", "RSA 458-A:16", "UCCJEA Notice and Opportunity to Be Heard", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-16.htm"),
    "uccjea_parallel": CatalogAuthority("uccjea_parallel", "NH-V0031", "RSA 458-A:17", "UCCJEA Simultaneous Proceedings", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-17.htm"),
    "uccjea_forum": CatalogAuthority("uccjea_forum", "NH-V0032", "RSA 458-A:18", "UCCJEA Inconvenient Forum", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-18.htm"),
    "uccjea_conduct": CatalogAuthority("uccjea_conduct", "NH-V0033", "RSA 458-A:19", "UCCJEA Unjustifiable Conduct", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-19.htm"),
    "uccjea_disclosure": CatalogAuthority("uccjea_disclosure", "NH-V0034", "RSA 458-A:20", "UCCJEA Residence and Proceeding Disclosures", "https://gc.nh.gov/rsa/html/XLIII/458-A/458-A-20.htm"),
    "uifsa": CatalogAuthority("uifsa", "NH-0027", "RSA 546-B", "Uniform Interstate Family Support Act", "https://gc.nh.gov/rsa/html/LV/546-B/546-B-mrg.htm", required_status="source_seed_unverified"),
}


class AuthorityGate:
    """Verify that behavior rules cite promoted, hash-valid local authority."""

    def __init__(self, *, as_of: date, manifest_path: str | Path | None = None) -> None:
        self.as_of = as_of
        self.manifest_path = Path(manifest_path).resolve() if manifest_path else default_manifest_path()
        self._payload = load_payload(self.manifest_path)
        self._records_by_id = {
            str(row.get("authority_id")): AuthorityRecord.from_dict(row)
            for row in self._payload.get("authorities", [])
        }
        self._active_ids = {
            row.authority_id for row in active_records(as_of=as_of, path=self.manifest_path)
        }
        self._root = self._resolve_storage_root()
        self._future_effective_sections = self._expired_pending_overlays()

    def _resolve_storage_root(self) -> Path:
        """Resolve local filenames for repository and embedded manifests.

        Repository records use paths rooted at the checkout (``corpus/...``),
        while the packaged manifest uses paths rooted at ``authority_snapshot``.
        Refuse ambiguous layouts rather than silently skipping hash checks.
        """
        snapshot_root = snapshot_root_for_manifest(self.manifest_path)
        candidates = [snapshot_root, snapshot_root.parent]
        local_names = [
            record.local_filename
            for record in self._records_by_id.values()
            if record.local_filename
        ]
        for candidate in candidates:
            if any((candidate / name).is_file() for name in local_names):
                return candidate
        return snapshot_root


    def _expired_pending_overlays(self) -> tuple[str, ...]:
        """Return base citations whose pending amendment date has arrived.

        A prior capsule is not allowed to remain active after a known amendment
        reaches its effective date.  The amended section must be freshly
        reviewed and explicitly promoted first.
        """
        blocked: list[str] = []
        for row in self._payload.get("authorities", []):
            if row.get("status") != "future_effective_pending":
                continue
            effective = row.get("effective_date")
            if not effective:
                continue
            try:
                arrived = date.fromisoformat(str(effective)) <= self.as_of
            except ValueError:
                arrived = True
            if not arrived:
                continue
            citation = str(row.get("citation") or "")
            base = citation.split(",", 1)[0].split(" (", 1)[0].strip()
            if base:
                blocked.append(base)
        return tuple(dict.fromkeys(blocked))

    def _blocked_by_pending_amendment(self, citation: str) -> bool:
        return any(citation == base or citation.startswith(base + ",") for base in self._future_effective_sections)

    def resolve(self, keys: Iterable[str]) -> tuple[list[AuthorityReference], list[str]]:
        refs: list[AuthorityReference] = []
        gaps: list[str] = []
        for key in keys:
            catalog = CATALOG.get(key)
            if catalog is None:
                gaps.append(f"Unknown authority catalog key: {key}")
                continue
            record = self._records_by_id.get(catalog.authority_id)
            if record is None:
                refs.append(catalog.public_reference(status="missing", eligible=False))
                gaps.append(f"{catalog.citation}: manifest record missing")
                continue
            file_valid = verify_record_file(record, repository_root=self._root)
            pending_amendment = self._blocked_by_pending_amendment(catalog.citation)
            active = (
                catalog.authority_id in self._active_ids
                and file_valid
                and not pending_amendment
            )
            refs.append(catalog.public_reference(status=record.status, eligible=active))
            if not active:
                if pending_amendment:
                    reason = "known amendment is now effective but the amended section is not promoted"
                elif record.status != "current_verified" or not record.retrieval_eligible:
                    reason = "not current/retrieval eligible"
                else:
                    reason = "local source hash missing or invalid"
                gaps.append(f"{catalog.citation}: {reason}")
        return refs, gaps

    def source_text(self, authority_id: str) -> str | None:
        record = self._records_by_id.get(authority_id)
        if record is None or authority_id not in self._active_ids:
            return None
        if self._blocked_by_pending_amendment(record.citation):
            return None
        if not verify_record_file(record, repository_root=self._root):
            return None
        if not record.local_filename:
            return None
        path = self._root / record.local_filename
        return path.read_text(encoding="utf-8", errors="replace")

    def available_sources(self) -> list[dict[str, object]]:
        """List catalog source statuses without exposing local paths or evidence data."""
        refs, _ = self.resolve(CATALOG)
        return [ref.to_dict() for ref in refs]

    def source_capsule(self, authority_id: str) -> dict[str, object]:
        """Return only an active, hash-verified reviewed capsule, never a raw path."""
        catalog = next((row for row in CATALOG.values() if row.authority_id == authority_id), None)
        if catalog is None:
            raise KeyError(authority_id)
        refs, gaps = self.resolve([catalog.key])
        if gaps or not refs[0].retrieval_eligible:
            raise ValueError("source_not_active_or_verified")
        record = self._records_by_id[authority_id]
        raw = read_verified_record(record, repository_root=self._root)
        if raw is None:
            raise ValueError("source_integrity_failed")
        return {
            **refs[0].to_dict(),
            "as_of_date": self.as_of.isoformat(),
            "content_kind": "reviewed_capsule",
            "extract_is_verbatim": record.extract_is_verbatim,
            "raw_source_bytes_preserved": record.raw_source_bytes_preserved,
            "safe_for_direct_quote": False,
            "sha256": record.sha256,
            "text": raw.decode("utf-8"),
            "review_required": True,
            "notice": "This is a source-grounded summary, not the official statute text. Open the official source before quoting or filing.",
        }

    def desktop_status(self) -> dict[str, object]:
        sources = self.available_sources()
        return {
            "jurisdiction": "NH",
            "as_of_date": self.as_of.isoformat(),
            "snapshot_as_of_date": self._payload.get("as_of_date"),
            "catalog_source_count": len(sources),
            "active_catalog_source_count": sum(row["retrieval_eligible"] is True for row in sources),
            "known_amendment_blocks": list(self._future_effective_sections),
            "sources": sources,
            "review_required": True,
            "exhaustive_coverage": False,
            "attorney_reviewed": False,
            "source_format": "reviewed_nonverbatim_capsules",
            "support_calculator_available": False,
            "local_model_required_for_issue_spotting": False,
            "facts_persisted_by_review_routes": False,
        }
