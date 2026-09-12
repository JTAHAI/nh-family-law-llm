#!/usr/bin/env python3
from __future__ import annotations
import importlib, json, os, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
identity=json.loads((ROOT/"config/product_identity.json").read_text(encoding="utf-8"))
assert identity["jurisdiction"]["code"]=="NH"
brand=importlib.import_module("nh_family_law_llm.branding")
protocol=importlib.import_module("nh_family_law_llm.protocol")
assert brand.PRODUCT_NAME=="New Hampshire Family Law LLM"
assert protocol.ProtocolEnvelope("research").urn("smoke")=="urn:nhfl:research:smoke"
with tempfile.TemporaryDirectory() as td:
    out=Path(td)/"export.json"
    out.write_text(json.dumps({
        "metadata":brand.export_metadata(title="Smoke export",authority_as_of="2026-09-11"),
        "protocol":protocol.PROTOCOL_ID,
        "jurisdiction":"NH",
    },indent=2),encoding="utf-8")
    saved=json.loads(out.read_text(encoding="utf-8"))
    assert saved["metadata"]["producer"]=="New Hampshire Family Law LLM"
    assert saved["protocol"]=="nhfl"
print("PASS: source-mode NH identity, protocol, and export journey")
