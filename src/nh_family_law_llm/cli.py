"""Command-line interface for the local New Hampshire Family Law LLM workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from legal.nh_family_law import (
    AuthoritySnapshotUnavailable,
    EvaluationDatasetError,
    InvalidLegalBehaviorInput,
    NewHampshireLegalBehaviorEngine,
    run_evaluation,
    write_report,
)

from .source_manifest import ManifestValidationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nhfl", description="New Hampshire Family Law LLM local workbench")
    sub = parser.add_subparsers(dest="command")

    sources = sub.add_parser("sources")
    sources_sub = sources.add_subparsers(dest="sources_command")
    sources_sub.add_parser("list")
    sources_sub.add_parser("validate")
    fetch_cmd = sources_sub.add_parser("fetch")
    fetch_cmd.add_argument("--fixtures", action="store_true")
    normalize_cmd = sources_sub.add_parser("normalize")
    normalize_cmd.add_argument("--fixtures", action="store_true")

    index_cmd = sub.add_parser("index")
    index_sub = index_cmd.add_subparsers(dest="index_command")
    build_cmd = index_sub.add_parser("build")
    build_cmd.add_argument("--fixtures", action="store_true")

    ask = sub.add_parser("ask")
    ask.add_argument("question")
    draft = sub.add_parser("draft")
    draft.add_argument("request")
    draft.add_argument("--mode", default="checklist")
    inspect = sub.add_parser("inspect-source")
    inspect.add_argument("source_id")
    corpus = sub.add_parser("corpus")
    corpus_sub = corpus.add_subparsers(dest="corpus_command")
    corpus_sub.add_parser("requirements")
    manifest_cmd = corpus_sub.add_parser("build-manifest")
    manifest_cmd.add_argument("--data-root", default=None)
    audit_cmd = corpus_sub.add_parser("audit")
    audit_cmd.add_argument("--data-root", default=None)
    normalize_live_cmd = corpus_sub.add_parser("normalize")
    normalize_live_cmd.add_argument("--data-root", default=None)
    parse_live_cmd = corpus_sub.add_parser("parse")
    parse_live_cmd.add_argument("--data-root", default=None)
    index_live_cmd = corpus_sub.add_parser("build-indexes")
    index_live_cmd.add_argument("--data-root", default=None)
    fetch_live_cmd = corpus_sub.add_parser("fetch-live")
    fetch_live_cmd.add_argument("--data-root", default=None)
    fetch_live_cmd.add_argument("--allow-live", action="store_true")
    fetch_live_cmd.add_argument("--force", action="store_true")
    fetch_live_cmd.add_argument("--max-sources", type=int, default=None)
    behavior = sub.add_parser(
        "behavior",
        help="Run source-gated NH parenting/support issue spotting from JSON",
    )
    behavior.add_argument(
        "--input",
        default="-",
        help="JSON file path or '-' for stdin",
    )
    behavior.add_argument(
        "--manifest",
        default=None,
        help="Optional explicit NH authority manifest path",
    )
    behavior.add_argument(
        "--strict-authority",
        action="store_true",
        help="Exit 1 when required current authority is unavailable",
    )
    behavior.add_argument("--compact", action="store_true")

    legal_eval = sub.add_parser(
        "legal-eval",
        help="Run the synthetic NH legal-behavior engineering regression suite",
    )
    legal_eval.add_argument("--dataset", default=None)
    legal_eval.add_argument("--manifest", default=None)
    legal_eval.add_argument("--output", default=None)
    legal_eval.add_argument("--compact", action="store_true")

    desktop = sub.add_parser("desktop", help="Serve the installed NH workbench on loopback only")
    desktop.add_argument("--port", type=int, default=8000, help="Loopback port; 0 requests an available port")
    desktop.add_argument("--data-root", default=None, help="Explicit private runtime directory")

    sub.add_parser("doctor")

    skills = sub.add_parser("skills")
    skills_sub = skills.add_subparsers(dest="skills_command")
    skills_list = skills_sub.add_parser("list")
    skills_list.add_argument("--directory", default=None)
    skills_validate = skills_sub.add_parser("validate")
    skills_validate.add_argument("--directory", default=None)

    matter = sub.add_parser("matter")
    matter_sub = matter.add_subparsers(dest="matter_command")
    matter_scan = matter_sub.add_parser("scan")
    matter_scan.add_argument("folder")
    matter_scan.add_argument("--no-recursive", action="store_true")
    matter_scan.add_argument("--include-unsupported", action="store_true")
    matter_scan.add_argument("--hash", action="store_true", dest="hash_files")

    knowledge = sub.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command")
    knowledge_validate = knowledge_sub.add_parser("validate")
    knowledge_validate.add_argument("bundle")

    security = sub.add_parser("security")
    security_sub = security.add_subparsers(dest="security_command")
    dependency_audit = security_sub.add_parser("dependencies")
    dependency_audit.add_argument("--no-api", action="store_true")
    dependency_audit.add_argument("--include-build", action="store_true")
    dependency_audit.add_argument("--strict-optional", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "sources":
            return _sources(args)
        if args.command == "index":
            return _index(args)
        if args.command == "ask":
            return _ask(args.question)
        if args.command == "draft":
            return _draft(args.request, args.mode)
        if args.command == "inspect-source":
            return _inspect(args.source_id)
        if args.command == "corpus":
            return _corpus(args)
        if args.command == "behavior":
            return _behavior(args)
        if args.command == "legal-eval":
            return _legal_eval(args)
        if args.command == "desktop":
            from .desktop import serve_desktop
            return serve_desktop(port=args.port, data_root=args.data_root)
        if args.command == "doctor":
            return _doctor()
        if args.command == "skills":
            return _skills(args)
        if args.command == "matter":
            return _matter(args)
        if args.command == "knowledge":
            return _knowledge(args)
        if args.command == "security":
            return _security(args)
        parser.print_help()
        return 2
    except ManifestValidationError as exc:
        print(json.dumps({"status": "failed", "failure_class": "manifest_invalid", "recovery_hint": str(exc)}))
        return 2


def _sources(args: argparse.Namespace) -> int:
    from .fetch import SourceFetcher
    from .normalize import normalize_fetch_result
    from .sources import (
        DEFAULT_CACHE_DIR,
        DEFAULT_FIXTURES_DIR,
        DEFAULT_MANIFEST_PATH,
        load_seed_manifest,
    )

    entries = load_seed_manifest()
    if args.sources_command == "list":
        for entry in entries:
            print(f"{entry.id}\t{entry.source_type}\tofficial={entry.official}\t{entry.url}")
        return 0
    if args.sources_command == "validate":
        print(json.dumps({"status": "pass", "source_count": len(entries), "manifest": str(DEFAULT_MANIFEST_PATH)}))
        return 0
    if args.sources_command == "fetch":
        fetcher = SourceFetcher(DEFAULT_FIXTURES_DIR, DEFAULT_CACHE_DIR, allow_live=False)
        results = [fetcher.fetch(entry, fixtures=bool(args.fixtures), force=True) for entry in entries]
        print(json.dumps({"status": "pass" if all(item.ok for item in results) else "failed", "fetched": sum(1 for item in results if item.ok)}))
        return 0 if all(item.ok for item in results) else 2
    if args.sources_command == "normalize":
        fetcher = SourceFetcher(DEFAULT_FIXTURES_DIR, DEFAULT_CACHE_DIR, allow_live=False)
        out_dir = Path(DEFAULT_CACHE_DIR) / "normalized"
        count = 0
        for entry in entries:
            result = fetcher.fetch(entry, fixtures=bool(args.fixtures), force=True)
            if result.ok:
                normalize_fetch_result(result, output_dir=out_dir)
                count += 1
        print(json.dumps({"status": "pass", "normalized": count, "output_dir": str(out_dir)}))
        return 0
    return 2


def _index(args: argparse.Namespace) -> int:
    from .index import save_index
    from .sources import DEFAULT_INDEX_PATH
    from .workbench import build_fixture_chunks

    if args.index_command == "build":
        chunks = build_fixture_chunks()
        proxy_chunks = [type("_ChunkProxy", (), {"to_dict": lambda self, payload=chunk: payload})() for chunk in chunks]
        path = save_index(DEFAULT_INDEX_PATH, proxy_chunks)
        print(json.dumps({"status": "pass", "chunk_count": len(chunks), "index_path": str(path)}))
        return 0
    return 2


def _ask(question: str) -> int:
    from .answer import compose_answer
    from .chat_library import expand_query_for_library
    from .safety import classify_prompt
    from .workbench import retrieve_fixture_sources

    safety = classify_prompt(question)
    response = retrieve_fixture_sources(expand_query_for_library(question))
    answer = compose_answer(question, response.results, safety)
    print(answer.answer)
    return 0 if answer.failure_class == "none" else 1


def _draft(request: str, mode: str) -> int:
    from .draft import draft_from_sources
    from .workbench import retrieve_fixture_sources

    response = retrieve_fixture_sources(request)
    draft = draft_from_sources(request, response.results, mode=mode)
    print(draft.text)
    return 0 if draft.failure_class == "none" else 1


def _inspect(source_id: str) -> int:
    from .corpus_registry import full_corpus_manifest_entries
    from .sources import get_source, load_seed_manifest

    entries = load_seed_manifest() + full_corpus_manifest_entries()
    entry = get_source(entries, source_id)
    if entry is None:
        print(json.dumps({"status": "failed", "failure_class": "source_not_found", "source_id": source_id}))
        return 1
    print(json.dumps(entry.to_dict(), indent=2))
    return 0


def _corpus(args: argparse.Namespace) -> int:
    from .corpus_build import (
        audit_external_corpus,
        build_required_indexes,
        default_data_root,
        fetch_live_official_corpus,
        normalize_external_corpus,
        parse_external_corpus,
        write_full_corpus_manifest,
    )
    from .corpus_registry import corpus_summary

    data_root = Path(args.data_root).resolve() if getattr(args, "data_root", None) else default_data_root()
    if args.corpus_command == "requirements":
        print(json.dumps(corpus_summary(), indent=2))
        return 0
    if args.corpus_command == "build-manifest":
        path = write_full_corpus_manifest(data_root)
        print(json.dumps({"status": "pass", "manifest_path": str(path), "data_root": str(data_root)}))
        return 0
    if args.corpus_command == "audit":
        report = audit_external_corpus(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "normalize":
        report = normalize_external_corpus(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "parse":
        report = parse_external_corpus(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "build-indexes":
        report = build_required_indexes(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "fetch-live":
        try:
            artifacts = fetch_live_official_corpus(
                data_root,
                allow_live=bool(args.allow_live),
                max_sources=args.max_sources,
                force=bool(args.force),
            )
        except ValueError as exc:
            print(json.dumps({"status": "blocked", "failure_class": "live_fetch_not_confirmed", "recovery_hint": str(exc)}))
            return 2
        ok_count = sum(1 for item in artifacts if item.ok)
        print(
            json.dumps(
                {
                    "status": "pass" if ok_count == len(artifacts) else "blocked",
                    "fetched": ok_count,
                    "attempted": len(artifacts),
                    "data_root": str(data_root),
                    "failures": [item.to_dict() for item in artifacts if not item.ok],
                },
                indent=2,
            )
        )
        return 0 if ok_count == len(artifacts) else 1
    return 2


def _behavior(args: argparse.Namespace) -> int:
    try:
        if args.input == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.input).expanduser().read_text(encoding="utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("input JSON must be an object")
        report = NewHampshireLegalBehaviorEngine(
            manifest_path=args.manifest
        ).analyze(payload)
    except InvalidLegalBehaviorInput as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}))
        return 2
    except AuthoritySnapshotUnavailable as exc:
        print(json.dumps({"status": "authority_unavailable", "error": str(exc)}))
        return 3
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2
    result = report.to_dict()
    print(json.dumps(result, indent=None if args.compact else 2))
    return 1 if args.strict_authority and result["authority_gaps"] else 0


def _legal_eval(args: argparse.Namespace) -> int:
    try:
        report = run_evaluation(
            dataset_path=args.dataset,
            manifest_path=args.manifest,
        )
        result = report.to_dict()
        if args.output:
            write_report(report, Path(args.output).expanduser())
    except (EvaluationDatasetError, OSError, ValueError) as exc:
        print(json.dumps({"status": "invalid_evaluation_dataset", "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=None if args.compact else 2))
    return 0 if result["status"] == "pass" else 1


def _doctor() -> int:
    repo = Path(__file__).resolve().parents[2]
    forbidden = []
    for name in (".local_tmp", ".pytest_cache", "__pycache__", "NH_FAMILY_LAW_LLM_data", "vector_store"):
        forbidden.extend(str(path.relative_to(repo)) for path in repo.rglob(name) if path.exists())
    forbidden = [item for item in forbidden if not item.startswith((".venv\\", ".venv/"))]
    status = "pass" if not forbidden else "fail"
    print(json.dumps({"status": status, "forbidden_paths": forbidden, "repo": str(repo)}))
    return 0 if status == "pass" else 1


def _default_skill_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "workflow_skills"


def _skills(args: argparse.Namespace) -> int:
    from legal.workflow_skills import SkillRegistry, SkillValidationError

    directory = (
        Path(args.directory).expanduser().resolve()
        if getattr(args, "directory", None)
        else _default_skill_directory()
    )
    try:
        registry = SkillRegistry.from_directory(directory)
    except (SkillValidationError, OSError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc), "directory": str(directory)}))
        return 2
    if args.skills_command == "list":
        print(
            json.dumps(
                {
                    "status": "pass",
                    "directory": str(directory),
                    "skills": [manifest.to_dict() for manifest in registry.list()],
                },
                indent=2,
            )
        )
        return 0
    if args.skills_command == "validate":
        report = registry.validate_dependencies()
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.status == "pass" else 1
    return 2


def _matter(args: argparse.Namespace) -> int:
    from legal.matter.document_inventory import InventoryError, scan_matter_folder

    if args.matter_command != "scan":
        return 2
    try:
        report = scan_matter_folder(
            Path(args.folder),
            recursive=not args.no_recursive,
            include_unsupported=bool(args.include_unsupported),
            hash_files=bool(args.hash_files),
        )
    except (InventoryError, OSError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}))
        return 2
    print(json.dumps(report.to_dict(), indent=2))
    return 0


def _knowledge(args: argparse.Namespace) -> int:
    from legal.knowledge_bundle import validate_bundle

    if args.knowledge_command != "validate":
        return 2
    try:
        report = validate_bundle(Path(args.bundle))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}))
        return 2
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.status == "pass" else 1


def _security(args: argparse.Namespace) -> int:
    from legal.security.dependency_floor import audit_dependency_floors

    if args.security_command != "dependencies":
        return 2
    report = audit_dependency_floors(
        include_api=not args.no_api,
        include_build=bool(args.include_build),
        strict_optional=bool(args.strict_optional),
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
