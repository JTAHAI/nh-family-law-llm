# New Hampshire Family Law LLM — Pass 8 checkpoint

**Version 8.0.10 · Build 80 · Four further passes planned.**

Start with **docs/PASS_08_DESKTOP_INTEGRATION.md**. The new `/nh-review` screen is
wired to the existing source-gated NH behavior engine and included in the Python
wheel. Source and installed-package HTTP journeys passed, but this is **not a
production-qualified application or a signed Windows installer**.

Current evidence is under `artifacts/pass-08`. Earlier pass receipts remain
historical. The wider batches still have 16 failures; pinned dependency install,
browser navigation, frozen Windows/MSIX, signing, WACK and clean-machine gates
are not qualified. Do not reinterpret source checks as those missing results.

No authorities were promoted. The corpus still contains reviewed non-verbatim
capsules and unverified inventory, not an exhaustive collection of NH law. Human
legal review remains required; no output is filing-ready or an enforceable child
support calculation.

A validated Python wheel is included in `installables/`. Use the source guide for
installation and launch commands. It requires its declared Python dependencies.
See `NEXT_PASS.md` for the next work item and carried-forward blockers.
