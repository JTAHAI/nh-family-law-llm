import json
from pathlib import Path

from legal.evals.benchmark_runner import BASE_GOLD_REQUIRED_FIELDS, BenchmarkRunner


REQUIRED_DATASETS = {
    "nh_rag_retrieval_gold.jsonl",
    "nh_citation_validity_gold.jsonl",
    "nh_quote_span_gold.jsonl",
    "nh_issue_classification_gold.jsonl",
    "nh_posture_classification_gold.jsonl",
    "nh_authority_ranking_gold.jsonl",
    "nh_fact_to_evidence_gold.jsonl",
    "nh_hallucination_negative_cases.jsonl",
    "nh_forms_freshness_gold.jsonl",
    "nh_drafting_review_gold.jsonl",
    "nh_supreme_court_holding_gold.jsonl",
    "nh_rule_52_gap_gold.jsonl",
}


def test_required_gold_dataset_seed_files_and_schemas_exist():
    eval_root = Path("eval_data")
    dataset_names = {path.name for path in eval_root.glob("*.jsonl")}
    schema_names = {path.name for path in (eval_root / "schemas").glob("*.json")}
    assert REQUIRED_DATASETS <= dataset_names
    assert {name.replace(".jsonl", ".schema.json") for name in REQUIRED_DATASETS} <= schema_names


def test_gold_seed_rows_have_required_fields_and_no_private_training_flag():
    for dataset in REQUIRED_DATASETS:
        path = Path("eval_data") / dataset
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert BASE_GOLD_REQUIRED_FIELDS <= set(row)
        assert row["private_data_allowed_for_training"] is False
        assert row["review_status"] == "seed_not_attorney_reviewed"


def test_benchmark_runner_validates_seed_schemas_honestly():
    result = BenchmarkRunner("eval_data").run()
    assert result["status"] == "pass"
    assert result["dataset_count"] >= len(REQUIRED_DATASETS)
    assert result["schema_violations"] == 0
    assert result["private_training_rows"] == 0
    assert result["metric_basis"] == "schema_validated_synthetic_seed_only_not_attorney_gold"
    assert result["retrieval_accuracy"] is None
