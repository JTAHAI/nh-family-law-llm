#!/usr/bin/env python3
"""Fail when active project files still contain Maine-specific legal authority.

The New Hampshire fork may retain narrowly scoped provenance/history references to
its Maine upstream, but runtime code, tests, active configuration, corpus data,
and current documentation must not depend on Maine statutes, courts, forms,
agencies, citations, or official-source domains.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {
    ".css", ".csv", ".html", ".ini", ".js", ".json", ".jsonl", ".jsx",
    ".md", ".mjs", ".ps1", ".py", ".rst", ".scss", ".sh", ".svg", ".toml",
    ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
SKIP_DIR_NAMES = {
    ".git", ".mypy_cache", ".nhfl_work", ".pytest_cache", ".ruff_cache",
    ".tox", ".venv", "__pycache__", "artifacts", "build", "dist", "htmlcov",
    "node_modules", "venv",
}

# These files intentionally describe the fork's provenance or define this audit.
ALLOWED_EXACT_PATHS = {
    "README.md",
    "MIGRATION_REPORT.md",
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "LEGACY_AUTHORITY_SCAN.md",
    "docs/MAINE_TO_NH_CROSSWALK.md",
    "docs/PASS_01_CODE_REPAIR.md",
    "docs/PASS_02_NH_AUTHORITY_ELIMINATION.md",
    "docs/v3/PASS_00_BASELINE_RECONCILIATION.md",
    "scripts/audit_nh_authorities.py",
    "scripts/scan_for_maine_authority.py",
}
ALLOWED_PATH_PREFIXES = {
    "docs/archive/",
    "docs/history/",
    "release_receipts/history/",
}

MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("abbreviated_foreign_statute", re.compile(r"\bM[e]\.\s*Rev\.\s*Stat\.", re.I)),
    ("structured_foreign_title", re.compile(r'add_statute\("19[-]A"|title_number="19[-]A"', re.I)),
    ("maine_official_domain", re.compile(r"(?:mainelegislature\.org|legislature\.maine\.gov|courts\.maine\.gov|(?:[a-z0-9-]+\.)?maine\.gov)", re.I)),
    ("maine_revised_statutes", re.compile(r"\b(?:title\s*19[- ]?a|19[- ]?a\s+m\.?r\.?s\.?a?|m\.?r\.?s\.?a?\.?\s*§|maine\s+revised\s+statutes?)\b", re.I)),
    ("maine_case_citation", re.compile(r"\b(?:19|20)\d{2}\s+ME\s+\d+\b", re.I)),
    ("maine_court", re.compile(r"\b(?:maine\s+law\s+court|maine\s+supreme\s+judicial\s+court|maine\s+judicial\s+branch)\b", re.I)),
    ("maine_authority_token", re.compile(r"\b(?:maine_statute|maine_case|maine_rule|maine_form|verified_official_maine|verified_maine_law_court|federal_maine|district_maine|maine_sjc|maine_revisor)\b", re.I)),
    ("maine_source_id", re.compile(r"\b(?:me-revisor|me-courts|mrs-title|case-(?:19|20)\d{2}-me-|me-title-19a|me-statutes|me-rules|me-nh-supreme)\b", re.I)),
    ("maine_runtime_identity", re.compile(r"(?:maine_family_law_llm|NewHampshireFamilyLawLLM|MAINE_FAST_INTERCHANGE|ME_FM_LLM|\bUS-ME\b)", re.I)),
    ("maine_legacy_control", re.compile(r"(?:uses_real_official_maine_authority|OFFICIAL_MAINE_DOMAINS|official_maine_fixture|_MAINE_JURISDICTION)", re.I)),
    ("maine_legacy_parser_label", re.compile(r"(?:\blawcourt\b|/courts/sjc/|revisor-layout-table|ingest-maine-authority|title[_-]?19a)", re.I)),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    marker: str
    excerpt: str


def _allowed(relative: str) -> bool:
    return relative in ALLOWED_EXACT_PATHS or any(relative.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES)


def _iter_text_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIR_NAMES for part in relative.parts):
            continue
        rel = relative.as_posix()
        if _allowed(rel):
            continue
        # Avoid accidentally decoding generated checksum manifests as source.
        if path.name == "MANIFEST.SHA256":
            continue
        yield path


def scan() -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for marker_name, pattern in MARKERS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                if line_end < 0:
                    line_end = len(text)
                excerpt = text[line_start:line_end].strip()
                findings.append(
                    Finding(
                        path=rel,
                        line=line,
                        column=match.start() - line_start + 1,
                        marker=marker_name,
                        excerpt=excerpt[:240],
                    )
                )
    return sorted(findings, key=lambda f: (f.path, f.line, f.column, f.marker))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    findings = scan()
    result = {
        "ok": not findings,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
        "allowed_provenance_paths": sorted(ALLOWED_EXACT_PATHS),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif findings:
        for item in findings:
            print(f"{item.path}:{item.line}:{item.column}: {item.marker}: {item.excerpt}")
        print(f"FAIL: {len(findings)} active Maine-authority marker(s) found.")
    else:
        print("PASS: no active Maine legal-authority markers found outside approved provenance/history files.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
