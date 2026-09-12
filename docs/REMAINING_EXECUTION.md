# Remaining execution ledger

| ID | Task | Status | Changed files | Evidence / next dependency |
| --- | --- | --- | --- | --- |
| R9-01 | Establish local import checkpoint | complete | `.git/` | `98ddfff` is the ZIP import checkpoint; original Git history was not supplied. |
| R9-02 | Restore missing conversation engineering evaluations | complete | `eval_data/conversation/nh_conversation_eval_cases.json` | Synthetic, non-attorney-reviewed cases include missing facts, safety, interstate scope, and prompt injection. |
| R9-03 | Restore missing user-journey engineering evaluations | complete | `eval_data/user_journeys/nh_user_journey_eval_cases.json` | 27 synthetic journeys; all are engineering fixtures, not gold legal answers. |
| R9-04 | Repair authority acceptance fixture boundary | complete | `scripts/run-ga-authority-acceptance.py`, `tests/test_current_authority_acceptance.py` | Synthetic app and authority roots are separate under repository `dist`; production boundary remains source-root based. |
| R9-05 | Reproduce and resolve reported 16 failures | complete | files above | 34 targeted tests passed on Windows; receipt under `artifacts/release/20260912-regression-repair/`. |
| R10-01 | Acquire and inventory official NH original sources | active | `legal/data_boundaries/storage_layout.py`, `scripts/ingest-nh-authority.py`, `dist/authority-acquisition/run-20260912/` | 37 official seeds validated; 29 original response bodies preserved with metadata and hashes; 8 404/403 gaps retained. Forms and opinions indexes now parse. No record was promoted without substantive/currentness review. |
| R10-02 | Case-law collection and retrieval integration | pending | — | Depends on R10-01 source/provenance inventory. |
| R11-01 | Independent NH legal-review packet and attorney sign-off | pending external gate | — | Engineering packet may be prepared; attorney review cannot be self-certified. |
| R12-01 | Clean dependency resolution and full Windows suite | active | `dist/clean-dependency-env` | Native Windows Python 3.14.3 clean install of `.[api,dev]` and `pip check` passed; full-suite reconciliation remains. |
| R12-02 | Browser, frozen executable, installer/MSIX, signing and clean-machine qualification | active | `store/pyinstaller/nh_family_law_llm.spec`, `store/msix/identity.example.json`, `scripts/build-msix.ps1`, `scripts/qualify_nh_desktop.py`, `dist/store-v3/`, `dist/installed-wheel-browser-qualification/` | Source and isolated installed-wheel Chromium acceptance, essential frozen executable, and final offline unsigned MSIX passed their available gates. Signing, WACK, MSIX installation, and clean-machine evidence remain. |
| R12-03 | Assemble release archive and reconcile final evidence | pending | — | Only after current engineering results are collected. |
