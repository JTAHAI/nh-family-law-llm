from __future__ import annotations


class LegalBehaviorError(RuntimeError):
    """Base class for deterministic legal-behavior failures."""


class InvalidLegalBehaviorInput(LegalBehaviorError, ValueError):
    """The caller supplied an invalid fact envelope."""


class AuthoritySnapshotUnavailable(LegalBehaviorError):
    """Required authority metadata or local source bytes failed closed."""
