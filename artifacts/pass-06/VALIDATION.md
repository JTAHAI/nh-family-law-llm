# Pass 6 validation receipt

**Version:** 8.0.8  
**Package version:** 8.0.8.0  
**Build:** 60  
**Branch:** `pass-06-nh-legal-behavior`  
**Feature commit:** `48ddddbf7003bee1d27b0b616bfd8c14fd5e5b9c`  
**Generated:** 2026-09-11

## Result

The New Hampshire legal-behavior source checkpoint passed its defined source gates. It remains review-required and is not represented as attorney-validated, filing-ready, or a completed Windows/MSIX release.

| Gate | Result |
|---|---:|
| Python compilation | **PASS** |
| Pass 4 authority integrity gate | **PASS** |
| Pass 6 legal-behavior gate | **PASS** |
| Active Maine-authority scan | **PASS — 0 findings** |
| Legacy runtime scan | **PASS** |
| Core behavior/authority regression | **44 passed** |
| Version and UI regression | **85 passed** |
| Pytest collection | **2643 tests across 532 files** |
| Exact private-identifier scan | **PASS — 0 findings** |
| Ruff | **UNAVAILABLE** |
| Full test suite | **INCOMPLETE — no pass claimed** |

## Authority state

- 76 manifest records.
- 37 current-verified, retrieval-eligible core capsules.
- 2 future-effective pending overlays.
- 0 authority promotions in Pass 6.
- RSA 546-B/UIFSA remains fail-closed because the current record is an unverified source seed.

## Behavior boundaries

The engine performs deterministic issue spotting, evidence-gap identification, authority gating, and procedural routing. It does not calculate an enforceable support amount, decide contested facts, guarantee equal parenting or a support reduction, select an unverified form number, or authorize noncompliance with an existing order.

## Remaining release work

- Complete the broad official-source acquisition and legal-review corpus.
- Replace remaining inherited `X-MFLL-*` compatibility headers on legacy endpoints through a documented transition.
- Run complete regression, adversarial legal-answer evaluation, Windows frozen-runtime, MSIX, signing, WACK, and clean-machine qualification.
