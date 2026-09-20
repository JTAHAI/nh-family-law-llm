"""Read-only package configuration paths for checkout, wheel and frozen layouts.

This resolver is for shipped application settings, NOT a legal-authority manifest
or a user-selected trust file. Explicit constructor overrides stay explicit.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys


def runtime_config_path(filename: str) -> Path:
    if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.json', filename):
        raise ValueError('A single shipped JSON configuration filename is required')
    if getattr(sys, 'frozen', False):
        package = Path(__file__).resolve().parent
        bundle = Path(getattr(sys, '_MEIPASS', package.parent))
        # A frozen executable must use its sealed bundle configuration even
        # when it was launched from a source checkout during qualification.
        return bundle / 'configs' / filename
    package = Path(__file__).resolve().parent
    # Do not walk ancestors of site-packages and accidentally borrow a checkout.
    checkout = package.parent.parent
    if package.parent.name == 'src' and (checkout / 'pyproject.toml').is_file():
        return checkout / 'configs' / filename
    return package / 'resources' / 'runtime' / 'configs' / filename
