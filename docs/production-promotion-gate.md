# Production promotion gate

The production promotion gate is the final hard blocker between local/source testing and any claim that the New Hampshire Family Law LLM is production-legal-ready.

Run it only after the external data root has been populated with live official New Hampshire authority, parsed authority stores, retrieval indexes, attorney-reviewed gold evals, measured metrics, pilot/security evidence, rollback evidence, and owner signoffs.

```powershell
cd C:\dev\NH_FAMILY_LAW_LLM
python scripts\run-networked-source-gate.py --data-root C:\dev\NH_FAMILY_LAW_LLM_data
python scripts\run-production-promotion-gate.py --data-root C:\dev\NH_FAMILY_LAW_LLM_data
```

For handoff/report generation before those materials exist:

```powershell
python scripts\run-production-promotion-gate.py --data-root C:\dev\NH_FAMILY_LAW_LLM_data --allow-fail-report
```

A failing report is expected during local fixture testing. It means the source tree may be test-ready, but production promotion remains locked.
