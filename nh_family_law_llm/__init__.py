from __future__ import annotations


from .compat.legacy_environment import apply_legacy_environment_aliases as _apply_legacy_environment_aliases
_apply_legacy_environment_aliases()
del _apply_legacy_environment_aliases

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "nh_family_law_llm"

if _SRC_PACKAGE.is_dir():
    # Point the compatibility package at the canonical src-layout package
    # without executing source text dynamically.
    __path__ = [str(_SRC_PACKAGE)]

from .version import VERSION

__all__ = ["__version__"]
__version__ = VERSION
