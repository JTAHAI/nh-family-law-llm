#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.nh_family_law.evaluation import run_evaluation
from nh_family_law_llm.version import (
    BUILD_NUMBER,
    PACKAGE_VERSION,
    UI_PASS_MARKER,
    UI_VERSION,
    VERSION,
)



def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    require(tuple(map(int, VERSION.split("."))) >= (8, 0, 9), f"unexpected VERSION {VERSION}")
    require(PACKAGE_VERSION == VERSION + ".0", f"unexpected PACKAGE_VERSION {PACKAGE_VERSION}")
    require(BUILD_NUMBER >= 70, f"unexpected BUILD_NUMBER {BUILD_NUMBER}")
    require(UI_VERSION.startswith(VERSION + "-") and UI_VERSION.endswith(f"-b{BUILD_NUMBER}"), f"unexpected UI_VERSION {UI_VERSION}")
    require(UI_PASS_MARKER.startswith("v" + VERSION + "-"), f"unexpected UI marker {UI_PASS_MARKER}")

    policy = json.loads((ROOT / "configs/nh_pass07_evaluation_policy.json").read_text())
    require(policy["attorney_reviewed"] is False, "engineering eval must not claim attorney review")
    require(policy["release_metric_eligible"] is False, "engineering eval must not claim legal metric eligibility")

    result = run_evaluation().to_dict()
    require(result["status"] == "pass", "one or more Pass 7 evaluation cases failed")
    require(result["summary"]["case_count"] == 34, "unexpected evaluation case count")
    require(result["summary"]["safety_critical_failure_count"] == 0, "safety-critical evaluation failure")

    old_prefixes = (("X-" + "M" + "FLL-").casefold(), ("X-" + "M" + "FL-").casefold())
    allowed = {
        (ROOT / "legal/runtime/transport_headers.py").resolve(),
        Path(__file__).resolve(),
        (ROOT / "tests/test_pass07_nh_evaluation_hardening.py").resolve(),
    }
    hits: list[str] = []
    for directory in ("app", "legal", "nh_family_law_llm", "src", "scripts"):
        for path in (ROOT / directory).rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".ps1", ".sh"}:
                continue
            if path.resolve() in allowed or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            if any(prefix in text for prefix in old_prefixes):
                hits.append(path.relative_to(ROOT).as_posix())
    require(not hits, f"historical transport headers remain active: {hits}")

    output = ROOT / "dist/pass07-evaluation-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "version": VERSION,
        "package_version": PACKAGE_VERSION,
        "build_number": BUILD_NUMBER,
        "case_count": result["summary"]["case_count"],
        "passed": result["summary"]["passed"],
        "failed": result["summary"]["failed"],
        "safety_critical_failure_count": result["summary"]["safety_critical_failure_count"],
        "dataset_sha256": result["dataset_sha256"],
        "result_sha256": result["deterministic_result_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
