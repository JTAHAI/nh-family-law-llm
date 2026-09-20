# NH prelaunch status

Run `python scripts/verify-prelaunch-release.py --package dist/store-submission-v8.0.10-partner-identity-r6/msix/NHFamilyLawLLM_8.0.10.0_x64.msix --output artifacts/release/<run-id>/release-readiness.json` to emit the canonical machine-readable status for the exact candidate. The command is deliberately non-promoting and exits nonzero until every required gate has current evidence.

The current state is `NOT_READY`: the September 20, 2026 full repository run recorded 2,551 passed, 156 failed, and 23 skipped. Technical source corrections and unsigned package preparation exist, but full regression repair, official coverage/currentness, independent legal review, installed Windows/accessibility evidence, WACK, and Partner Center/Microsoft evidence remain blocked or not run. See `RELEASE_BLOCKERS.json` for reproducible records and owner dependencies.
