"""Canonical version and product metadata for New Hampshire Family Law LLM."""

from __future__ import annotations

VERSION = "8.0.10"
BUILD_NUMBER = 80
# Microsoft Store accepts a four-part MSIX version, but the revision component
# must remain zero. Keep the product version in the first three components.
PACKAGE_VERSION = f"{VERSION}.0"
UI_TRACK = "pass8"
UI_VERSION = f"{VERSION}-{UI_TRACK}-b{BUILD_NUMBER}"
UI_PASS_MARKER = "v8.0.10-pass8"
UI_FOOTER_LABEL = "v8.0.10 Pass 8"

APP_DISPLAY_NAME = "New Hampshire Family Law LLM"
APP_EXECUTABLE_NAME = "NHFamilyLawLLM.exe"
GITHUB_REPOSITORY_URL = "https://github.com/JTAHAI/nh-family-law-llm"
STORE_MISSION_TAGLINE = (
    "Built for New Hampshire families. Open-sourced so every state can build its own verified, "
    "source-grounded edition."
)
FORK_GUIDE_RELATIVE_PATH = "docs/FORK_FOR_YOUR_STATE.md"
PRIVACY_POLICY_RELATIVE_PATH = "docs/PRIVACY_POLICY_MICROSOFT_STORE.html"
