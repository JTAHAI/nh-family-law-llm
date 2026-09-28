"""Git checkout must preserve identical packaging templates on either host."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    "store/msix/AppxManifest.xml.in",
    "packaging/windows/AppxManifest.template.xml",
)


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_msix_templates_remain_byte_identical_after_git_checkout(tmp_path, autocrlf):
    source = tmp_path / "synthetic-checkout"
    destination = tmp_path / "materialized-checkout"
    source.mkdir()
    for name in (".gitattributes", *TEMPLATES):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    def git(*args):
        subprocess.run(
            ["git", "-C", str(source), "-c", f"core.autocrlf={autocrlf}", *args],
            check=True, capture_output=True, timeout=30,
        )
    git("init", "-q")
    git("add", ".")
    git("checkout-index", "--all", "--prefix=" + destination.as_posix() + "/")
    first, second = ((destination / name).read_bytes() for name in TEMPLATES)
    assert first == second == (ROOT / TEMPLATES[0]).read_bytes()
    assert b"\r\n" not in first
