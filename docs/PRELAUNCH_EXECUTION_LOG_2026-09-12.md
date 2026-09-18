# Prelaunch execution log — 2026-09-12 (America/New_York)

This is an implementation record, not a legal-currentness certification or a
Microsoft Store submission record.  It preserves the exact restart state for
the remaining prelaunch work.

## Completed technical work

- Corrected three verified General Court source-identity defects in both the
  seed catalog and runtime corpus registry:
  - RSA 463: `XLIV/463/463-mrg.htm`
  - RSA 464-A: `XLIV/464-A/464-A-mrg.htm`
  - RSA 546-B: `LV/546-B/546-B-mrg.htm`
- Added regression tests that bind those citations to their official URL
  identities and require every audited source class to be represented by the
  configured catalog.
- Preserved a full live acquisition attempt outside the repository at
  `D:\NHFamilyLawLLM-authority-data\run-20260912-full-catalog-repaired-r2`.
  It contains 33 raw official responses, their retrieval metadata, and
  SHA-256 hashes.  Its three repaired statutory chapter targets and the
  Chaptered Final Version index returned HTTP 200 and parsed successfully.
  Acquisition timestamps are UTC in the raw manifest.
- Corrected the authority-build audit policy so its source classes exactly
  describe the configured 37-target catalog, while requiring all 37 targets
  (rather than permitting a lower unrelated count).
- Fixed MSIX preflight to accept exactly the supported pair of extensions:
  the `windows.fullTrustProcess` desktop extension and the view-only `nhfl`
  `windows.protocol` extension.  It still rejects any additional namespace,
  category, executable, entry point, or protocol name.
- Updated stale packaging regression tests and the secondary Windows identity
  record to match the configured reserved identity.  The configuration still
  explicitly says that production identity confirmation is false.
- Restored the missing deterministic quality-check entry point and repaired
  its stale catalog and package-data assumptions.  Its passing result is an
  engineering/source-tree check only; it does not represent legal readiness.
- Expanded the conversation safety evaluation corpus from 5 to 22 synthetic,
  non-personal scenarios across intake, drafting, evidence mapping, source
  checking, timeline, filing-readiness, safety, and prompt-injection paths.
  Every deterministic hard-safety metric passes.
- Restored the required unsent outreach tracker schema and one clearly
  redacted example row.  The materials do not claim outreach, attorney review,
  pilot evidence, or legal sign-off.
- Built and qualified the current unsigned essential-tier MSIX:
  `dist/store-submission-v8.0.10-prelaunch-r7/msix/NHFamilyLawLLM_8.0.10.0_x64.msix`.
  Its SHA-256 is
  `37bf5750bfd69b086aeb27824c4c733766e496b3404873b2e5d17bb927b17c51`
  (264,040,160 bytes).  Static manifest, payload, archive, path,
  bundled-engine, and private-data audits pass.
- Corrected the frozen-runtime feature-tier contract.  The sealed essential
  build now reports `essential`, and all applicable feature checks pass under
  the canonical frozen HTTP qualification.  That qualification is still
  blocked—rather than passed—because it is not an installed MSIX run and no
  OS-level zero-network observation was performed.

## Executed evidence

- Authority/source and Store regression selection: **138 passed, 1 skipped**.
- Authority build policy tests: **11 passed**.
- Conversation schema, safety regression, and internal-pilot tests: **6 passed**.
- Product-polish/outreach tracker tests: **5 passed**.
- Quality-check entry point and dependent source-tree tests: **9 passed**.
- Full live acquisition: **33 ingested / 4 failed / 37 requested**.
- External authority build audit: **not production-ready**; it correctly
  reports `minimum_ingested_targets_not_met` and
  `source_class_minimum_not_met`.
- Full project test suite: running fail-fast from
  `dist/qualification/pytest-first-failure-external-r17-20260913/` with its
  temporary workspace outside the repository. It has passed the corrected
  historical GA-tracker expectation and reached 21% at this record update.
  Do not infer final success until stdout/stderr has completed and been
  reviewed.
- The true-GA tracker now reports zero verified completions and 33 remaining
  passes. Historical row labels cannot override its empty audited-completion
  list; the resulting mismatch is an explicit blocker rather than a release
  claim.
- The WACK executable is installed, but the repository runner was blocked by
  the local unsigned-script policy before any elevated WACK session ran. A
  hash-bound `not_run` receipt is retained at
  `dist/store-submission-v8.0.10-prelaunch-r7/evidence/wack/wack-result.json`.

## Active blocks requiring further work or owner evidence

1. NH-0028 through NH-0031 point to retired Judicial Branch rule URLs and
   returned HTTP 404.  Identify the current official rule URLs, preserve their
   raw sources, then subject them to legal/currentness review before promotion.
2. The preserved raw material is not promoted into the shipped authority
   snapshot.  Independent New Hampshire attorney review must verify source
   identity, each proposed proposition, codification, amendments, and effective
   dates before any promotion.
3. The 2026-09-13 pending amendment remains fail-closed: on or after that date
   the old RSA 461-A:6 capsule is blocked until a fresh reviewed source is
   explicitly promoted.  No automatic promotion occurred.
4. Store readiness remains blocked: the r7 preflight is `BLOCKED` for the
   intentionally unperformed installed-package qualification and WACK; the
   identity is configured as
   `TAHAIWebServices.NHFamilyLawLLM` / `TAHAI Web Services`, but its status is
   `reserved_partner_center_identity_submission_not_completed` and
   `production_identity_confirmed` is false.  No signing, WACK result, package
   installation, clean-machine run, Partner Center submission, or Microsoft
   certification has been claimed.

## Next concrete actions

1. Finish and repair the full test suite from the durable log.
2. Run available installed-package and accessibility checks for the current
   unsigned MSIX; record the WACK, Store-signing, and clean-machine limitations
   as blockers rather than treating the static package result as installation
   evidence.
3. After the NH prelaunch gates are exhausted, begin the separately deferred
   ProSe-SENTINEL integration handoff without importing or rebuilding the donor
   product.
