#!/usr/bin/env python3
"""Rebuild MANIFEST.SHA256 from repository files, excluding generated residue."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "MANIFEST.SHA256"
EXCLUDED_PREFIXES = (
    ".git/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    "build/",
    "dist/",
)
EXCLUDED_PARTS = {"__pycache__", ".venv", "venv", "node_modules"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    for raw in result.stdout.splitlines():
        relative = raw.strip().replace("\\", "/")
        if not relative or relative == OUTPUT.name:
            continue
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        if any(part in EXCLUDED_PARTS for part in Path(relative).parts):
            continue
        path = ROOT / relative
        if path.is_file():
            paths.append(relative)
    return sorted(set(paths))


def main() -> int:
    paths = repository_files()
    lines = [f"{sha256(ROOT / relative)}  {relative}" for relative in paths]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(lines)} file hashes to {OUTPUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
