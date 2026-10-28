"""Command-line interface for the reproducible research artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import doctor
from .analysis import analyze_runs
from .registry import experiments
from .reports import build_report
from .runner import run
from .live_analysis import prepare_review_sample, summarize_live_runs
from .live_qualification import run_qualification
from .suites import SUITES, run_suite
from .validation import validate_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pulsecrawl-research")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check baseline and runtime availability")
    commands.add_parser("list", help="list registered experiments")
    commands.add_parser("validate", help="validate registry, corpus, and version pins")
    run_parser = commands.add_parser("run", help="execute one registered experiment")
    run_parser.add_argument("identifier")
    run_parser.add_argument("--output-root", type=Path)
    run_parser.add_argument(
        "--phase",
        choices=("qualification", "engineering", "retained"),
        help="live-study phase; ignored by controlled experiments",
    )
    report_parser = commands.add_parser("report", help="aggregate existing run summaries")
    report_parser.add_argument("--run-root", type=Path)
    report_parser.add_argument("--output", type=Path)
    analysis_parser = commands.add_parser("analyze", help="generate statistical and manuscript assets")
    analysis_parser.add_argument("--run-root", type=Path, required=True)
    analysis_parser.add_argument("--output", type=Path, required=True)
    analysis_parser.add_argument(
        "--phase", choices=("pilot", "confirmatory", "remediation"), default="pilot"
    )
    live_summary_parser = commands.add_parser(
        "summarize-live", help="summarize live studies without pooling their phases"
    )
    live_summary_parser.add_argument("--run-root", type=Path, required=True)
    live_summary_parser.add_argument("--output", type=Path, required=True)
    live_review_parser = commands.add_parser(
        "prepare-live-review", help="create a site-balanced manual review worksheet"
    )
    live_review_parser.add_argument("--run-dir", type=Path, required=True)
    live_review_parser.add_argument("--output", type=Path, required=True)
    live_review_parser.add_argument("--sample-size", type=int, default=30)
    qualification_parser = commands.add_parser(
        "qualify-live", help="run the bounded ten-minute qualification for every live category"
    )
    qualification_parser.add_argument("--output-root", type=Path, required=True)
    qualification_parser.add_argument("--workers", type=int, default=9)
    suite_parser = commands.add_parser("suite", help="execute a named experiment suite")
    suite_parser.add_argument("name", choices=sorted(SUITES))
    suite_parser.add_argument("--output-root", type=Path, required=True)
    suite_parser.add_argument(
        "--resume",
        action="store_true",
        help="skip completed repetitions already present in the output root",
    )
    args = parser.parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(doctor(), indent=2, sort_keys=True))
        return 0
    if args.command == "list":
        print(
            json.dumps(
                [
                    {
                        "id": experiment_id,
                        "title": experiment.get("title"),
                        "kind": experiment.get("kind"),
                        "aliases": experiment.get("aliases", []),
                    }
                    for experiment_id, experiment in experiments().items()
                ],
                indent=2,
            )
        )
        return 0
    if args.command == "validate":
        result = validate_artifact()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 1
    if args.command == "run":
        path, result = run(args.identifier, output_root=args.output_root, phase=args.phase)
        print(json.dumps({"runDirectory": str(path), **result}, indent=2, default=str))
        return 0
    if args.command == "report":
        print(
            json.dumps(
                build_report(run_root=args.run_root, output=args.output),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "analyze":
        print(json.dumps(analyze_runs(args.run_root, args.output, phase=args.phase), indent=2, sort_keys=True))
        return 0
    if args.command == "summarize-live":
        print(json.dumps(summarize_live_runs(args.run_root, args.output), indent=2, sort_keys=True))
        return 0
    if args.command == "prepare-live-review":
        rows = prepare_review_sample(args.run_dir, args.output, sample_size=args.sample_size)
        print(json.dumps({"output": str(args.output), "rows": rows}, indent=2, sort_keys=True))
        return 0
    if args.command == "qualify-live":
        result = run_qualification(args.output_root, workers=args.workers)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passedRuntimeGate"] else 1
    if args.command == "suite":
        print(json.dumps(
            run_suite(args.name, args.output_root, resume=args.resume),
            indent=2,
            sort_keys=True,
        ))
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
