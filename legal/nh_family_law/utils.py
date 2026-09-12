from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

Tri = Literal["yes", "no", "unknown"]


def tri(value: Any) -> Tri:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"yes", "true", "y", "1", "known_yes"}:
            return "yes"
        if normalized in {"no", "false", "n", "0", "known_no"}:
            return "no"
    return "unknown"


def clean_text(value: Any, *, limit: int = 10_000) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    return text[:limit]


def parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = clean_text(value, limit=32)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def years_between(start: date, end: date) -> float:
    return (end - start).days / 365.2425


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result
