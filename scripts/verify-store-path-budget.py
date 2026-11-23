#!/usr/bin/env python3
"""Fail-closed path-length preflight for native WACK's legacy Win32 readers.

WACK inspects the installed MSIX payload using APIs that can enforce MAX_PATH
regardless of the application's own longPathAware setting. We bind both the
production name and a distinct but longer QA name, not just the compressed
archive's shallow relative filenames. This is not a substitute for native WACK.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

PRODUCTION_IDENTITY = "TAHAIWebServices.NewHampshireFamilyLawLLM"
QA_IDENTITY = PRODUCTION_IDENTITY + ".Q"
WINDOWS_APPS_ROOT = "C:\\Program Files\\WindowsApps\\"
WINDOWS_FAMILY_SUFFIX_LENGTH = 13
MAX_FILE_LENGTH = 255  # leave margin below WACK's 260-character legacy ceiling
MAX_DIR_LENGTH = 247
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 10000


def audit_msix(package: Path) -> dict:
    result = {
        "schema": "nhfl.store_path_budget.v1", "status": "blocked",
        "blockers": [], "package_sha256": None,
        "production_identity": PRODUCTION_IDENTITY, "qa_identity": QA_IDENTITY,
        "production_ready": False, "wack_qualified": False,
    }
    blockers = result["blockers"]
    try:
        if not package.is_file() or package.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("package_missing_or_too_large")
        raw = package.read_bytes()
        result["package_sha256"] = hashlib.sha256(raw).hexdigest()
        with zipfile.ZipFile(package) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_MEMBERS or not entries:
                raise ValueError("invalid_member_count")
            if "AppxManifest.xml" not in archive.namelist():
                raise ValueError("package_manifest_missing")
            manifest_bytes = archive.read("AppxManifest.xml")
            if b"<!DOCTYPE" in manifest_bytes.upper() or b"<!ENTITY" in manifest_bytes.upper():
                raise ValueError("unsafe_manifest_declaration")
            manifest = ET.fromstring(manifest_bytes)
            identity = next((node for node in manifest.iter() if node.tag.endswith("}Identity")), None)
            if identity is None:
                raise ValueError("identity_missing")
            name = identity.get("Name", "")
            version = identity.get("Version", "")
            arch = identity.get("ProcessorArchitecture", "")
            if not re.fullmatch(r"[A-Za-z0-9.]{3,70}", name) or not re.fullmatch(r"\d+(?:\.\d+){3}", version) or arch != "x64":
                raise ValueError("identity_invalid")
            if name not in {PRODUCTION_IDENTITY, QA_IDENTITY}:
                raise ValueError("unexpected_package_identity")
            if len(QA_IDENTITY) <= len(PRODUCTION_IDENTITY):
                raise ValueError("qa_identity_not_conservative")
            result["actual_identity"] = name
            result["package_version"] = version
            maximum = 0
            worst = ""
            for entry in entries:
                original = entry.orig_filename
                if original != entry.filename or "\\" in original or "\x00" in original or original.startswith("/") or any(x in ("", ".", "..") for x in original.rstrip("/").split("/")):
                    raise ValueError("unsafe_archive_member")
                for candidate_name in (PRODUCTION_IDENTITY, QA_IDENTITY):
                    # Package family identifiers always occupy 13 characters.
                    # Their exact hash depends on the publisher certificate.
                    prefix = WINDOWS_APPS_ROOT + candidate_name + "_" + version + "_" + arch + "__" + "x" * WINDOWS_FAMILY_SUFFIX_LENGTH + "\\"
                    full = prefix + original.replace("/", "\\")
                    parent = full.rpartition("\\")[0]
                    length = len(full)
                    if length > maximum:
                        maximum, worst = length, original
                    if length > MAX_FILE_LENGTH or len(parent) > MAX_DIR_LENGTH:
                        blockers.append("installed_path_exceeds_legacy_wack_budget")
                        break
            result["max_installed_file_path_characters"] = maximum
            result["max_file_limit"] = MAX_FILE_LENGTH
            result["max_directory_limit"] = MAX_DIR_LENGTH
            result["worst_relative_member"] = worst
    except (ValueError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile, RuntimeError) as exc:
        blockers.append("audit_unavailable:" + type(exc).__name__ + (":" + str(exc) if isinstance(exc, ValueError) else ""))
    # Keep the receipt bounded and avoid listing developer host paths.
    result["blockers"] = sorted(set(blockers))
    result["status"] = "pass" if not result["blockers"] else "blocked"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--msix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit_msix(args.msix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "blockers": report["blockers"], "max_path": report.get("max_installed_file_path_characters")}))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
