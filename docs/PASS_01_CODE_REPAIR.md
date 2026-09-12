# Pass 01 — New Hampshire code repair

**Checkpoint:** 8.0.3 Pass 1  
**Date:** 2026-09-11  
**Status:** Complete as a development checkpoint; not a release candidate or GA build.

## Objective

Make the mechanically rebranded project executable again before performing the full Maine-authority elimination and New Hampshire-authority replacement pass.

## Repairs completed

- Repaired invalid Python identifiers created by literal jurisdiction-name replacement, including the authority reranker, findings/forms store, and workbench component names.
- Restored required generic runtime modules that had been removed during the first migration attempt, then adapted package imports for the New Hampshire namespace.
- Restored complete pytest collection by adding temporary compatibility bridges for older parser and workbench imports. Those bridges are deliberately visible and are scheduled for removal or NH-native replacement in Pass 2.
- Added `data/sources/manifest.seed.json` with seven New Hampshire fixture records: six official-source fixtures and one clearly labeled synthetic secondary fixture.
- Replaced the live-fetch host boundary with New Hampshire and directly relevant federal official domains. Former Maine government domains are rejected by the Pass 1 boundary test.
- Replaced the live-fetch user agent with the New Hampshire project identity.
- Added `nhfl` and `nhfl-fast-interchange-worker` console entry points while retaining temporary upstream command aliases for compatibility.
- Corrected project citation metadata, product version metadata, application titles, and release notes for the NH development checkpoint.
- Added `tests/test_pass01_nh_code_repair.py` to lock the application identity, NH-only fixture manifest, and official-domain boundary.
- Kept unreviewed authority seeds ineligible for legal retrieval. This pass does not promote any source to verified-current authority.

## Restored compatibility modules

The following runtime modules were restored because their absence prevented import or test collection. Several still contain Maine-era fixtures or names and are therefore migration inputs—not finished NH legal content:

- `legal/addons/workbench.py`
- `legal/authority_store/parsed_store.py`
- `legal/connectors/maine_forms.py`
- `legal/connectors/maine_revisor.py`
- `legal/connectors/maine_rules.py`
- `legal/connectors/maine_sjc_opinions.py`
- `legal/connectors/official_source_catalog.py`
- `legal/evals/evaluation_orchestrator.py`
- `legal/law_court/intelligence.py`
- `legal/product/family_first_chat_v204.py`
- `legal/product/family_justice_workbench_v205.py`
- `legal/product/filing_gate_studio_v203.py`
- `legal/production/data_product_readiness.py`
- `legal/production/followup_targets.py`
- `legal/resources/offline_validation_pack.py`
- `legal/security/legal_red_team.py`
- `legal/verifiers/authority_status_verifier.py`
- `legal/verifiers/citation_parser.py`

## Validation results

| Check | Result |
|---|---:|
| Python compileall across application, scripts, and tests | PASS |
| Pytest collection | PASS — 2,592 tests collected |
| Focused migration execution suite | PASS — 90 tests |
| Service/API import smoke | PASS |
| New Hampshire fixture fetch/normalize/draft smoke | PASS |
| Python wheel build from sanitized source tree | PASS |
| New Hampshire authority audit | EXPECTED FAIL — 49 residual legacy-authority findings |
| Legacy authority scan | EXPECTED FAIL — 38 residual marker hits |
| Complete 2,592-test execution | NOT YET RUN TO COMPLETION |
| Ruff lint | NOT RUN — Ruff is not installed in this runtime |

The residual scan failures are not hidden. They define the work queue for Pass 2.

## Known limitations after Pass 1

1. The runtime still contains Maine-era authority fixtures, parser class names, citation examples, URLs, FOCAF inventory content, and associated tests.
2. The 37-record NH authority inventory is a source seed. It does not yet contain a fully downloaded, independently reviewed, current statewide authority corpus.
3. Some compatibility modules use Maine-oriented filenames so upstream imports continue to work. Pass 2 will replace call sites with NH-native modules and remove these bridges.
4. The entire inherited test suite has been collected successfully, but only the focused migration suite has been executed as the Pass 1 gate.
5. No child-support calculator or legal outcome predictor is represented as NH-validated.

## Pass 2 gate

Pass 2 must reduce both authority scans to zero outside explicitly permitted provenance/crosswalk files, replace Maine legal fixtures with NH authorities and synthetic NH test records, rename parser/corpus modules, and then rerun the affected authority, retrieval, drafting, and UI tests.

## Privacy boundary

No private message screenshot, phone number, party name, or identifying facts about the user’s brother are included in this repository.
