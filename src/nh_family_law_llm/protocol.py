"""NH-native application and evidence interchange identifiers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PROTOCOL_ID: Final = "nhfl"
PROTOCOL_VERSION: Final = "1.0"
URI_SCHEME: Final = "nhfl"
URN_PREFIX: Final = "urn:nhfl:"
MEDIA_TYPE: Final = "application/vnd.nhfl.evidence+json"
SCHEMA_ID: Final = "https://schemas.nh-family-law-llm.local/evidence/v1.json"

@dataclass(frozen=True, slots=True)
class ProtocolEnvelope:
    kind: str
    version: str = PROTOCOL_VERSION
    jurisdiction: str = "NH"

    def urn(self, identifier: str) -> str:
        clean = identifier.strip()
        if not clean:
            raise ValueError("identifier must not be empty")
        return f"{URN_PREFIX}{self.kind}:{clean}"
