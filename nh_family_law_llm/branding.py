"""Canonical product, jurisdiction, visual, and export identity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PRODUCT_NAME: Final = "New Hampshire Family Law LLM"
PRODUCT_SHORT_NAME: Final = "NH Family Law LLM"
PACKAGE_NAME: Final = "nh-family-law-llm"
PYTHON_PACKAGE: Final = "nh_family_law_llm"
JURISDICTION_NAME: Final = "New Hampshire"
JURISDICTION_CODE: Final = "NH"
OFFICIAL_STATE_DOMAIN: Final = "gc.nh.gov"
OFFICIAL_COURT_DOMAIN: Final = "courts.nh.gov"
APP_ID: Final = "com.jtahai.nh-family-law-llm"
WINDOWS_AUMID: Final = "JTAHAI.NHFamilyLawLLM"
URI_SCHEME: Final = "nhfl"
PROTOCOL_NAMESPACE: Final = "urn:nhfl"
EXPORT_PRODUCER: Final = "New Hampshire Family Law LLM"
SUPPORT_EMAIL_PLACEHOLDER: Final = "support@example.invalid"

@dataclass(frozen=True, slots=True)
class BrandPalette:
    navy: str = "#102A43"
    granite: str = "#5B6770"
    paper: str = "#F7F9FB"
    white: str = "#FFFFFF"
    red: str = "#A61B29"
    focus: str = "#2F6FA3"

PALETTE: Final = BrandPalette()

def export_metadata(*, title: str, authority_as_of: str | None = None) -> dict[str, str]:
    """Return neutral metadata shared by PDF/DOCX/HTML/JSON export adapters."""
    data = {
        "title": title,
        "creator": PRODUCT_NAME,
        "producer": EXPORT_PRODUCER,
        "jurisdiction": JURISDICTION_NAME,
        "jurisdiction_code": JURISDICTION_CODE,
    }
    if authority_as_of:
        data["authority_as_of"] = authority_as_of
    return data
