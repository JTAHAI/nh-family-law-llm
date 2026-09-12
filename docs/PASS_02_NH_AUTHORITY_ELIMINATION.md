# Pass 2 — New Hampshire authority elimination and replacement

**Checkpoint:** 8.0.4 Pass 2
**Generated:** 2026-09-11T16:17:58Z
**Release status:** development checkpoint; not production, GA, or an exhaustive legal corpus

## Objective

Remove active legacy-jurisdiction legal authority, parser, source, fixture, packaging, and release-control assumptions from the New Hampshire fork, then replace them with New Hampshire-native contracts that fail closed until official authority is acquired and reviewed.

## Completed work

- Replaced active legacy statute, court-rule, opinion, form, agency, source-ID, and jurisdiction fixtures with New Hampshire RSA, Judicial Branch, Supreme Court, DHHS/BCSS, and federal-overlay terminology.
- Removed the former jurisdiction-specific connector modules and installed New Hampshire General Court, forms, rules, and Supreme Court opinion connectors.
- Rebuilt guarded query expansion around RSA, NHJB, New Hampshire court terminology, UCCJEA/UIFSA concepts, and direct federal overlays. A query naming another state now suppresses NH synonym injection and returns an explicit review-required jurisdiction status.
- Renamed GA controls, source checks, evaluation labels, parser-regression fixtures, and evidence-stage identifiers to New Hampshire-native names.
- Corrected the Windows launcher and PyInstaller source tree/executable identity to `NHFamilyLawLLM`.
- Added `configs/nh_enterprise_resource_catalog.json` with 40 New Hampshire official-source inventory records. Every record is explicitly a retrieval-ineligible source seed until acquisition and currentness review.
- Replaced the inherited printable bundle with seven generalized New Hampshire family-case planning PDFs in a non-authority toolkit lane.
- Updated current operator documentation, external data-root examples, ingestion commands, privacy policy, Docker boundary, and package metadata for the New Hampshire project.
- Added a fail-closed active legacy-authority scan and a Pass 2 regression suite.

## Authority state at this checkpoint

| Measure | Value |
|---|---:|
| Machine-readable authority manifest records | 37 |
| Enterprise official-source inventory records | 40 |
| `current_verified` records | 0 |
| Retrieval-eligible records | 0 |
| Locally acquired/checksummed authority snapshots | 0 |
| Active legacy-authority scan findings | 0 |

This is deliberate. A URL inventory is not treated as current legal authority. Each official snapshot must be acquired, hashed, effective-date checked, reviewed, and explicitly promoted before retrieval eligibility can become true.

## Validation

- Python compilation across `app`, `legal`, `src`, the root package, and `scripts`: **pass**.
- Pytest collection: **2,598 tests collected** with no collection errors.
- Selected migration/authority/packaging regression set: **209 passed, 1 skipped** across 210 unique tests.
- New Pass 2 regression tests: **6 passed**.
- Application and local-workbench import smoke: **pass**.
- Wheel build and isolated wheel import smoke: **pass**.
- Active legacy-authority scanner: **pass, zero findings** outside approved provenance/history files.
- NH authority audit: **pass**, with expected warnings that no authority is yet current-verified or retrieval-eligible.
- JSON/JSONL parse audit and `git diff --check`: **pass**.
- Full 2,598-test execution: **not completed**; a 300-second run exceeded the available execution window. Collection and the selected regression set are not represented as a full-suite pass.
- Ruff: **not run** because Ruff is not installed in the execution environment.

## Approved residual references

References to the upstream jurisdiction are retained only in clearly labeled provenance/history material and in the terminology crosswalk. The scanner itself necessarily contains the forbidden-marker patterns it enforces. A negative-control test also constructs a non-NH URL to verify that the official-source boundary rejects it.

## Next gate — Pass 3

Pass 3 must perform the full UI/runtime integration pass: verify the new brand on every screen and export, migrate or compatibility-wrap remaining generic `NHFL_*` internal protocol/environment identifiers, validate all launchers and Windows packaging paths, exercise source and frozen-runtime user journeys, and eliminate visual or operational remnants that are not legal-authority content.
