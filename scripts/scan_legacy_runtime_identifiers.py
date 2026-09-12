#!/usr/bin/env python3
"""Fail when inherited runtime identifiers escape the explicit compatibility lane."""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKIP={".git","node_modules",".venv","venv","dist","build","__pycache__"}
ALLOW={
 "scripts/scan_legacy_runtime_identifiers.py",
 "scripts/verify_pass_03.py",
}
EXT={".py",".js",".jsx",".ts",".tsx",".toml",".yaml",".yml",".json",".html",".css",".ps1",".sh",".spec",".xml"}
old_prefix="M"+"FL_"
markers=(old_prefix,"m"+"fl://","urn:"+"m"+"fl:","vnd."+"m"+"fl")
hits=[]
for path in ROOT.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in EXT or any(part in SKIP for part in path.parts):
        continue
    rel=path.relative_to(ROOT).as_posix()
    if rel in ALLOW or "/compat/legacy_environment.py" in rel:
        continue
    text=path.read_text(encoding="utf-8",errors="ignore")
    found=[m for m in markers if m in text]
    if found:
        hits.append({"file":rel,"markers":found})
if hits:
    for hit in hits:
        print(f"FAIL {hit['file']}: {', '.join(hit['markers'])}")
    raise SystemExit(1)
print("PASS: no inherited runtime identifiers outside compatibility lane")
