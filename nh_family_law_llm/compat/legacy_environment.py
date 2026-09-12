"""Compatibility bridge for environment variables used by the Maine upstream.

The New Hampshire application owns the ``NHFL_`` namespace.  During the
migration window, a value supplied only under the former namespace is copied
to its NHFL equivalent once, before the rest of the package reads settings.
The bridge never overwrites an explicitly supplied NHFL value and emits a
deprecation warning.  Remove this module only in a future documented major
release.
"""
from __future__ import annotations

import os
import warnings
from collections.abc import MutableMapping

CURRENT_PREFIX = "NHFL_"
# Constructed to keep legacy identifiers isolated to this compatibility file.
LEGACY_PREFIX = "M" + "FL_"

KNOWN_SUFFIXES: tuple[str, ...] = (
    "ACCESSIBILITY_BIAS_EVAL_ROOT",
    "ADMIN_CONSOLE_ROOT",
    "AUDIT_VERIFICATION_ROOT",
    "AUTHORITY_DATA_ROOT",
    "AUTHORITY_TRUST_STORE",
    "AUTHORITY_UPDATE_INBOX",
    "AUTHORITY_UPDATE_ROOT",
    "BACKUP_ROOT",
    "CASE_LIBRARY_PATH",
    "CHILD_CONTINUITY_KEY",
    "CLAIM_SUPPORT_EVAL_ROOT",
    "CLAIM_SUPPORT_PARSED_AUTHORITY_ROOT",
    "CLAIM_SUPPORT_SOURCE_TEXT_JSONL",
    "COMMUNICATIONS_KEY",
    "CONFIGURATION_EXPORT_ROOT",
    "CONFIGURATION_EXPORT_TRUST",
    "DOCLING_ARTIFACTS_PATH",
    "ENABLE_EXPERIMENTAL_SLICES",
    "ENABLE_EXPERIMENTAL_SLICES_21_31",
    "EVAL_ROOT",
    "EXTENSION_TRUST_CONFIG",
    "FAST_INTERCHANGE_",
    "FAST_INTERCHANGE_ADMISSION_CATALOG",
    "FAST_INTERCHANGE_ADMISSION_TRUST",
    "FAST_INTERCHANGE_ALLOW_CPU",
    "FAST_INTERCHANGE_ARTIFACT_REGISTRY",
    "FAST_INTERCHANGE_ARTIFACT_ROOT",
    "FAST_INTERCHANGE_BUNDLED_PACK_ROOT",
    "FAST_INTERCHANGE_CPU_THREADS",
    "FAST_INTERCHANGE_CUDA_DEVICE",
    "FAST_INTERCHANGE_FORCE_CPU",
    "FAST_INTERCHANGE_HOST",
    "FAST_INTERCHANGE_PACK_ROOT",
    "FAST_INTERCHANGE_PORT",
    "FAST_INTERCHANGE_RELEASE_REGISTRY",
    "FAST_INTERCHANGE_STATE_ROOT",
    "FAST_INTERCHANGE_TRUST_POLICY",
    "FAST_INTERCHANGE_WORKER_TOKEN",
    "FORCE_AVX512",
    "GA_EVIDENCE_ROOT",
    "GA_HARDENING",
    "GA_INSTALLED_OFFLINE",
    "GA_MSIX",
    "GA_RUNTIME",
    "GOVERNANCE_EVIDENCE_ROOT",
    "GPU_NAME",
    "HUMAN_EVAL_ROOT",
    "IDEMPOTENCY_STATE_ROOT",
    "JURISDICTION_PACK_ROOT",
    "JURISDICTION_PACK_STATE_ROOT",
    "LEGAL_HOLD_ROOT",
    "LOCAL_API_INSTANCE_ID",
    "LOCAL_API_STATE_PATH",
    "LOCAL_MUTOOL",
    "LOCAL_PDFTOPPM",
    "LOCAL_TESSERACT",
    "LONGITUDINAL_MATTER_EVAL_ROOT",
    "MATTER_ROOT",
    "MINIMUM_WRITE_RESERVE_BYTES",
    "MODEL_ARTIFACT_ROOT",
    "MODEL_STORE_ROOT",
    "OFFLINE_ENTITLEMENT_ROOT",
    "OFFLINE_ENTITLEMENT_TRUST",
    "ORGANIZATION_READINESS_ROOT",
    "PDF_PREVIEW_EPHEMERAL_KEY",
    "POLICY_PACK_TRUST_CONFIG",
    "PROCEDURAL_SAFETY_EVAL_ROOT",
    "PROJECT_ROOT",
    "PROVIDER_STORE_ROOT",
    "PUBLIC_API_CONTRACT_ROOT",
    "QA_FAILURE",
    "QA_SCRIPT",
    "QDRANT_URL",
    "QUOTE_BENCHMARK_AUTHORITY_INDEX",
    "QUOTE_BENCHMARK_EVAL_ROOT",
    "QUOTE_BENCHMARK_PARSED_AUTHORITY_ROOT",
    "QUOTE_BENCHMARK_SOURCE_TEXT_JSONL",
    "RELEASE_CLOSURE_EVIDENCE_ROOT",
    "RELEASE_CLOSURE_MSIX_PATH",
    "RELEASE_METRIC_ELIGIBILITY_ROOT",
    "REQUIRE_IDEMPOTENCY_KEYS",
    "RETENTION_APPROVAL_CONFIG",
    "RETENTION_ENGINE_ROOT",
    "ROLE_POLICY_SIMULATION_ROOT",
    "RUNTIME_LOG_DIR",
    "RUNTIME_MODE",
    "RUNTIME_ROOT",
    "RUNTIME_STATE_ROOT",
    "SECURITY_BACKUP_ROOT",
    "SEPARATION_OF_DUTIES_ROOT",
    "SESSION_SIGNING_SECRET",
    "SIGNED_POLICY_PACK_ROOT",
    "STORE_BUNDLED_SPECIALIST_PACK_ROOT",
    "STORE_BUNDLED_SPECIALIST_VALIDATION",
    "STORE_DEBUG_CONSOLE",
    "STORE_FEATURE_TIER",
    "TRANSFER_ROOT",
    "USE_ACTIVE_AUTHORITY_IN_SOURCE",
    "VAULT_KEY_ROOT",
    "VRAM_BYTES",
    "WHISPER_BUNDLE_ROOT",
    "WHISPER_COMMAND_JSON",
    "WHISPER_DISABLE_BUILTIN",
    "WHISPER_E2E_WAV",
    "WHISPER_TOOL_ROOT",
)

def apply_legacy_environment_aliases(
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy legacy values into the NHFL namespace without overriding NHFL."""
    env = os.environ if environ is None else environ
    applied: dict[str, str] = {}
    for suffix in KNOWN_SUFFIXES:
        old_name = f"{LEGACY_PREFIX}{suffix}"
        new_name = f"{CURRENT_PREFIX}{suffix}"
        if new_name in env or old_name not in env:
            continue
        env[new_name] = env[old_name]
        applied[old_name] = new_name
    if applied:
        warnings.warn(
            "Legacy environment variables were mapped to NHFL_* names: "
            + ", ".join(f"{old}->{new}" for old, new in sorted(applied.items())),
            DeprecationWarning,
            stacklevel=2,
        )
    return applied
