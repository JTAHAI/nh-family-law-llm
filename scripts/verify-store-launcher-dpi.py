#!/usr/bin/env python3
"""Verify the WACK-required DPI declaration is embedded in the frozen PE.

Source manifests are not the installed-executable manifest. A production build
must pass the PE resource check against its exact frozen launcher before MSIX
sealing. No DPI claim is made on non-Windows hosts without that PE evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

DPIV2 = "{http://schemas.microsoft.com/SMI/2016/WindowsSettings}dpiAwareness"
LONG_PATH = "{http://schemas.microsoft.com/SMI/2016/WindowsSettings}longPathAware"
EXECUTION = "{urn:schemas-microsoft-com:asm.v3}requestedExecutionLevel"


def validate_manifest(raw: bytes) -> list[str]:
    blockers = []
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        return ["unsafe_manifest_declaration"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return ["manifest_xml_invalid"]
    dpi = [node.text.strip() for node in root.iter(DPIV2) if node.text]
    if dpi != ["PerMonitorV2"]:
        blockers.append("per_monitor_v2_missing_or_ambiguous")
    long_paths = [node.text.strip() for node in root.iter(LONG_PATH) if node.text]
    if long_paths != ["true"]:
        blockers.append("long_path_awareness_missing_or_ambiguous")
    elevation = [node.attrib for node in root.iter(EXECUTION)]
    if len(elevation) != 1 or elevation[0].get("level") != "asInvoker" or elevation[0].get("uiAccess") != "false":
        blockers.append("as_invoker_manifest_missing_or_ambiguous")
    return blockers


def embedded_manifest(exe: Path) -> tuple[bytes, str]:
    # pefile is pulled into the pinned Windows PyInstaller build environment.
    # Imported here so Linux source tests need no Windows dependencies.
    import pefile

    pe = pefile.PE(str(exe), fast_load=False)
    try:
        resources = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
        if resources is None:
            raise ValueError("exe_resource_directory_missing")
        blobs = []
        for type_entry in resources.entries:
            if type_entry.id != 24:  # Windows RT_MANIFEST
                continue
            for name_entry in type_entry.directory.entries:
                for language in name_entry.directory.entries:
                    data = language.data.struct
                    blobs.append(pe.get_data(data.OffsetToData, data.Size))
        if len(blobs) != 1:
            raise ValueError("exe_manifest_missing_or_ambiguous")
        return blobs[0], hashlib.sha256(exe.read_bytes()).hexdigest()
    finally:
        pe.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    blockers = []
    receipt = {"schema": "nhfl.store_launcher_dpi.v1", "status": "blocked",
               "exe_sha256": None, "embedded_manifest_sha256": None,
               "source_manifest_sha256": None, "wack_qualified": False,
               "microsoft_certified": False, "production_ready": False}
    try:
        raw = args.source_manifest.read_bytes()
        receipt["source_manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        blockers.extend(validate_manifest(raw))
        if not args.exe.is_file():
            blockers.append("frozen_executable_missing")
        else:
            embedded, digest = embedded_manifest(args.exe)
            receipt["exe_sha256"] = digest
            receipt["embedded_manifest_sha256"] = hashlib.sha256(embedded).hexdigest()
            blockers.extend(validate_manifest(embedded))
    except (OSError, ValueError, ImportError, RuntimeError, AttributeError) as exc:
        blockers.append("launcher_manifest_unavailable:" + type(exc).__name__)
    receipt["blockers"] = sorted(set(blockers))
    receipt["status"] = "pass" if not blockers else "blocked"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
