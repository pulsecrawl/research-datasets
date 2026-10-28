"""Build reviewer-readable CSV companions for retained research evidence.

The JSON and Parquet files remain authoritative.  This tool creates derived
views that GitHub can render directly and records exactly which source files
were used.  It never invents event-level observations that were not retained
by the original execution.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
CONTROLLED_SOURCE_RELEASE = ROOT / "experiments/releases/controlled-evidence-v0.3.2"
CONTROLLED_RELEASE = ROOT / "experiments/releases/controlled-evidence-v0.3.3"
QUALIFICATION_SOURCE_RELEASE = ROOT / "experiments/releases/multi-category-qualification-v0.4.1-rc.1"
QUALIFICATION_RELEASE = ROOT / "experiments/releases/multi-category-qualification-v0.4.1"
MAX_COMPLETE_ROWS = 10_000
PREVIEW_ROWS = 500
CSV_REDACTIONS = (
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[redacted-email]"),
    (re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+", re.I), "[redacted-home-path]"),
    (re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b"), "[redacted-credential]"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    for pattern, replacement in CSV_REDACTIONS:
        text = pattern.sub(replacement, text)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def flatten(value: Any, path: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{path}.{key}" if path else str(key)
            rows.extend(flatten(value[key], child))
    elif isinstance(value, list):
        if not value:
            rows.append({"measurement": path, "value": "[]", "type": "list"})
        else:
            for index, child_value in enumerate(value):
                rows.extend(flatten(child_value, f"{path}[{index}]"))
    else:
        value_type = "null" if value is None else type(value).__name__
        rows.append({"measurement": path, "value": csv_value(value), "type": value_type})
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def files_for_checksums(folder: Path) -> list[Path]:
    return sorted(
        path for path in folder.rglob("*")
        if path.is_file() and path.name not in {"checksums.sha256", "README.md"}
    )


def write_checksums(folder: Path) -> str:
    body = "".join(
        f"{sha256(path)}  {path.relative_to(folder).as_posix()}\n"
        for path in files_for_checksums(folder)
    )
    checksum_path = folder / "checksums.sha256"
    checksum_path.write_text(body, encoding="utf-8")
    return sha256(checksum_path)


def gap_rows(value: Any, path: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        required = value.get("requiredGapSeconds")
        minimum = value.get("minimumGapSeconds")
        violations = value.get("gapViolations")
        if required is not None and minimum is not None and violations is not None:
            rows.append({
                "scope": path,
                "required_gap_seconds": required,
                "minimum_observed_gap_seconds": minimum,
                "violations": violations,
                "result": "pass" if violations == 0 and minimum >= required else "fail",
            })
        for key, child in value.items():
            rows.extend(gap_rows(child, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(gap_rows(child, f"{path}[{index}]"))
    return rows


def controlled_readme(
    *, manifest: dict[str, Any], experiment: dict[str, Any], summary: dict[str, Any],
    has_dataset: bool,
) -> str:
    status = manifest.get("status", "unknown")
    lines = [
        f"# {experiment.get('title', manifest['experimentId'])}",
        "",
        f"**Execution:** `{manifest['executionId']}`  ",
        f"**Status:** {status}  ",
        f"**Acceptance rule:** {experiment.get('acceptance', 'See resolved-experiment.json.')}",
        "",
        "## What to inspect",
        "",
        "| File | Purpose |",
        "|---|---|",
        "| `measurements.csv` | Human-readable, flattened view of every retained measurement |",
        "| `measurements.json` | Authoritative structured measurements |",
        "| `summary.json` | Run-level result consumed by the reviewed analysis |",
        "| `resolved-experiment.json` | Registered workload, measures, and acceptance rule |",
        "| `execution-manifest.json` | Software, timing, command, and source-evidence identity |",
        "| `checksums.sha256` | Integrity hashes for all published run files |",
    ]
    if has_dataset:
        lines.append(
            "| `readable-output/` | Parquet evidence plus its matching CSV view and export manifest |"
        )
    gaps = gap_rows(summary)
    if gaps:
        lines.extend([
            "", "## Recorded pacing checks", "",
            "| Scope | Required gap (s) | Minimum observed gap (s) | Violations | Result |",
            "|---|---:|---:|---:|---|",
        ])
        for row in gaps:
            lines.append(
                f"| `{row['scope']}` | {row['required_gap_seconds']} | "
                f"{row['minimum_observed_gap_seconds']} | {row['violations']} | {row['result']} |"
            )
    lines.extend([
        "",
        "`measurements.csv` is derived from `measurements.json`; it does not add observations",
        "that were not retained by the execution. Parquet files, when present, remain the",
        "authoritative dataset representation and the CSV is a reviewer-readable companion.",
        "",
    ])
    return "\n".join(lines)


def pyarrow_modules():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency error is explicit
        raise RuntimeError("install the datalake dependencies to build readable evidence") from exc
    return pa, pq


def rows_from_table(table: Any) -> tuple[list[dict[str, Any]], list[str]]:
    columns = list(table.column_names)
    rows = [{key: csv_value(value) for key, value in row.items()} for row in table.to_pylist()]
    return rows, columns


def schema_json(table: Any) -> dict[str, Any]:
    return {
        "fields": [
            {"name": field.name, "type": str(field.type), "nullable": field.nullable}
            for field in table.schema
        ]
    }


def select_controlled_parquet(source_run: Path) -> Path | None:
    root = source_run / "artifacts/datalake"
    if not root.is_dir():
        return None
    direct = root / "compact.parquet"
    if direct.is_file():
        return direct
    compact = sorted(root.rglob("compact*.parquet"))
    if compact:
        return compact[0]
    files = sorted(root.rglob("*.parquet"))
    return files[0] if files else None


def build_controlled_dataset_output(run: Path, source_run: Path) -> bool:
    selected = select_controlled_parquet(source_run)
    if selected is None:
        return False
    pa, pq = pyarrow_modules()
    table = pq.read_table(selected)
    source_rows = table.num_rows
    complete = source_rows <= MAX_COMPLETE_ROWS
    published = table if complete else table.slice(0, min(PREVIEW_ROWS, source_rows))
    output = run / "readable-output"
    output.mkdir(parents=True, exist_ok=True)
    parquet_name = "records.parquet" if complete else "records-preview.parquet"
    csv_name = "records.csv" if complete else "records-preview.csv"
    parquet_path = output / parquet_name
    if complete:
        shutil.copyfile(selected, parquet_path)
    else:
        pq.write_table(published, parquet_path, compression="zstd")
    rows, columns = rows_from_table(published)
    write_csv(output / csv_name, rows, columns)
    write_json(output / "schema.json", schema_json(published))
    all_source_files = sorted((source_run / "artifacts/datalake").rglob("*.parquet"))
    write_json(output / "export-manifest.json", {
        "authoritativeFormat": "Parquet",
        "csvRole": "reviewer-readable companion",
        "csvSanitization": [
            "email addresses are replaced with [redacted-email]",
            "absolute home paths are replaced with [redacted-home-path]",
            "credential-shaped values are replaced with [redacted-credential]",
        ],
        "exportType": "complete-selected-file" if complete else "deterministic-preview",
        "selectedSourceFile": selected.relative_to(source_run).as_posix(),
        "selectedSourceFileSha256": sha256(selected),
        "selectedSourceRows": source_rows,
        "publishedRows": published.num_rows,
        "publishedParquet": parquet_name,
        "publishedParquetSha256": sha256(parquet_path),
        "publishedCsv": csv_name,
        "publishedCsvSha256": sha256(output / csv_name),
        "sourceRunParquetFiles": len(all_source_files),
        "sourceRunParquetBytes": sum(path.stat().st_size for path in all_source_files),
        "note": (
            "The complete selected source file is published."
            if complete else
            "The full benchmark output is large; this deterministic preview contains the "
            "first retained rows of one selected source file. Aggregate full-run measurements "
            "remain in measurements.json and measurements.csv."
        ),
    })
    (output / "README.md").write_text(
        "# Readable dataset output\n\n"
        f"`{parquet_name}` is the Parquet evidence published for this run. "
        f"`{csv_name}` contains the same {published.num_rows} rows in a format GitHub can "
        "display directly. Open `export-manifest.json` to see whether this is the complete "
        "selected file or a bounded preview and to trace it to the retained source file.\n",
        encoding="utf-8",
    )
    return True


def enrich_controlled_runs(source_run_root: Path) -> dict[str, int]:
    if not CONTROLLED_RELEASE.exists():
        CONTROLLED_RELEASE.mkdir(parents=True)
        shutil.copytree(
            CONTROLLED_SOURCE_RELEASE / "analysis",
            CONTROLLED_RELEASE / "analysis",
        )
        source_manifest = read_json(
            CONTROLLED_SOURCE_RELEASE / "release-manifest-v0.3.2.json"
        )
        source_manifest["release"] = "0.3.3"
        source_manifest["documentation"]["version"] = "0.3.3"
        source_manifest["artifactAreas"] = {
            "datasets": "datasets/",
            "experiments": "experiments/",
            "protocols": "docs/protocols/",
            "controlledEvidence": "experiments/controlled/",
            "analysis": "experiments/releases/controlled-evidence-v0.3.3/analysis/",
            "liveEvidence": "experiments/live/",
        }
        source_manifest["evidence"].update({
            "schema": "experiments/releases/execution-manifest.schema.json",
            "executionsPath": "experiments/controlled/",
            "evidenceRelease": "0.3.3",
            "reviewedRelease": "experiments/releases/controlled-evidence-v0.3.3/reviewed-release.json",
            "status": "sanitized-reviewed-and-readable-evidence-published",
        })
        source_manifest["analysis"].update({
            "schema": "experiments/releases/analysis-manifest.schema.json",
            "path": "experiments/releases/controlled-evidence-v0.3.3/analysis/",
            "reviewedRelease": "experiments/releases/controlled-evidence-v0.3.3/analysis/",
        })
        source_manifest["revisionNote"] = (
            "Release 0.3.3 adds a human-readable README and measurements.csv to every "
            "controlled run. Dataset-producing runs also publish checksum-linked Parquet "
            "evidence with a matching complete or bounded CSV view. Measurements and "
            "hypothesis decisions are unchanged from release 0.3.2."
        )
        write_json(
            CONTROLLED_RELEASE / "release-manifest-v0.3.3.json",
            source_manifest,
        )
        reviewed = read_json(CONTROLLED_SOURCE_RELEASE / "reviewed-release.json")
        reviewed["release"] = "0.3.3"
        write_json(CONTROLLED_RELEASE / "reviewed-release.json", reviewed)
    reviewed_path = CONTROLLED_RELEASE / "reviewed-release.json"
    reviewed = read_json(reviewed_path)
    by_execution = {row["executionId"]: row for row in reviewed["controlledExecutions"]}
    enriched = 0
    dataset_runs = 0
    for run in sorted((ROOT / "experiments/controlled").glob("*/runs/run-*")):
        manifest_path = run / "execution-manifest.json"
        manifest = read_json(manifest_path)
        experiment = read_json(run / "resolved-experiment.json")
        measurements = read_json(run / "measurements.json")
        summary = read_json(run / "summary.json")
        write_csv(run / "measurements.csv", flatten(measurements), ["measurement", "value", "type"])
        source_run = source_run_root / manifest["executionId"]
        has_dataset = False
        if experiment.get("family") == "versioned-datasets" and source_run.is_dir():
            has_dataset = build_controlled_dataset_output(run, source_run)
            dataset_runs += int(has_dataset)
        manifest.setdefault("outputs", {})["readableMeasurements"] = "measurements.csv"
        if has_dataset:
            manifest["outputs"]["readableDataset"] = "readable-output/export-manifest.json"
        write_json(manifest_path, manifest)
        (run / "README.md").write_text(
            controlled_readme(
                manifest=manifest, experiment=experiment, summary=summary,
                has_dataset=has_dataset,
            ),
            encoding="utf-8",
        )
        digest = write_checksums(run)
        by_execution[manifest["executionId"]]["publicChecksumsSha256"] = digest
        enriched += 1
    reviewed["controlledExecutions"] = [
        by_execution[row["executionId"]] for row in reviewed["controlledExecutions"]
    ]
    reviewed.setdefault("publicationBoundary", {})["readableCsvIncluded"] = True
    reviewed["publicationBoundary"]["datasetParquetCompanionsIncluded"] = True
    write_json(reviewed_path, reviewed)
    return {"controlledRuns": enriched, "controlledDatasetRuns": dataset_runs}


def manifest_selected_files(dataset: Path) -> tuple[Path, list[Path], dict[str, Any]]:
    current = read_json(dataset / "manifests/current.json")
    version_manifest = dataset / current["manifest"]
    manifest = read_json(version_manifest)
    files = [dataset / entry["path"] for entry in manifest["files"]]
    if not files or not all(path.is_file() for path in files):
        raise ValueError(f"current dataset version references missing files: {dataset}")
    return version_manifest, files, manifest


def build_live_readable_output(run: Path) -> dict[str, Any]:
    pa, pq = pyarrow_modules()
    datasets = sorted((run / "workspace-evidence/workspace/datasets").glob("ds_*"))
    if len(datasets) != 1:
        raise ValueError(f"expected one published dataset in {run}")
    dataset = datasets[0]
    version_manifest, files, manifest = manifest_selected_files(dataset)
    tables = [pq.read_table(path) for path in files]
    table = pa.concat_tables(tables, promote_options="default")
    sort_keys = [name for name in ("_execution_id", "_source_url", "_row_key") if name in table.column_names]
    if sort_keys:
        table = table.sort_by([(name, "ascending") for name in sort_keys])
    output = run / "readable-output"
    output.mkdir(parents=True, exist_ok=True)
    rows, columns = rows_from_table(table)
    write_csv(output / "records.csv", rows, columns)
    write_json(output / "schema.json", schema_json(table))
    source_rows = sum(int(entry["rows"]) for entry in manifest["files"])
    if source_rows != table.num_rows:
        raise ValueError(f"manifest row count differs from Parquet rows: {run}")
    write_json(output / "csv-export.json", {
        "authoritativeFormat": "Parquet",
        "csvRole": "complete row-level reviewer view with sensitive text redacted",
        "csvSanitization": [
            "email addresses are replaced with [redacted-email]",
            "absolute home paths are replaced with [redacted-home-path]",
            "credential-shaped values are replaced with [redacted-credential]",
        ],
        "exportType": "complete-current-version",
        "datasetId": manifest["datasetId"],
        "datasetVersion": manifest["version"],
        "sourceManifest": version_manifest.relative_to(run).as_posix(),
        "sourceManifestSha256": sha256(version_manifest),
        "sourceParquetFiles": [
            {
                "path": path.relative_to(run).as_posix(),
                "sha256": sha256(path),
            }
            for path in files
        ],
        "rowCount": table.num_rows,
        "columnCount": table.num_columns,
        "csv": "records.csv",
        "csvSha256": sha256(output / "records.csv"),
    })
    (output / "README.md").write_text(
        "# Human-readable dataset view\n\n"
        "`records.csv` is a complete, deterministic row-level CSV view of the current dataset version. "
        "The manifest-selected Parquet files under `workspace-evidence/` remain authoritative. "
        "Email addresses, absolute home paths, and credential-shaped text are redacted only "
        "in the CSV view. `csv-export.json` records the selected version, row count, source "
        "files, checksums, and sanitization boundary.\n",
        encoding="utf-8",
    )
    return {"rows": table.num_rows, "parquetFiles": len(files)}


def enrich_live_runs() -> dict[str, int]:
    if not QUALIFICATION_RELEASE.exists():
        QUALIFICATION_RELEASE.mkdir(parents=True)
        shutil.copyfile(
            QUALIFICATION_SOURCE_RELEASE / "qualification-summary.json",
            QUALIFICATION_RELEASE / "qualification-summary.json",
        )
        (QUALIFICATION_RELEASE / "README.md").write_text(
            "# Multi-category qualification v0.4.1\n\n"
            "This release publishes the same accepted nine-category qualification as the "
            "release candidate and adds complete, sanitized CSV views of each current "
            "manifest-selected Parquet dataset version. The 24-hour study was not started.\n",
            encoding="utf-8",
        )
        release = read_json(QUALIFICATION_SOURCE_RELEASE / "release-manifest.json")
        release["release"] = "0.4.1"
        release["status"] = "qualification-readable-evidence-published"
        release["note"] = (
            "This final qualification release adds checksum-linked CSV views of the "
            "existing Parquet evidence. It is not the separately configured 24-hour study."
        )
        write_json(QUALIFICATION_RELEASE / "release-manifest.json", release)
    manifest_path = QUALIFICATION_RELEASE / "release-manifest.json"
    release = read_json(manifest_path)
    total_rows = 0
    total_parquet = 0
    for category in release["categories"]:
        run = ROOT / category["path"]
        result = build_live_readable_output(run)
        total_rows += result["rows"]
        total_parquet += result["parquetFiles"]
        readme = run / "README.md"
        body = readme.read_text(encoding="utf-8")
        if "readable-output/records.csv" not in body:
            body += (
                "\n## Read the extracted records\n\n"
                "Open [`readable-output/records.csv`](readable-output/records.csv) to inspect "
                "the complete current dataset version directly on GitHub. The source Parquet "
                "parts remain under `workspace-evidence/`.\n"
            )
            readme.write_text(body, encoding="utf-8")
        category["readableCsv"] = f"{category['path']}/readable-output/records.csv"
        category["readableRows"] = result["rows"]
        category["checksumsSha256"] = write_checksums(run)
    release["readableCsvIncluded"] = True
    release["readableRows"] = total_rows
    write_json(manifest_path, release)
    write_checksums(QUALIFICATION_RELEASE)
    return {
        "liveRuns": len(release["categories"]),
        "liveRows": total_rows,
        "liveParquetFiles": total_parquet,
    }


def update_root_release_checksum() -> None:
    checksum_path = CONTROLLED_RELEASE / "checksums-v0.3.3.sha256"
    paths = sorted(
        path for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in {".git", ".venv", "__pycache__"} for part in path.relative_to(ROOT).parts)
        and path != checksum_path
    )
    checksum_path.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in paths),
        encoding="utf-8",
    )


def build(source_run_root: Path) -> dict[str, int]:
    result = enrich_controlled_runs(source_run_root)
    result.update(enrich_live_runs())
    update_root_release_checksum()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_run_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
