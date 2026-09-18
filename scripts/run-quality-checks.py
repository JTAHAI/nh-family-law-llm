#!/usr/bin/env python3
"""Run deterministic source-tree quality checks.

This command validates engineering safeguards and emits a machine-readable
report.  A passing result is not a legal-readiness or attorney-review claim;
external authority acquisition, currentness, and independent review remain
separate fail-closed gates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.evaluation_orchestrator import EvaluationOrchestrator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic NH Family Law LLM quality checks.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    args = parser.parse_args()

    report = EvaluationOrchestrator(args.repo_root).run_all()
    if args.output:
        output = args.output if args.output.is_absolute() else args.repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
