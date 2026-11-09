"""Resolve frozen application code from src, never the checkout-only shim."""
from pathlib import Path


def pre_find_module_path(api):
    source = Path(__file__).resolve().parents[4] / "src"
    if not (source / "nh_family_law_llm" / "__init__.py").is_file():
        raise RuntimeError("canonical_source_package_missing")
    api.search_dirs = [str(source)]
