# 8.0.9 — NH evaluation and transport hardening

Pass 7 adds a synthetic, operator-source-backed regression suite for the New Hampshire legal-behavior engine. It exercises parenting modification, child support, court-versus-DHHS routing, interstate issues, stale authority, unsupported conclusions, jurisdiction contamination, and safety controls. The suite is engineering evidence only: it is not attorney-reviewed gold, a legal-accuracy metric, or filing approval.

The active API and local-workbench transport namespace is now `X-NHFL-*`. Historical request headers are accepted only by a bounded compatibility middleware, canonical NH headers take precedence, and responses emit only the NH namespace.

No authority was promoted and no Windows package, Store, attorney-validation, or filing-ready claim is made.

# 8.0.8 — NH legal behavior

- Added gate-first parenting modification analysis, child-support review, court/DHHS routing, UCCJEA/UIFSA triage, drafting controls, API/CLI interfaces, and focused regression tests.
- No new legal authority was promoted in this pass.

# New Hampshire authority migration checkpoint — 8.0.4 Pass 2 — 2026-09-11

This development checkpoint completes the active legal-authority elimination/replacement pass. It is not a production or GA claim.

- Reduced the active legacy-authority scanner to zero findings outside explicit provenance/history exceptions.
- Replaced former jurisdiction-specific connectors, source IDs, legal terminology, release controls, opinion parsing, fixtures, and operator commands with New Hampshire-native equivalents.
- Added a 40-record NH enterprise source inventory and retained 37 machine-readable authority-manifest records as retrieval-ineligible seeds.
- Rebuilt jurisdiction-aware query expansion around RSA/NHJB terminology and direct federal overlays.
- Corrected `NHFamilyLawLLM` launcher and PyInstaller identity paths.
- Replaced the inherited printable resource bundle with seven generalized NH planning aids that are explicitly non-authority.
- Added current NH Microsoft Store privacy documentation and repaired container/data-root boundaries.
- Collected 2,598 tests and passed a selected 210-test migration/authority/packaging set with one skip.
- Built and import-tested the 8.0.4 wheel.

No official-source record is yet marked current-verified or retrieval-eligible. Authority acquisition, effective-date review, and explicit promotion remain later passes.

---

# New Hampshire code-repair checkpoint — 8.0.3 Pass 1 — 2026-09-11

- Repaired invalid identifiers and imports introduced by the initial automated jurisdiction migration.
- Restored test collection and an executable NH development baseline.
- Established an NH/federal source boundary and fail-closed seed-authority behavior.
- Left the legacy-authority elimination queue visible for Pass 2.
