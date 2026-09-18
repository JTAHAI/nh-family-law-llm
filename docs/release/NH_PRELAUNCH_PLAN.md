# NH prelaunch status

Run `python scripts/verify-prelaunch-release.py --output artifacts/release/<run-id>/release-readiness.json` to emit the canonical machine-readable status. The command is deliberately non-promoting and exits nonzero until every required gate has current evidence.

The current state is `NOT_READY`: technical source corrections and unsigned package preparation exist, but official coverage/currentness, independent legal review, installed Windows/accessibility evidence, WACK, and Partner Center/Microsoft evidence remain blocked or not run. See `RELEASE_BLOCKERS.json` for reproducible records and owner dependencies.
