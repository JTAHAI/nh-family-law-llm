# New Hampshire legal-behavior contract

The deterministic behavior engine is an issue spotter and evidence router. It does not decide facts, predict judicial outcomes, create attorney-client relationships, select an official form number without a verified live catalog, or calculate an enforceable support amount.

## Input lanes

- `parenting`: order posture, requested scope, RSA 461-A:11 gate facts, decision-making, relocation, and enforcement.
- `support`: issuer, order date, changed circumstances, ordered annual parenting percentages, income-similarity facts, cost sharing, and deviation evidence.
- `support_order`: signed court order, RSA 161-C notice/decision, or collection-only evidence.
- `interstate`: issuing state, residence history, emergency facts, parallel proceedings, and support-order state.
- `safety`: escalation marker only; the engine does not determine whether abuse occurred.

## Output guarantees

Every legal finding carries authority IDs; required authorities must be current-verified, retrieval eligible, effective on the analysis date, locally present, and hash valid. Missing or unverified authority creates a blocker. Reported facts stay reported facts. Existing orders are treated as enforceable until authorized modification, stay, or supersession.

## Interfaces

```bash
nhfl behavior --input examples/pass06_parenting_support_review.json
```

```http
POST /api/legal-behavior/analyze
```

Both return `nh_family_law_llm.legal_behavior_report.v1` and remain review-required.
