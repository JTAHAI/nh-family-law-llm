# Pass 4 — Reviewed New Hampshire Authority Snapshot

**Date:** 2026-09-11  
**Version:** 8.0.6

## Completed

- Added 37 current, section-scoped, checksum-backed NH authority capsules.
- Added 2 future-effective capsules with explicit non-activation.
- Covered core child-support, parenting, administrative-support, and UCCJEA provisions.
- Added official RSA and administrative-rule currentness methodology.
- Added acquisition-blocker receipts for Judicial Branch and DHHS materials and for the unavailable raw-response preservation channel.
- Added a runtime manifest loader that enforces status, effective date, scope, and checksum.
- Added deterministic JSON/JSONL/CSV projection and a Pass 4 verifier/test suite.

## Preservation model

The acquisition environment could read normalized official-page text through a web retrieval layer but could not preserve original response bodies. Therefore:

- every capsule says `raw_source_bytes_preserved=false`;
- its SHA-256 covers the local normalized capsule;
- source-grounded extracts are short, condensed, and section-scoped;
- structured summaries are bounded by that section;
- each record links back to the official page; and
- consequential use requires fresh source checking.

## Not complete

Court rules/forms, DHHS schedules, full administrative rules, case law, UIFSA, domestic violence, adoption, guardianship, child protection, and the rest of the statewide authority map remain for later passes. This checkpoint must not be described as exhaustive.
