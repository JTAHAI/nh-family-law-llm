"""Open-source New Hampshire Family Law LLM workbench package."""


from .compat.legacy_environment import apply_legacy_environment_aliases as _apply_legacy_environment_aliases
_apply_legacy_environment_aliases()
del _apply_legacy_environment_aliases

from .version import VERSION

__all__ = ["__version__"]

__version__ = VERSION
