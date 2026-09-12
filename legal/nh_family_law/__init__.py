"""New Hampshire-specific legal behavior, routing, and drafting safeguards.

This package does not decide a case or calculate an enforceable support amount.
It converts reported facts into issue spots, evidence gaps, authority requirements,
and review-required procedural routes grounded in the promoted NH authority snapshot.
"""
from .engine import NewHampshireLegalBehaviorEngine
from .errors import AuthoritySnapshotUnavailable, InvalidLegalBehaviorInput
from .evaluation import EvaluationDatasetError, EvaluationSuiteReport, run_evaluation, write_report
from .models import LegalBehaviorReport

__all__ = [
    "AuthoritySnapshotUnavailable",
    "InvalidLegalBehaviorInput",
    "EvaluationDatasetError",
    "EvaluationSuiteReport",
    "LegalBehaviorReport",
    "NewHampshireLegalBehaviorEngine",
    "run_evaluation",
    "write_report",
]
