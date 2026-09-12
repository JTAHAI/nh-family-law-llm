from __future__ import annotations

"""New Hampshire official-source catalog loader.

The first migration pass removed the old New Hampshire catalog because it embedded New Hampshire
URLs directly in runtime code.  This module restores the connector contract while
loading only repository-declared New Hampshire authority seeds.  All manifest
records remain unverified until the acquisition/review pipeline promotes them.
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from legal.connectors.base import SourceTarget

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CATALOG = _REPO_ROOT / "config" / "nh_authority_sources.json"


def _content_type(url: str, row: dict[str, Any]) -> str:
    explicit = str(row.get("expected_content_type") or "").strip()
    if explicit:
        return explicit
    path = urlparse(url).path.lower()
    return "application/pdf" if path.endswith(".pdf") else "text/html"


def _parser_for(row: dict[str, Any], url: str) -> str:
    explicit = str(row.get("parser_name") or "").strip()
    if explicit:
        return explicit

    kind = str(row.get("authority_type") or row.get("source_class") or "").strip().lower()
    is_pdf = _content_type(url, row) == "application/pdf"
    if kind in {"statute", "session_law", "session_law_index", "constitution"}:
        return "nh_general_court_section" if not is_pdf else "pdf_snapshot"
    if kind in {
        "court_rule",
        "evidence_rule",
        "appellate_rule",
        "standing_order",
        "administrative_order",
    }:
        return "nh_rules_text" if is_pdf else "nh_rules_index"
    if kind in {"court_form", "form", "form_index"}:
        return "nh_form_text" if is_pdf else "nh_forms_index"
    if kind in {"case", "opinion", "case_law", "case_law_index"}:
        return "nh_supreme_court_opinion_text" if is_pdf else "nh_supreme_court_opinion_index"
    return "pdf_snapshot" if is_pdf else "html_snapshot"


def _source_class_for(row: dict[str, Any]) -> str:
    explicit = str(row.get("source_class") or "").strip()
    if explicit:
        return explicit
    kind = str(row.get("authority_type") or "official_source").strip().lower()
    aliases = {
        "statute": "statute_section",
        "session_law": "session_law",
        "constitution": "constitution",
        "court_rule": "court_rule",
        "evidence_rule": "evidence_rule",
        "appellate_rule": "appellate_rule",
        "standing_order": "standing_order",
        "administrative_order": "administrative_order",
        "administrative_rule": "administrative_rule",
        "court_form": "court_form",
        "form": "court_form",
        "case": "supreme_court_opinion",
        "case_law": "supreme_court_opinion",
        "opinion": "supreme_court_opinion",
        "official_guidance": "official_guidance",
        "self_help": "official_guidance",
    }
    return aliases.get(kind, kind or "official_source")


def _target_from_config(row: dict[str, Any], *, index: int = 0) -> SourceTarget:
    url = str(row.get("url") or row.get("source_url") or "").strip()
    target_id = str(
        row.get("target_id")
        or row.get("authority_id")
        or row.get("source_id")
        or f"nh-source-{index:04d}"
    ).strip()
    jurisdiction = str(row.get("jurisdiction") or "NH").strip()
    priority = row.get("priority", row.get("retrieval_priority", 1))
    notes = str(row.get("notes") or "").strip()
    if row.get("status"):
        notes = (notes + " " if notes else "") + f"Manifest status: {row.get('status')}."
    return SourceTarget(
        target_id=target_id,
        source_class=_source_class_for(row),
        jurisdiction=jurisdiction,
        url=url,
        parser_name=_parser_for(row, url),
        expected_content_type=_content_type(url, row),
        priority=int(priority or 1),
        freshness_strategy=str(row.get("freshness_strategy") or "retrieved_timestamp_and_review"),
        notes=notes,
    )


def _load_rows(path: str | Path) -> list[dict[str, Any]]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        rows = loaded
    elif isinstance(loaded, dict):
        rows = loaded.get("targets")
        if rows is None:
            rows = loaded.get("sources")
        if rows is None:
            rows = loaded.get("authorities")
    else:
        raise ValueError("source catalog must be a JSON array or object")
    if not isinstance(rows, list):
        raise ValueError("source catalog must contain targets, sources, or authorities as a list")
    return [row for row in rows if isinstance(row, dict)]


def _validate(targets: list[SourceTarget], *, label: str) -> list[SourceTarget]:
    problems: list[str] = []
    for target in targets:
        problems.extend(f"{target.target_id}: {problem}" for problem in target.validate())
    if problems:
        raise ValueError(f"invalid {label}: " + "; ".join(problems))
    return targets


def load_official_source_targets() -> list[SourceTarget]:
    if not _DEFAULT_CATALOG.is_file():
        raise FileNotFoundError(_DEFAULT_CATALOG)
    rows = _load_rows(_DEFAULT_CATALOG)
    targets = [_target_from_config(row, index=i) for i, row in enumerate(rows, start=1)]
    return _validate(targets, label="New Hampshire official source catalog")


def load_source_targets_from_file(path: str | Path) -> list[SourceTarget]:
    rows = _load_rows(path)
    targets = [_target_from_config(row, index=i) for i, row in enumerate(rows, start=1)]
    return _validate(targets, label="source target catalog")


__all__ = ["load_official_source_targets", "load_source_targets_from_file"]
