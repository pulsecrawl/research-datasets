"""Generate synthetic storage input, not historical experiment results.

SQL row expressions adapted from PulseCrawl research tooling; AGPL-3.0-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

DUCKDB_VERSION = "1.5.5"


def row_sql(execution: int, rows_per_execution: int, new_fraction: float,
            minimum: int, maximum: int) -> str:
    if execution < 0 or rows_per_execution < 1 or not 0 < new_fraction <= 1:
        raise ValueError("invalid row-generation parameters")
    if minimum < 1 or maximum < minimum:
        raise ValueError("invalid body-length range")
    new_count = max(1, round(rows_per_execution * new_fraction))
    stable_count = rows_per_execution - new_count
    span = maximum - minimum + 1
    repeats = math.ceil(maximum / 32) + 1
    identity = (
        f"CASE WHEN i < {stable_count} THEN i + 1 "
        f"ELSE 1000000000 + {execution * new_count} + i - {stable_count} END"
    )
    body_length = f"CAST({minimum} + (hash(i, {execution}) % {span}) AS BIGINT)"
    return (
        "SELECT "
        f"'Item ' || ({identity})::VARCHAR || ' execution {execution}' AS title, "
        f"substr(repeat(md5(({identity})::VARCHAR || '-{execution}'), {repeats}), 1, {body_length}) AS body, "
        f"'https://source.example/item/' || ({identity})::VARCHAR AS _source_url, "
        f"'https://source.example/item/' || ({identity})::VARCHAR AS _url_identity, "
        f"'exec-{execution:06d}' AS _execution_id, "
        f"TIMESTAMPTZ '2026-01-01T00:00:00Z' + {execution} * INTERVAL '1 hour' + i * INTERVAL '1 microsecond' AS _crawled_at, "
        f"TIMESTAMPTZ '2026-01-01T00:00:00Z' + {execution} * INTERVAL '1 hour' AS _committed_at, "
        f"({str(execution == 0).upper()} OR i >= {stable_count}) AS _is_new_url "
        f"FROM range({rows_per_execution}) AS t(i)"
    )


def generate(output: Path, rows: int, executions: int, *, format: str = "parquet") -> dict:
    import duckdb
    if duckdb.__version__ != DUCKDB_VERSION:
        raise RuntimeError("install the pinned requirements-storage.txt dependency")
    if rows < 1 or executions < 1 or rows % executions:
        raise ValueError("positive rows must be divisible by executions")
    if format not in ("parquet", "jsonl"):
        raise ValueError("unsupported output format")
    if output.exists():
        raise FileExistsError("use a new output directory; existing output is never overwritten")
    output.mkdir(parents=True)
    files = []
    connection = duckdb.connect(":memory:")
    try:
        for execution in range(executions):
            relative = Path(f"exec-{execution:06d}.{format}")
            path = output / relative
            escaped = str(path).replace("'", "''")
            options = "FORMAT PARQUET, COMPRESSION ZSTD" if format == "parquet" else "FORMAT JSON, ARRAY false"
            connection.execute(f"COPY ({row_sql(execution, rows // executions, 0.01, 128, 2048)}) TO '{escaped}' ({options})")
            files.append({
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": rows // executions,
            })
    finally:
        connection.close()
    manifest = {
        "schemaVersion": 1, "classification": "freshly-generated-synthetic-storage-input",
        "historicalExperimentOutput": False, "rows": rows, "executions": executions,
        "rowsPerExecution": rows // executions, "newFraction": 0.01,
        "minimumBodyBytes": 128, "maximumBodyBytes": 2048,
        "duckdbVersion": DUCKDB_VERSION, "format": format,
        "expectedDistinctUrlIdentities": rows // executions - max(1, round(rows // executions * 0.01))
            + executions * max(1, round(rows // executions * 0.01)),
        "files": files, "license": "AGPL-3.0-only",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rows", type=int, default=1000000)
    parser.add_argument("--executions", type=int, default=100)
    parser.add_argument("--format", choices=("parquet", "jsonl"), default="parquet")
    args = parser.parse_args()
    result = generate(args.output, args.rows, args.executions, format=args.format)
    print(json.dumps({"rows": result["rows"], "executions": result["executions"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
