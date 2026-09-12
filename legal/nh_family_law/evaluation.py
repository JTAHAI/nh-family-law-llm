"""Deterministic engineering evaluation harness for NH legal behavior.

This suite is intentionally *not* attorney-reviewed gold.  It provides a
source-backed, synthetic regression gate for jurisdiction isolation, stale-law
blocking, citation closure, prohibited-outcome controls, and deterministic
behavior.  It may support engineering release decisions, but it cannot satisfy
legal-quality or GA metrics that require attorney-reviewed examples.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from importlib import resources
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .engine import NewHampshireLegalBehaviorEngine
from .jurisdiction import foreign_authority_labels

_SCHEMA = "nh_family_law_llm.pass07_eval_report.v1"
_ALLOWED_AUTHORITY_HOSTS = {
    "gc.nh.gov",
    "courts.nh.gov",
    "www.courts.nh.gov",
    "dhhs.nh.gov",
    "www.dhhs.nh.gov",
    "sos.nh.gov",
    "www.sos.nh.gov",
}
_PRIVATE_MARKERS = (
    "private_case_attachment_marker",
    "private_message_screenshot_marker",
)
_PROHIBITED_PROMISES = (
    "the court will grant",
    "the judge will grant",
    "guaranteed result",
    "guaranteed outcome",
    "child support will be zero",
    "support automatically ends",
    "automatically entitled to 50/50",
)


class EvaluationDatasetError(ValueError):
    """The engineering dataset is malformed or makes an unsafe claim."""


@dataclass(frozen=True, slots=True)
class EvaluationFailure:
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    case_id: str
    category: str
    safety_critical: bool
    passed: bool
    report_status: str
    report_sha256: str
    checks_run: int
    failures: tuple[EvaluationFailure, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failures"] = [row.to_dict() for row in self.failures]
        return payload


@dataclass(slots=True)
class EvaluationSuiteReport:
    dataset_id: str
    review_mode: str
    dataset_sha256: str
    cases: list[EvaluationCaseResult] = field(default_factory=list)
    schema: str = _SCHEMA
    attorney_reviewed: bool = False
    private_data_training_allowed: bool = False
    release_metric_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        passed = sum(row.passed for row in self.cases)
        failed = len(self.cases) - passed
        safety_failures = sum(row.safety_critical and not row.passed for row in self.cases)
        category_totals: dict[str, dict[str, int]] = {}
        for row in self.cases:
            bucket = category_totals.setdefault(row.category, {"total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            bucket["passed" if row.passed else "failed"] += 1
        canonical_cases = [row.to_dict() for row in self.cases]
        digest = sha256(
            json.dumps(canonical_cases, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "schema": self.schema,
            "status": "pass" if failed == 0 else "blocked",
            "dataset_id": self.dataset_id,
            "review_mode": self.review_mode,
            "attorney_reviewed": self.attorney_reviewed,
            "private_data_training_allowed": self.private_data_training_allowed,
            "release_metric_eligible": self.release_metric_eligible,
            "review_required": True,
            "filing_ready": False,
            "legal_advice": False,
            "dataset_sha256": self.dataset_sha256,
            "deterministic_result_sha256": digest,
            "summary": {
                "case_count": len(self.cases),
                "passed": passed,
                "failed": failed,
                "pass_rate": 1.0 if not self.cases else passed / len(self.cases),
                "safety_critical_failure_count": safety_failures,
                "category_totals": category_totals,
            },
            "cases": canonical_cases,
            "notices": [
                "Synthetic operator-source-backed engineering evidence is not attorney-reviewed gold.",
                "A passing suite does not establish legal accuracy, filing readiness, or a predicted outcome.",
                "Every substantive release still requires current-authority review and human legal review.",
            ],
        }


def _default_dataset_path() -> Path:
    try:
        candidate = resources.files("nh_family_law_llm").joinpath(
            "data/evals/nh_pass07_operator_source_backed.jsonl"
        )
        if candidate.is_file():
            return Path(str(candidate))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        pass
    repository = Path(__file__).resolve().parents[2]
    for candidate in (
        repository / "eval_data/nh_pass07_operator_source_backed.jsonl",
        repository / "nh_family_law_llm/data/evals/nh_pass07_operator_source_backed.jsonl",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Pass 7 NH legal-behavior evaluation dataset is unavailable")


def load_cases(path: str | Path | None = None) -> tuple[Path, list[dict[str, Any]]]:
    dataset_path = Path(path).expanduser().resolve() if path else _default_dataset_path()
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise EvaluationDatasetError(
                    f"{dataset_path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(row, dict):
                raise EvaluationDatasetError(f"{dataset_path}:{line_number}: row must be an object")
            case_id = str(row.get("case_id") or "").strip()
            if not case_id or case_id in seen:
                raise EvaluationDatasetError(
                    f"{dataset_path}:{line_number}: missing or duplicate case_id"
                )
            seen.add(case_id)
            if row.get("jurisdiction") != "NH":
                raise EvaluationDatasetError(f"{case_id}: jurisdiction must be NH")
            if row.get("review_mode") != "operator_source_backed":
                raise EvaluationDatasetError(f"{case_id}: review_mode must be operator_source_backed")
            if row.get("synthetic") is not True:
                raise EvaluationDatasetError(f"{case_id}: synthetic must be true")
            if row.get("private_data_allowed_for_training") is not False:
                raise EvaluationDatasetError(
                    f"{case_id}: private_data_allowed_for_training must be false"
                )
            if not isinstance(row.get("payload"), dict) or not isinstance(row.get("expected"), dict):
                raise EvaluationDatasetError(f"{case_id}: payload and expected must be objects")
            serialized = json.dumps(row, sort_keys=True).casefold()
            for marker in _PRIVATE_MARKERS:
                if marker.casefold() in serialized:
                    raise EvaluationDatasetError(f"{case_id}: private marker present")
            cases.append(row)
    if not cases:
        raise EvaluationDatasetError("evaluation dataset is empty")
    return dataset_path, cases


def _canonical_report(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _contains_all(values: Iterable[str], expected: Iterable[str]) -> list[str]:
    actual = set(values)
    return [item for item in expected if item not in actual]


def _substring_missing(values: Iterable[str], needles: Iterable[str]) -> list[str]:
    haystack = "\n".join(values).casefold()
    return [needle for needle in needles if str(needle).casefold() not in haystack]


def _check_case(row: dict[str, Any], report: dict[str, Any]) -> tuple[int, list[EvaluationFailure]]:
    expected = row["expected"]
    failures: list[EvaluationFailure] = []
    checks = 0

    def require(condition: bool, code: str, detail: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(EvaluationFailure(code, detail))

    require(report.get("review_required") is True, "review_required_false", "review_required must remain true")
    require(report.get("filing_ready") is False, "filing_ready_true", "filing_ready must remain false")
    require(report.get("legal_advice") is False, "legal_advice_true", "legal_advice must remain false")
    require(
        report.get("existing_order_remains_in_effect") is True,
        "existing_order_guard_missing",
        "existing-order guard must remain true",
    )

    expected_status = expected.get("status")
    if expected_status:
        require(report.get("status") == expected_status, "status_mismatch", f"expected {expected_status}, got {report.get('status')}")

    findings = {str(item.get("finding_id")): item for item in report.get("findings") or []}
    routes = {str(item.get("route_id")): item for item in report.get("routes") or []}
    issues = [str(item) for item in report.get("issues") or []]
    refs = {str(item.get("authority_id")): item for item in report.get("authority_references") or []}

    for label, actual, key in (
        ("issue", issues, "issues"),
        ("finding", findings, "finding_ids"),
        ("route", routes, "route_ids"),
        ("authority", refs, "authority_ids"),
    ):
        missing = _contains_all(actual, [str(item) for item in expected.get(key, [])])
        require(not missing, f"missing_{label}", f"missing {label} values: {missing}")

    for finding_id, severity in dict(expected.get("finding_severity") or {}).items():
        actual = findings.get(finding_id)
        require(actual is not None, "missing_finding_for_severity", finding_id)
        if actual is not None:
            require(actual.get("severity") == severity, "finding_severity_mismatch", f"{finding_id}: expected {severity}, got {actual.get('severity')}")

    for finding_id, status in dict(expected.get("finding_status") or {}).items():
        actual = findings.get(finding_id)
        require(actual is not None, "missing_finding_for_status", finding_id)
        if actual is not None:
            require(actual.get("status") == status, "finding_status_mismatch", f"{finding_id}: expected {status}, got {actual.get('status')}")

    missing_gaps = _substring_missing(report.get("authority_gaps") or [], expected.get("authority_gaps_contain") or [])
    require(not missing_gaps, "authority_gap_text_missing", f"missing authority-gap text: {missing_gaps}")
    missing_notices = _substring_missing(report.get("notices") or [], expected.get("notices_contain") or [])
    require(not missing_notices, "notice_text_missing", f"missing notice text: {missing_notices}")

    blocker_count = int((report.get("summary") or {}).get("blocker_count") or 0)
    if "requires_blocker" in expected:
        required = bool(expected["requires_blocker"])
        require((blocker_count > 0) is required, "blocker_expectation_mismatch", f"expected requires_blocker={required}, blocker_count={blocker_count}")

    # Citation closure: every authority named by a finding or route must have a
    # corresponding authority card, even when the card is ineligible and blocks.
    referenced: set[str] = set()
    for item in [*(report.get("findings") or []), *(report.get("routes") or [])]:
        referenced.update(str(value) for value in item.get("authority_ids") or [])
    missing_cards = sorted(referenced - set(refs))
    require(not missing_cards, "citation_closure_failure", f"authority cards missing for: {missing_cards}")

    # Eligible sources must be current-verified and come from an approved NH
    # government host. Ineligible cards are acceptable only with an authority gap.
    bad_eligible: list[str] = []
    bad_hosts: list[str] = []
    for authority_id, ref in refs.items():
        if ref.get("retrieval_eligible") and ref.get("status") != "current_verified":
            bad_eligible.append(authority_id)
        host = (urlparse(str(ref.get("source_url") or "")).hostname or "").casefold()
        if host not in _ALLOWED_AUTHORITY_HOSTS:
            bad_hosts.append(f"{authority_id}:{host or '<missing>'}")
    require(not bad_eligible, "eligible_authority_not_current", f"ineligible status on eligible cards: {bad_eligible}")
    require(not bad_hosts, "unapproved_authority_host", f"unapproved authority hosts: {bad_hosts}")

    canonical = _canonical_report(report)
    folded = canonical.casefold()
    foreign_hits = [label for label in foreign_authority_labels() if label.casefold() in folded]
    require(not foreign_hits, "cross_jurisdiction_contamination", f"foreign authority labels in report: {foreign_hits}")
    prohibited = [phrase for phrase in _PROHIBITED_PROMISES if phrase in folded]
    require(not prohibited, "unsupported_outcome_promise", f"prohibited outcome promises: {prohibited}")
    for text in expected.get("prohibited_text") or []:
        require(str(text).casefold() not in folded, "case_prohibited_text", f"prohibited text present: {text}")
    for marker in _PRIVATE_MARKERS:
        require(marker.casefold() not in folded, "private_marker_leak", f"private marker present: {marker}")

    return checks, failures


def run_evaluation(
    *,
    dataset_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> EvaluationSuiteReport:
    path, rows = load_cases(dataset_path)
    dataset_sha = sha256(path.read_bytes()).hexdigest()
    engine = NewHampshireLegalBehaviorEngine(manifest_path=manifest_path)
    results: list[EvaluationCaseResult] = []
    for row in rows:
        report = engine.analyze(row["payload"]).to_dict()
        checks, failures = _check_case(row, report)
        canonical = _canonical_report(report)
        results.append(
            EvaluationCaseResult(
                case_id=str(row["case_id"]),
                category=str(row.get("category") or "uncategorized"),
                safety_critical=bool(row.get("safety_critical")),
                passed=not failures,
                report_status=str(report.get("status") or ""),
                report_sha256=sha256(canonical.encode("utf-8")).hexdigest(),
                checks_run=checks,
                failures=tuple(failures),
            )
        )
    return EvaluationSuiteReport(
        dataset_id=path.name,
        review_mode="operator_source_backed",
        dataset_sha256=dataset_sha,
        cases=results,
    )


def write_report(report: EvaluationSuiteReport, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


__all__ = [
    "EvaluationCaseResult",
    "EvaluationDatasetError",
    "EvaluationFailure",
    "EvaluationSuiteReport",
    "load_cases",
    "run_evaluation",
    "write_report",
]
