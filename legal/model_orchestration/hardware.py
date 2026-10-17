from __future__ import annotations

import ctypes
import math
import os
import platform
import struct
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _total_memory_bytes() -> int:
    if hasattr(os, "sysconf"):
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_PHYS_PAGES" in names:
            try:
                return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
            except (OSError, ValueError, TypeError):
                pass
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.ullTotalPhys)
    return 0


def _available_memory_bytes() -> int:
    if hasattr(os, "sysconf"):
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_AVPHYS_PAGES" in names:
            try:
                return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES"))
            except (OSError, ValueError, TypeError):
                pass
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.ullAvailPhys)
    return 0


def _gpu_hint() -> str:
    for name in ("NVIDIA_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES", "ROCM_VISIBLE_DEVICES"):
        value = os.environ.get(name, "").strip()
        if value and value not in {"void", "none", "-1"}:
            return value
    return ""


def _nvidia_inventory() -> tuple[dict[str, Any], ...]:
    """Read driver-published capacity without loading a model or using a shell."""

    executable = shutil.which("nvidia-smi")
    if not executable:
        return ()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=index,uuid,name,memory.total,memory.free,compute_cap",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 6:
            continue
        try:
            index = int(parts[0])
            total_mib = int(parts[3])
            free_mib = int(parts[4])
            capability = float(parts[5])
        except ValueError:
            continue
        if (not 0 <= index <= 31 or total_mib <= 0 or not 0 <= free_mib <= total_mib
                or not math.isfinite(capability) or capability <= 0):
            continue
        rows.append(
            {
                "index": index,
                "uuid": parts[1][:96],
                "name": parts[2][:160],
                "total_vram_bytes": total_mib * 1024**2,
                "available_vram_bytes": free_mib * 1024**2,
                "compute_capability": capability,
                "source": "local_driver",
            }
        )
    return tuple(rows)


def _instruction_sets() -> tuple[str, ...]:
    hints: list[str] = []
    processor = (platform.processor() or "").lower()
    if "x86" in processor or "amd64" in processor or "intel" in processor or "ryzen" in processor:
        hints.extend(["sse2", "sse4.2"])
    if "avx2" in processor:
        hints.append("avx2")
    if os.environ.get("NHFL_FORCE_AVX512", "").strip() == "1":
        hints.append("avx512")
    return tuple(sorted(set(hints)))


def measured_capacity_bytes(value: object) -> int:
    """Return measured nonnegative bytes, or zero when not safely known.

    Capacity hints, booleans, strings and nonfinite numbers cannot stand in for
    free memory. Zero remains zero; callers must never fall back to total RAM
    or VRAM when this conservative result cannot fund a requested operation.
    """
    return value if type(value) is int and value >= 0 else 0


@dataclass(frozen=True)
class HardwareProfile:
    os_name: str
    os_version: str
    machine: str
    architecture: str
    logical_cpu_count: int
    total_memory_bytes: int
    available_memory_bytes: int
    disk_free_bytes: int
    gpu_hint: str = ""
    gpu_name: str = ""
    vram_bytes: int = 0
    available_vram_bytes: int = 0
    gpu_compute_capability: float = 0.0
    current_operating_mode: str = "local_only"
    instruction_sets: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_concurrency: int = 1
    recommended_context_limit: int = 0
    estimated_peak_memory_bytes: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "machine": self.machine,
            "architecture": self.architecture,
            "logical_cpu_count": self.logical_cpu_count,
            "total_memory_bytes": self.total_memory_bytes,
            "available_memory_bytes": self.available_memory_bytes,
            "disk_free_bytes": self.disk_free_bytes,
            "gpu_hint": self.gpu_hint,
            "gpu_name": self.gpu_name,
            "vram_bytes": self.vram_bytes,
            "available_vram_bytes": self.available_vram_bytes,
            "gpu_compute_capability": self.gpu_compute_capability,
            "current_operating_mode": self.current_operating_mode,
            "instruction_sets": list(self.instruction_sets),
            "warnings": list(self.warnings),
            "recommended_concurrency": self.recommended_concurrency,
            "recommended_context_limit": self.recommended_context_limit,
            "estimated_peak_memory_bytes": self.estimated_peak_memory_bytes,
            "details": dict(self.details),
        }


