"""Import a frozen local release as bounded, sanitized public evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_RULES = {
    "absolute home path": re.compile(
        r"/(?:Users|home)/[A-Za-z0-9_.-]+|[A-Za-z]:\\Users\\", re.I
    ),
    "credential": re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}

EXPERIMENT_IDS = {
    "S01": "execution-budget-under-concurrency",
    "S02": "interruption-recovery",
    "S03": "shared-origin-pacing",
    "S04": "robots-request-controls",
    "S05": "deferred-work-efficiency",
    "S06": "policy-mechanism-ablation",
    "S07": "concurrent-redelivery-stress",
    "S08": "coordination-operation-cost",
    "T01": "url-scoped-template-selection",
    "T02": "fallback-and-template-diagnostics",
    "T03": "controlled-markup-drift",
    "T04": "frozen-multi-industry-corpus",
    "T05": "integration-surface-comparison",
    "T06": "template-change-diffusion",
    "T07": "multiple-entity-ambiguity",
    "T09": "scoped-template-governance",
    "T10": "expanded-template-policy-comparison",
    "D01": "temporal-query-scaling",
    "D02": "new-url-materialization",
    "D03": "compaction-version-isolation",
    "D04": "parquet-semantic-round-trip",
    "D05": "publication-atomicity-ablation",
    "D06": "million-row-scale-matrix",
    "D07": "temporal-query-correctness",
    "D08": "compaction-interruption-matrix",
    "D10": "governed-dataset-pipeline",
    "D11": "public-workspace-publication",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scan_text(label: str, text: str) -> None:
    for rule, pattern in PRIVATE_RULES.items():
        if pattern.search(text):
            raise ValueError(f"{label} contains a prohibited {rule}")


def scan_path(path: Path) -> None:
    scan_text(path.name, path.read_text(encoding="utf-8"))


def verify_source_checksums(run_dir: Path, expected_manifest_hash: str) -> None:
    checksum_path = run_dir / "checksums.sha256"
    if sha256(checksum_path) != expected_manifest_hash:
        raise ValueError(f"source checksum-manifest mismatch: {run_dir.name}")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        target = run_dir / relative
        if not target.is_file() or sha256(target) != digest:
            raise ValueError(f"source checksum mismatch: {run_dir.name}/{relative}")


def collect_times(value: Any, started: list[str], completed: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("_", "")
            if isinstance(child, str) and "t" in child.lower():
                if "startedat" in normalized:
                    started.append(child)
                if "finishedat" in normalized or "completedat" in normalized:
                    completed.append(child)
            collect_times(child, started, completed)
    elif isinstance(value, list):
        for child in value:
            collect_times(child, started, completed)


def source_times(summary: Any, run_id: str) -> tuple[str, str]:
    started: list[str] = []
    completed: list[str] = []
    collect_times(summary, started, completed)
    fallback = datetime.strptime(run_id[:16], "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    return min(started) if started else fallback, max(completed) if completed else fallback


def generic_platform(environment: dict[str, Any]) -> str:
    raw = str(environment.get("platform") or "unknown")
    machine = str(environment.get("machine") or "unknown")
    if raw.lower().startswith("macos"):
        return f"macOS-{machine}"
    if raw.lower().startswith("linux"):
        return f"Linux-{machine}"
    if raw.lower().startswith("windows"):
        return f"Windows-{machine}"
    return f"Other-{machine}"


def write_checksums(directory: Path, files: Iterable[Path]) -> None:
    paths = sorted(files, key=lambda path: path.name)
    body = "".join(f"{sha256(path)}  {path.name}\n" for path in paths)
    (directory / "checksums.sha256").write_text(body, encoding="utf-8")


def publish_execution(
    *,
    run_dir: Path,
    release_row: dict[str, Any],
    public_experiment: dict[str, Any],
    release: dict[str, Any],
    output_root: Path,
) -> dict[str, str]:
    verify_source_checksums(run_dir, release_row["checksumsSha256"])
    measurement_names = [
        name
        for name in ("observations.json", "template-metrics.json", "datalake-metrics.json")
        if (run_dir / name).is_file()
    ]
    if len(measurement_names) != 1:
        raise ValueError(f"expected one direct-measurement file in {run_dir.name}")
    source_measurements_path = run_dir / measurement_names[0]
    summary = read_json(run_dir / "summary.json")
    observations = read_json(source_measurements_path)
    environment = read_json(run_dir / "environment.json")
    scan_text(f"{run_dir.name}/summary.json", json.dumps(summary, sort_keys=True))
    scan_text(f"{run_dir.name}/{source_measurements_path.name}", json.dumps(observations, sort_keys=True))

    output_dir = output_root / "evidence" / "executions" / run_dir.name
    if output_dir.exists():
        manifest = read_json(output_dir / "execution-manifest.json")
        if manifest["inputs"]["sourceRunChecksumsSha256"] != release_row["checksumsSha256"]:
            raise ValueError(f"existing public execution has another source: {run_dir.name}")
        expected_files = {
            "execution-manifest.json",
            "resolved-experiment.json",
            "measurements.json",
            "summary.json",
            "checksums.sha256",
        }
        if {path.name for path in output_dir.iterdir() if path.is_file()} != expected_files:
            raise ValueError(f"existing public execution is incomplete: {run_dir.name}")
        for line in (output_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            if sha256(output_dir / relative) != digest:
                raise ValueError(f"existing public execution checksum mismatch: {run_dir.name}")
        return {
            "executionId": run_dir.name,
            "experimentId": public_experiment["id"],
            "sourceRunChecksumsSha256": release_row["checksumsSha256"],
            "publicChecksumsSha256": sha256(output_dir / "checksums.sha256"),
        }
    output_dir.mkdir(parents=True)
    resolved_path = output_dir / "resolved-experiment.json"
    measurements_path = output_dir / "measurements.json"
    summary_path = output_dir / "summary.json"
    write_json(resolved_path, public_experiment)
    write_json(measurements_path, observations)
    write_json(summary_path, summary)

    started_at, completed_at = source_times(summary, run_dir.name)
    manifest = {
        "schemaVersion": 1,
        "executionId": run_dir.name,
        "experimentId": public_experiment["id"],
        "status": "completed",
        "startedAt": started_at,
        "completedAt": completed_at,
        "software": {
            "pulsecrawl": str(environment["pulsecrawlDistributionVersion"]),
            "python": str(environment["python"]).split()[0],
            "platform": generic_platform(environment),
        },
        "inputs": {
            "artifactRelease": "0.3.0",
            "checksumsSha256": sha256(output_root / "checksums.sha256"),
            "sourceRelease": str(release["release"]),
            "sourceRepositoryCommit": str(release["repositoryCommit"]),
            "sourceRunChecksumsSha256": str(release_row["checksumsSha256"]),
        },
        "command": [
            "pulsecrawl-research",
            "run",
            str(release_row["experimentId"]),
            "--phase",
            "confirmatory",
        ],
        "configuration": public_experiment["workload"],
        "outputs": {
            "measurements": measurements_path.name,
            "summary": summary_path.name,
            "checksums": "checksums.sha256",
        },
        "notes": [
            "The shell invocation is reconstructed from the registered release procedure; the source run did not retain a shell transcript.",
            "This public directory excludes raw workspaces, downloaded HTML, and machine-specific environment fields.",
        ],
    }
    manifest_path = output_dir / "execution-manifest.json"
    write_json(manifest_path, manifest)
    write_checksums(
        output_dir, [manifest_path, resolved_path, measurements_path, summary_path]
    )
    for path in output_dir.iterdir():
        scan_path(path)
    return {
        "executionId": run_dir.name,
        "experimentId": public_experiment["id"],
        "sourceRunChecksumsSha256": release_row["checksumsSha256"],
        "publicChecksumsSha256": sha256(output_dir / "checksums.sha256"),
    }


def copy_analysis(
    *, source: Path, output_root: Path, execution_ids: list[str], created_at: str
) -> dict[str, str]:
    output_dir = output_root / "analysis" / "releases" / "public-local-0.1.0-2026-10-27"
    output_dir.mkdir(parents=True, exist_ok=True)
    names = [
        "analysis.json",
        "findings.md",
        "hypothesis-verdicts.json",
        "hypothesis-verdicts.md",
        "measurements.csv",
        "statistics.csv",
    ]
    outputs: dict[str, str] = {}
    copied: list[Path] = []
    for name in names:
        destination = output_dir / name
        shutil.copyfile(source / name, destination)
        scan_path(destination)
        copied.append(destination)
        outputs[name.replace("-", "_").replace(".", "_")] = name
    manifest = {
        "schemaVersion": 1,
        "analysisId": "public-local-0.1.0-2026-10-27",
        "createdAt": created_at,
        "includedExecutions": execution_ids,
        "excludedExecutions": [],
        "method": "Frozen confirmatory analysis with pilot, superseded, and remediation runs kept separate.",
        "software": {"pulsecrawl": "0.1.0", "python": "3.11.9"},
        "outputs": outputs | {"checksums": "checksums.sha256"},
    }
    manifest_path = output_dir / "analysis-manifest.json"
    write_json(manifest_path, manifest)
    copied.append(manifest_path)
    write_checksums(output_dir, copied)
    return {
        "analysisId": manifest["analysisId"],
        "checksumsSha256": sha256(output_dir / "checksums.sha256"),
    }


def copy_live_summary(
    *, study: str, source: Path, output_root: Path, source_checksum: str
) -> dict[str, str]:
    summary = read_json(source)
    scan_text(f"live {study} summary", json.dumps(summary, sort_keys=True))
    output_dir = output_root / "evidence" / "live-studies" / study
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    write_json(summary_path, summary)
    manifest = {
        "schemaVersion": 1,
        "study": study,
        "status": "completed-supporting-observation",
        "sourceSummarySha256": source_checksum,
        "publishedSummarySha256": sha256(summary_path),
        "exclusions": [
            "downloaded HTML bodies",
            "article and product text",
            "raw request logs",
            "workspace databases",
            "machine-specific environment fields",
        ],
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    write_checksums(output_dir, [manifest_path, summary_path])
    return {
        "study": study,
        "checksumsSha256": sha256(output_dir / "checksums.sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-release-manifest", type=Path, required=True)
    parser.add_argument("--source-run-root", type=Path, required=True)
    parser.add_argument("--source-analysis", type=Path, required=True)
    parser.add_argument("--news-summary", type=Path, required=True)
    parser.add_argument("--commerce-summary", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()

    release = read_json(args.source_release_manifest)
    if release["repositoryDirty"] is not False:
        raise ValueError("only a clean frozen source release can be published")
    if release["runCount"] != len(release["runs"]):
        raise ValueError("source release run count does not match its manifest")

    catalog = read_json(args.output_root / "experiments" / "catalog.json")
    public_experiments = {entry["id"]: entry for entry in catalog["experiments"]}
    published: list[dict[str, str]] = []
    for row in release["runs"]:
        local_id = row["experimentId"]
        public_id = EXPERIMENT_IDS.get(local_id)
        if public_id is None or public_id not in public_experiments:
            raise ValueError(f"no public experiment mapping for {local_id}")
        run_dir = args.source_run_root / row["runId"]
        published.append(
            publish_execution(
                run_dir=run_dir,
                release_row=row,
                public_experiment=public_experiments[public_id],
                release=release,
                output_root=args.output_root,
            )
        )

    analysis = copy_analysis(
        source=args.source_analysis,
        output_root=args.output_root,
        execution_ids=[row["executionId"] for row in published],
        created_at=release["createdAt"],
    )
    extra_hashes = {row["sha256"]: row for row in release["extraArtifacts"]}
    news_hash = sha256(args.news_summary)
    commerce_hash = sha256(args.commerce_summary)
    if news_hash not in extra_hashes or commerce_hash not in extra_hashes:
        raise ValueError("live summary is not identified by the frozen source release")
    live = [
        copy_live_summary(
            study="news",
            source=args.news_summary,
            output_root=args.output_root,
            source_checksum=news_hash,
        ),
        copy_live_summary(
            study="commerce",
            source=args.commerce_summary,
            output_root=args.output_root,
            source_checksum=commerce_hash,
        ),
    ]
    public_release = {
        "schemaVersion": 1,
        "release": "0.3.0",
        "sourceRelease": release["release"],
        "sourceRepositoryCommit": release["repositoryCommit"],
        "sourceRepositoryDirty": release["repositoryDirty"],
        "createdAt": release["createdAt"],
        "controlledExecutionCount": len(published),
        "controlledExecutions": published,
        "analysis": analysis,
        "liveStudies": live,
        "publicationBoundary": {
            "included": [
                "sanitized controlled summaries and direct measurements",
                "frozen controlled analysis",
                "aggregate retained live-study summaries",
            ],
            "excluded": [
                "raw workspaces and databases",
                "downloaded third-party HTML",
                "article and product text",
                "machine-specific paths and identifiers",
                "credentials and unreviewed logs",
            ],
        },
    }
    release_path = args.output_root / "evidence" / "reviewed-release.json"
    write_json(release_path, public_release)
    scan_path(release_path)
    print(
        json.dumps(
            {
                "controlledExecutions": len(published),
                "analysis": analysis["analysisId"],
                "liveStudies": [row["study"] for row in live],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
