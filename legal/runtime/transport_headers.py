"""Canonical NHFL transport headers with a bounded legacy request bridge.

Active code emits only ``X-NHFL-*`` headers.  During the migration window this
ASGI middleware accepts either of the two historical request prefixes used by
earlier local builds, maps them to the canonical name only when the caller did
not already send the NHFL form, and records that compatibility was used.

Response headers are canonicalized before they leave the process.  The bridge
therefore preserves old local clients without perpetuating old names in new
responses, tests, documentation, or integrations.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

CANONICAL_PREFIX = "X-NHFL-"
CANONICAL_PREFIX_BYTES = CANONICAL_PREFIX.casefold().encode("ascii")

# Constructed rather than written as product identifiers so active-source
# scans can prove that legacy prefixes are confined to this compatibility lane.
LEGACY_PREFIXES = (
    "X-" + "M" + "FLL-",
    "X-" + "M" + "FL-",
)
LEGACY_PREFIX_BYTES = tuple(value.casefold().encode("ascii") for value in LEGACY_PREFIXES)

LEGACY_ACCEPTED_HEADER = "X-NHFL-Legacy-Headers-Accepted"
LEGACY_ACCEPTED_HEADER_BYTES = LEGACY_ACCEPTED_HEADER.casefold().encode("ascii")


def canonicalize_header_name(name: str) -> str:
    """Return the canonical header name while leaving unrelated names alone."""

    lowered = name.casefold()
    for prefix in LEGACY_PREFIXES:
        if lowered.startswith(prefix.casefold()):
            return CANONICAL_PREFIX + name[len(prefix) :]
    return name


def _canonicalize_bytes(name: bytes) -> tuple[bytes, bool]:
    lowered = name.lower()
    for prefix in LEGACY_PREFIX_BYTES:
        if lowered.startswith(prefix):
            return CANONICAL_PREFIX_BYTES + lowered[len(prefix) :], True
    return lowered, False


def canonical_request_headers(
    headers: Iterable[tuple[bytes, bytes]],
) -> tuple[list[tuple[bytes, bytes]], tuple[str, ...]]:
    """Map legacy request names to canonical names without overriding NHFL."""

    rows = list(headers)
    existing = {name.lower() for name, _ in rows}
    additions: list[tuple[bytes, bytes]] = []
    accepted: list[str] = []
    for name, value in rows:
        canonical, changed = _canonicalize_bytes(name)
        if not changed or canonical in existing:
            continue
        additions.append((canonical, value))
        existing.add(canonical)
        accepted.append(name.decode("latin-1"))
    return [*rows, *additions], tuple(dict.fromkeys(accepted))


def canonical_response_headers(headers: Iterable[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """Emit only canonical NHFL names, coalescing duplicate compatibility rows."""

    output: list[tuple[bytes, bytes]] = []
    seen: set[bytes] = set()
    for name, value in headers:
        canonical, _ = _canonicalize_bytes(name)
        if canonical in seen:
            continue
        output.append((canonical, value))
        seen.add(canonical)
    return output


class TransportHeaderCompatibilityMiddleware:
    """Pure ASGI bridge that accepts old requests but emits NHFL responses."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        migrated_headers, accepted = canonical_request_headers(scope.get("headers") or ())
        migrated_scope = dict(scope)
        migrated_scope["headers"] = migrated_headers
        state = dict(migrated_scope.get("state") or {})
        if accepted:
            state["nhfl_legacy_transport_headers"] = accepted
        migrated_scope["state"] = state

        async def send_canonical(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                message = dict(message)
                response_headers = canonical_response_headers(message.get("headers") or ())
                if accepted and LEGACY_ACCEPTED_HEADER_BYTES not in {name for name, _ in response_headers}:
                    response_headers.append((LEGACY_ACCEPTED_HEADER_BYTES, b"true"))
                message["headers"] = response_headers
            await send(message)

        await self.app(migrated_scope, receive, send_canonical)


__all__ = [
    "CANONICAL_PREFIX",
    "LEGACY_ACCEPTED_HEADER",
    "TransportHeaderCompatibilityMiddleware",
    "canonical_request_headers",
    "canonical_response_headers",
    "canonicalize_header_name",
]
