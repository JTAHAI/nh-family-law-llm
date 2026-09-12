# Pass 3 — UI, Runtime, Protocol, and Windows Identity Integration

**Date:** 2026-09-11  
**Version:** 8.0.5  
**Scope:** Source-level NH application identity and compatibility migration.

## Implemented

- Canonical NH product and export metadata module.
- NH-native protocol namespace, URI scheme, media type, and JSON schema.
- Active environment namespace migration from inherited identifiers to `NHFL_*`.
- Isolated, non-overriding, warning-emitting compatibility bridge.
- Granite/navy/red visual tokens, accessible focus styling, SVG application mark,
  banner assets, and static brand preview.
- Frontend document-title, favicon, theme, and brand-rail integration where HTML
  entry points were present.
- Windows AUMID/application/protocol source identities and an Appx manifest
  template.
- Windows verification script and evidence matrix; package/signing/WACK claims
  remain explicitly unverified until run on Windows.
- Source-mode identity/protocol/export smoke journey and focused regression tests.
- GitHub source gates for compilation, tests, and NH identity verification.

## Deliberate boundaries

This pass does not promote any legal source into `CURRENT_AUTHORITY`, does not
claim WACK/MSIX success, and does not claim that a source template is a signed
installer. The legal corpus remains fail-closed until the authority-acquisition
and legal-review passes.
