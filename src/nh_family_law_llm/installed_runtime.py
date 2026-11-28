"""Helpers for resolving and launching the installed Windows package."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .version import APP_EXECUTABLE_NAME


def run_package_query(command: str, package_name: str) -> subprocess.CompletedProcess | None:
    """Run a fixed package query with its selector passed separately as data."""
    if re.fullmatch(r"[A-Za-z0-9.-]{3,50}", package_name) is None:
        raise ValueError("Invalid Windows package identity name")
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            env={**os.environ, "FAMILY_LAW_PACKAGE_QUERY": package_name},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

DEFAULT_PACKAGE_NAME = "TAHAIWebServices.NewHampshireFamilyLawLLM"


def query_package_registration(package_name: str = DEFAULT_PACKAGE_NAME) -> dict[str, str]:
    command = (
        "$pkg = Get-AppxPackage -Name $env:FAMILY_LAW_PACKAGE_QUERY -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 PackageFullName,InstallLocation,@{Name='Version';Expression={[string]$_.Version}}; "
        "if ($pkg) { $pkg | ConvertTo-Json -Compress }"
    )
    completed = run_package_query(command, package_name)
    if completed is None or completed.returncode != 0:
        return {}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    fields = ("PackageFullName", "InstallLocation", "Version")
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(key), str) and payload[key].strip() for key in fields
    ):
        return {}
    if not payload["PackageFullName"].casefold().startswith(package_name.casefold() + "_"):
        return {}
    return {key: payload[key] for key in fields}


@dataclass(frozen=True)
class InstalledRuntimeResolution:
    package_name: str
    package_full_name: str
    install_location: str
    version: str
    executable_path: str
    source: str
    available: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fallback_runtime_executable(fallback_runtime_root: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    env_root = str(os.environ.get("NHFL_RUNTIME_ROOT") or "").strip()
    if env_root:
        candidates.append(Path(env_root))
    if fallback_runtime_root is not None:
        candidates.append(Path(fallback_runtime_root))
    repo_runtime = Path(__file__).resolve().parents[2] / "dist" / "store" / "runtime"
    candidates.append(repo_runtime)
    for root in candidates:
        exe = root / APP_EXECUTABLE_NAME
        if exe.is_file():
            return exe
    return None


def resolve_installed_runtime_executable(
    package_name: str = DEFAULT_PACKAGE_NAME,
    *,
    fallback_runtime_root: Path | None = None,
) -> InstalledRuntimeResolution:
    """Resolve the installed Store package executable, or fall back to the bundled runtime."""

    registration = query_package_registration(package_name)
    if registration:
        exe = Path(registration["InstallLocation"]) / APP_EXECUTABLE_NAME
        if exe.is_file():
            return InstalledRuntimeResolution(
                package_name=package_name,
                package_full_name=registration["PackageFullName"],
                install_location=registration["InstallLocation"],
                version=registration["Version"],
                executable_path=str(exe),
                source="appx_package",
                available=True,
            )

    fallback_exe = _fallback_runtime_executable(fallback_runtime_root)
    if fallback_exe is not None:
        return InstalledRuntimeResolution(
            package_name=package_name,
            package_full_name="",
            install_location=str(fallback_exe.parent),
            version="",
            executable_path=str(fallback_exe),
            source="bundled_runtime",
            available=False,
        )

    return InstalledRuntimeResolution(
        package_name=package_name,
        package_full_name="",
        install_location="",
        version="",
        executable_path="",
        source="unresolved",
        available=False,
    )
