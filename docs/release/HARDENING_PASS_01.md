# Engineering hardening pass 01 — vault and storage boundaries

Status: NOT_READY. Engineering-only work; no legal review, authority promotion,
installed-MSIX qualification, WACK result, or Store submission is represented.

## Source provenance

Started from master `4b44401a31271d84cf218cdb4a4c615081d596d0`.
An isolated tracked-source snapshot was obtained through branch bootstrap commit
`f4338ffb4f8dd30dc663237debc75f7d61e1375e`; its extracted Git tree matched
`d79a96ab1f13e7bbf7e4e4627cbf48b94f629574` exactly. The temporary bootstrap
workflow is replaced by the Windows/Linux storage-regression workflow.
No user Windows checkout, ignored release artifact, model weight, or Maine
repository was modified.

## Changes

- Serialize uncached vault initialization with the existing cross-process
  sidecar lock. Recheck the key after acquiring the lock; never replace an
  unreadable, invalid, or linked existing key. Cache only validated secrets.
- Validate default and explicit deliberation roots through the same boundary
  checks, before directory creation. Reject linked ancestors, dangling links,
  and Windows reparse points rather than resolving away their identity.
- Initialize the deliberation host on demand under a thread lock. A rejected
  default returns a sanitized, review-required 503 for that feature instead of
  crashing router import. Failed initialization remains retryable.
- Assert the exact key-plus-lock inventory in the existing encryption and PDF
  tests. Keep the Windows assertion that the persisted key is DPAPI-protected.
- Add an explicit Windows/Linux regression workflow using the unchanged
  declared application dependencies and synthetic PDF test dependencies.
  Only JUnit and dependency inventory files are uploaded, never fixture stores.

The sidecar lock is intentionally persistent: deleting it while processes can
be waiting would permit different processes to lock different files. This
change does not alter the envelope format or regenerate existing vault keys.

## Verification performed before publication

The new vault/root tests failed against the original modules: 23 failed,
2 passed. After repair, those tests and the four existing encryption tests
passed: 29 passed. Three deterministic spawned-process runs reproduce the
old overwrite ordering and verify shared-key restart decryption after repair.

The startup regressions initially failed: 4 failed. With lazy host acquisition,
the startup regressions plus the existing deliberation workspace suite passed:
6 passed. The final combined selected run passed: **85 passed, 0 failed**.
No assertion or test was skipped in that local run.

Command (run with HOME, USERPROFILE, LOCALAPPDATA, TEMP, TMP and TMPDIR pointed
at explicitly owned paths beneath this checkout's dist directory):

```text
python -m pytest tests/test_pass01_vault_storage_hardening.py tests/test_pass01_deliberation_startup.py tests/test_matter_vault_encryption.py tests/test_pdf_raster_preview.py tests/test_v540_local_agent_runtime.py tests/test_v540_local_agent_api_ui.py tests/test_deliberation_workspace.py --basetemp=dist/pass01/final-tmp --junitxml=dist/pass01/final-junit.xml -ra --tb=short
```

Local environment: Linux, Python 3.13.5, pytest 9.0.2. Preinstalled libraries
include cryptography 46.0.4, FastAPI 0.128.2, Starlette 0.50.0, pypdf 5.9.0,
and pypdfium2 5.8.0. These do not satisfy all pinned/current dependency floors;
therefore the local results are NOT declared-dependency or Windows/DPAPI
qualification. Dependencies were not relaxed. The new GitHub workflow must
supply independent results for the actual pushed commit on both platforms.

## Remaining work

The full regression suite has not been rerun or declared passing by this pass.
The existing release blocker ledger and r12 artifact reference remain unchanged.
Address the broader qualification harness, existing failing workflows, and
remaining storage initializers in subsequent passes. In particular, the
provider-connection store has a separate default-root resolver that needs its
own audit; this pass does not claim all external-store paths have been reviewed.
Current-law acquisition, independent legal review, installed Windows lifecycle,
accessibility, offline/network qualification, WACK, and submission authorization
remain separate unresolved gates.
