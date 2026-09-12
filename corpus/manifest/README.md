# NH authority manifest

`nh_authorities.json` is canonical. JSONL and CSV are deterministic projections.

Pass 4 adds section-scoped records with these safeguards:

- `status=current_verified` plus `retrieval_eligible=true` only for effective, reviewed capsules.
- `status=future_effective_pending` remains ineligible even after its date until an explicit fresh-source review and promotion.
- `sha256` covers the local normalized capsule, not the remote page.
- `raw_source_bytes_preserved=false` prevents the system from representing a capsule as a byte-for-byte source archive.
- `retrieval_scope=capsule_only` prevents chapter-wide completeness claims.
- `answer_scope=source_currentness_only` prevents source-governance guidance from being used as substantive family law.
