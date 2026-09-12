#!/usr/bin/env python3
from __future__ import annotations
import ast, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKIP={".git","node_modules",".venv","venv","dist","build","__pycache__",".pytest_cache"}
errors=[]
identity_path=ROOT/"config/product_identity.json"
if not identity_path.is_file():
    errors.append("missing config/product_identity.json")
else:
    identity=json.loads(identity_path.read_text(encoding="utf-8"))
    checks={
      "product_name":"New Hampshire Family Law LLM",
      "package_name":"nh-family-law-llm",
      "application_id":"com.jtahai.nh-family-law-llm",
      "windows_aumid":"JTAHAI.NHFamilyLawLLM",
      "uri_scheme":"nhfl",
    }
    for key,expected in checks.items():
        if identity.get(key)!=expected:
            errors.append(f"identity.{key}={identity.get(key)!r}; expected {expected!r}")
    if identity.get("jurisdiction",{}).get("code")!="NH":
        errors.append("identity.jurisdiction.code must be NH")
for rel in (
 "assets/brand/nh-family-law-llm-mark.svg",
 "assets/brand/nh-family-law-llm-banner.png",
 "assets/brand/nhfl-theme.css",
 "schemas/nhfl-evidence-envelope.schema.json",
 "packaging/windows/app-identity.json",
 "packaging/windows/AppxManifest.template.xml",
):
    if not (ROOT/rel).is_file():
        errors.append(f"missing {rel}")
for py in ROOT.rglob("*.py"):
    if any(part in SKIP for part in py.parts):
        continue
    try:
        ast.parse(py.read_text(encoding="utf-8"),filename=str(py))
    except SyntaxError as exc:
        errors.append(f"syntax {py.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
legacy_prefix="M"+"FL_"
legacy_markers=(legacy_prefix,"m"+"fl://","urn:"+"m"+"fl:","vnd."+"m"+"fl")
ext={".py",".js",".jsx",".ts",".tsx",".toml",".yaml",".yml",".json",".html",".css",".ps1",".sh",".spec",".xml"}
allow={"scripts/verify_pass_03.py","scripts/scan_legacy_runtime_identifiers.py"}
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in ext or any(part in SKIP for part in p.parts):
        continue
    rel=p.relative_to(ROOT).as_posix()
    if rel in allow or "/compat/legacy_environment.py" in rel:
        continue
    text=p.read_text(encoding="utf-8",errors="ignore")
    found=[marker for marker in legacy_markers if marker in text]
    if found:
        errors.append(f"legacy runtime marker in {rel}: {found}")
if errors:
    for error in errors:
        print("FAIL:",error)
    raise SystemExit(1)
print("PASS: NH UI/runtime/protocol source gate")