def profile_hardware(root: str | Path) -> HardwareProfile:
    root_path = Path(root)
    disk_free = 0
    try:
        disk_free = int(shutil.disk_usage(root_path).free)
    except FileNotFoundError:
        parent = root_path.parent if root_path.parent != root_path else Path.home()
        try:
            disk_free = int(shutil.disk_usage(parent).free)
        except Exception:
            disk_free = 0

    # Zero means no measured headroom, not permission to spend total RAM.
    total_memory = max(0, _total_memory_bytes())
    available_memory = max(0, _available_memory_bytes())
    if total_memory:
        available_memory = min(available_memory, total_memory)
    cpu_count = os.cpu_count() or 1
    instruction_sets = _instruction_sets()
    warnings: list[str] = []
    if not available_memory:
        warnings.append("available_memory_unavailable")
    if available_memory < 4 * 1024**3:
        warnings.append("low_available_memory")
    if disk_free and disk_free < 10 * 1024**3:
        warnings.append("low_disk_space")
    gpu_hint = _gpu_hint()
    gpus = _nvidia_inventory()
    best_gpu = max(
        gpus,
        key=lambda row: (
            row["compute_capability"],
            row["available_vram_bytes"],
            row["total_vram_bytes"],
        ),
    ) if gpus else None
    raw_vram = os.environ.get("NHFL_VRAM_BYTES", "").strip()
    try:
        configured_vram = int(raw_vram) if raw_vram else 0
        if configured_vram < 0:
            raise ValueError("negative_vram_hint")
    except ValueError:
        configured_vram = 0
        warnings.append("invalid_vram_hint")
    configured_name = os.environ.get("NHFL_GPU_NAME", "").strip()
    # Operator hints are display metadata, not observed free GPU memory.
    # A detected device supplies a coherent name/total/free tuple and wins
    # over unrelated environment hints. In particular, free=0 stays zero.
    if best_gpu is not None:
        vram_bytes = int(best_gpu["total_vram_bytes"])
        available_vram_bytes = int(best_gpu["available_vram_bytes"])
        gpu_name = str(best_gpu["name"])
        gpu_capacity_source = "local_driver"
    else:
        vram_bytes = configured_vram
        available_vram_bytes = 0
        gpu_name = configured_name
        gpu_capacity_source = "operator_hint" if configured_vram or configured_name else "unavailable"
        if configured_vram:
            warnings.append("gpu_capacity_hint_unverified")
    if not gpu_hint and gpus:
        gpu_hint = "local_nvidia_driver"
    if not gpu_hint and not vram_bytes:
        warnings.append("no_gpu_hint_detected")

    recommended_concurrency = 1 if available_memory < 8 * 1024**3 else max(1, min(4, cpu_count // 2 or 1))
    recommended_context_limit = 4096 if available_memory < 8 * 1024**3 else 8192
    estimated_peak_memory_bytes = max(0, min(total_memory or available_memory, int(available_memory * 0.65))) if available_memory else 0

    return HardwareProfile(
        os_name=platform.system() or "unknown",
        os_version=platform.version() or "unknown",
        machine=platform.machine() or "unknown",
        # ``platform.architecture`` may invoke an external ``file`` process on
        # POSIX.  Hardware profiling is local-only and already knows the
        # running interpreter's pointer width, so avoid the subprocess and its
        # platform-dependent output contract entirely.
        architecture=f"{struct.calcsize('P') * 8}bit",
        logical_cpu_count=cpu_count,
        total_memory_bytes=total_memory,
        available_memory_bytes=available_memory,
        disk_free_bytes=disk_free,
        gpu_hint=gpu_hint,
        gpu_name=gpu_name,
        vram_bytes=vram_bytes,
        available_vram_bytes=available_vram_bytes,
        gpu_compute_capability=float((best_gpu or {}).get("compute_capability") or 0.0),
        current_operating_mode="local_only",
        instruction_sets=instruction_sets,
        warnings=tuple(sorted(set(warnings))),
        recommended_concurrency=recommended_concurrency,
        recommended_context_limit=recommended_context_limit,
        estimated_peak_memory_bytes=estimated_peak_memory_bytes,
        details={
            "platform": platform.platform(),
            "processor": platform.processor() or "",
            "python": platform.python_version(),
            "gpus": list(gpus),
            "gpu_capacity_source": gpu_capacity_source,
        },
    )
