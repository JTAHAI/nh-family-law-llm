# NH curated Qwen 4B / 8B integration

Implementation began from the verified donor inventory on 2026-09-17. Every
one of the 45 donor files matched the SHA-256 values in
`D:\dev\Maine-Family-Law-LLM-github-main\docs\handoffs\NH_4B_8B_DONOR_FILES.json`
at inspection. The donor manifest itself declares `dependency_closure_complete:
false`; its frozen-runtime and legal-quality results are therefore not NH
evidence and have not been imported as such.

Implemented NH integration:

- `curated_ollama_reasoning` accepts only `qwen3:4b` and `qwen3:8b`, uses the
  literal `127.0.0.1:11434` origin, bypasses ambient proxies, rejects redirects,
  and keeps no model resident after an inference request.
- Only `evidence_review` and `drafting` are allowed. Both require exact
  server-rehydrated private-record sources and a fresh approval that binds the
  effective provider, endpoint, model, task, matter, session, and source hashes.
- The model emits strict excerpt JSON. The host validates source index, original
  character offsets, digest, protected-span boundaries, and renders only its own
  exact-record output. Model narrative is withheld. Quote matching does not
  verify relevance, completeness, facts, law, or filing readiness.
- The canonical source and packaged API mirrors advertise the feature as
  `not_legal_qualified`; the production workbench defaults evidence/drafting
  review to curated Qwen and makes the endpoint fixed in that mode.
- Qwen hardware preflight is local-only: 4B needs 6 GiB available RAM or 4 GiB
  available VRAM; 8B needs 10 GiB RAM or 5.5 GiB VRAM; either GPU route also
  requires 2 GiB free system RAM. It does not probe, pull, or admit a model.
- Local-agent audit fallback now uses the existing per-user random OS-protected
  NH vault key instead of a copied development-key label.

Focused source test evidence: `python -m pytest tests/test_qwen_review_hardening.py
tests/test_v540_local_agent_runtime.py tests/test_v540_local_agent_http_adapters.py
tests/test_v540_local_agent_api_ui.py -q` completed with **29 passed** on this
checkout. These are deterministic synthetic tests; no Ollama model was started,
downloaded, or tested, and no private case record was used.

## Explicit remaining gates

- The donor's in-chat installer and setup modules have not been activated in
  NH. Their manifest has an incomplete import closure and Maine-specific state,
  environment, and installer pin labels. Their external installer/model hashes,
  license terms, publisher validation, and current official sources need an NH
  review before an installation route is exposed.
- No actual Qwen inference, production UI exercise, frozen executable test,
  installed-MSIX test, clean-Windows installation, WACK run, model license
  review, NH authority-output review, independent legal review, or Store
  certification has occurred for this feature.
- Private-record quote review remains intentionally separate from the incomplete
  NH authority-currentness work. An authority citation is not accepted as a
  private record, and this feature does not make claims about current NH law.

The concrete restart point is the controlled adaptation of `legal/local_ai/*`
and `app/api/local_ai_setup.py`: first resolve their imports and replace each
Maine namespace/pin with independently verified NH values, then add synthetic
route/UI tests before any optional download path is enabled.
