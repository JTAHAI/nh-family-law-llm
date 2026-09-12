"""Strict view-only protocol activation. No command, file, or remote URL input."""
from __future__ import annotations

from urllib.parse import urlsplit

_TARGETS = {"review": "nh-review", "workbench": "workbench"}


def protocol_view(uri: str) -> str:
    if not isinstance(uri, str) or not 1 <= len(uri) <= 128:
        raise ValueError("invalid_protocol_uri")
    if any(ch.isspace() or ord(ch) < 32 for ch in uri) or any(ch in uri for ch in ('%', '\\', '"', "'")):
        raise ValueError("invalid_protocol_uri")
    parsed = urlsplit(uri)
    if parsed.scheme != "nhfl" or parsed.netloc not in _TARGETS:
        raise ValueError("invalid_protocol_uri")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("invalid_protocol_uri")
    return _TARGETS[parsed.netloc]
