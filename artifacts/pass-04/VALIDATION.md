# Pass 4 Validation Receipt

**Version:** 8.0.6  
**As of:** 2026-09-11  
**Status:** **PASS**

## Reviewed authority snapshot

- Manifest records: **76**
- Current-reviewed and retrieval eligible: **37**
- Future-effective and inactive: **2**
- Unverified source seeds retained: **37**
- Local current/future capsules: **39**
- Embedded package records: **39**
- Remote raw response bodies preserved: **0**
- Acquisition blocker receipts: **3**

Coverage claim: `section-verified core capsule snapshot; exhaustive statewide coverage is not asserted`

## Executed test batches

| Batch | Tests | Passed | Failures | Errors | Skipped | Result |
|---|---:|---:|---:|---:|---:|---:|
| `authority_migration` | 29 | 29 | 0 | 0 | 0 | **PASS** |
| `nhfl_specialist_renames` | 174 | 172 | 0 | 0 | 2 | **PASS** |
| `privacy_and_runtime` | 29 | 29 | 0 | 0 | 0 | **PASS** |
| `release_metadata` | 19 | 19 | 0 | 0 | 0 | **PASS** |

Pytest collection completed for **2615 tests across 531 files**. The complete 2,615-test suite is not claimed as executed; the pass-specific and migration-sensitive batches above are the execution evidence.

## Source and release gates

- Authority-manifest rebuild: **PASS**
- Pass 4 capsule verifier: **PASS**
- NH authority audit: **PASS**
- Pass 3 identity/protocol gate: **PASS**
- Active legacy-runtime scan: **PASS**
- Python compilation: **PASS**
- Release feature-truth validation: **PASS**
- Git whitespace check: **PASS**
- Private-case/localization marker scan: **PASS**
- Ruff: **NOT RUN — module unavailable**
- Windows frozen/MSIX/WACK/clean-machine validation: **NOT RUN**

## Honest boundary

The active records are condensed, section-scoped, non-verbatim research capsules grounded in official New Hampshire General Court pages. They are not byte-for-byte page archives and do not establish exhaustive NH family-law coverage. Three blocker receipts preserve unavailable Judicial Branch, DHHS/BCSS, and raw-response acquisition instead of silently substituting mirrors or secondary calculators.
