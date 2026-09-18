"""Truthful runtime feature-tier and optional-pack reporting."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

PACKS = {
    "core": ("fastapi", "pypdf", "cryptography"),
    "document_intelligence": ("docling", "presidio_analyzer", "spacy"),
    "advanced_retrieval": ("sqlite_vec", "qdrant_client"),
}


def _bundled_tier() -> str | None:
    """Read the immutable tier stamp created beside a frozen executable.

    Build-time environment variables do not survive into a user-launched MSIX,
    so an executable must not report a development tier merely because the
    launcher has a clean environment.
    """

    # PyInstaller can run imports from ``_internal`` while the launcher lives
    # one directory above it.  Look only at that small, deterministic ancestor
    # chain so both layouts find the package-adjacent immutable stamp.
    candidates: list[Path] = []
    for origin in (Path(sys.executable).resolve(), Path(getattr(sys, "_MEIPASS", "")).resolve()):
        if not str(origin) or str(origin) == ".":
            continue
        parent = origin.parent if origin.suffix else origin
        for _ in range(4):
            candidate = parent / "store" / "feature-tier.json"
            if candidate not in candidates:
                candidates.append(candidate)
            if parent.parent == parent:
                break
            parent = parent.parent
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("feature_tier")
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        tier = str(value or "").strip().lower()
        if tier in {"essential", "full"}:
            return tier
    return None


def feature_tier_status() -> dict[str, Any]:
    configured = str(os.environ.get("NHFL_STORE_FEATURE_TIER") or _bundled_tier() or "development").strip().lower()
    packs: dict[str, dict[str, Any]] = {}
    for name, modules in PACKS.items():
        availability = {module: importlib.util.find_spec(module) is not None for module in modules}
        packs[name] = {
            "status": "available" if all(availability.values()) else "not_installed",
            "modules": availability,
            "required_for_core_workflows": name == "core",
        }
    blockers = [
        f"required_pack_unavailable:{name}"
        for name, value in packs.items()
        if value["required_for_core_workflows"] and value["status"] != "available"
    ]
    return {
        "schema_version": "local_feature_tier_status_v1",
        "status": "pass" if not blockers else "blocked",
        "configured_tier": configured,
        "packs": packs,
        "core_workflows_available": not blockers,
        "optional_features_degrade_gracefully": True,
        "default_store_tier": "essential",
        "blockers": blockers,
        "review_required": False,
    }


__all__ = ["PACKS", "feature_tier_status"]
