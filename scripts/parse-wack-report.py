#!/usr/bin/env python3
"""Parse a WACK output directory and write hash-bound, fail-closed evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# This parser intentionally needs only the standard library. Import its exact
# implementation without running legal.release.__init__, which loads unrelated
# document/crypto dependencies before a failed native report can be recorded.
_spec = importlib.util.spec_from_file_location(
    "nhfl_standalone_wack_parser", ROOT / "legal/release/wack_qualification.py"
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("wack_parser_implementation_unavailable")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
parse_wack_report = _module.parse_wack_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse WACK output for an exact MSIX package.")
    parser.add_argument("--package", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--execution-status", required=True, choices=("completed", "pass", "failed", "not_run"))
    parser.add_argument("--reason", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = parse_wack_report(package=args.package, output_root=args.output_root, execution_status=args.execution_status, reason=args.reason)
    target = Path(args.output).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
