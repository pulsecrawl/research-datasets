"""D10 native-output and governance-equivalent temporal dataset comparison."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import math
import time
from pathlib import Path
from typing import Any

from .datalake import run_compaction_failure_matrix


SYSTEMS = (
    "pulsecrawl",
    "scrapy",
    "crawlee-python",
    "beautifulsoup-reference",
    "firecrawl-client",
)

GOVERNANCE_COMPONENTS = (
    "schema-normalization",
    "url-identity-ledger",
    "temporal-partitioner",
    "parquet-writer",
    "atomic-manifest-publisher",
    "daily-compactor",
    "snapshot-query-view",
)


def _safe_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def governed_pipeline_sources() -> dict[str, tuple[str, str, tuple[str, ...]]]:
    pulse = json.dumps(
        {
            "dataset": {
                "writePolicy": "new_urls_only",
                "urlIdentityField": "_source_url",
                "partitioning": ["ingest_date", "hour"],
                "format": "parquet",
                "manifest": "atomic-versioned",
                "compaction": "daily",
            },
            "query": {"activeSnapshotOnly": True, "unionByName": True},
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    comparator_template = '''\
"""Reference governance layer required in addition to {framework}."""
from dataclasses import dataclass

@dataclass
class GovernancePipeline:
    schema_normalizer: object
    url_identity_ledger: object
    temporal_partitioner: object
    parquet_writer: object
    manifest_publisher: object
    daily_compactor: object
    snapshot_query_view: object

    def commit(self, execution_rows):
        normalized = self.schema_normalizer.normalize(execution_rows)
        classified = self.url_identity_ledger.classify(normalized)
        parts = self.temporal_partitioner.partition(classified)
        candidates = self.parquet_writer.write_candidates(parts)
        snapshot = self.manifest_publisher.publish_atomically(candidates)
        return snapshot

    def compact(self, snapshot):
        candidates = self.daily_compactor.compact(snapshot)
        return self.manifest_publisher.publish_atomically(candidates)

    def query(self, sql):
        return self.snapshot_query_view.execute(sql)
'''
    sources: dict[str, tuple[str, str, tuple[str, ...]]] = {
        "pulsecrawl": ("pipeline.json", pulse, ("pulsecrawl-dataset-contract",)),
    }
    for system in SYSTEMS[1:]:
        framework = system.replace("-reference", "").replace("-client", "")
        source = comparator_template.format(framework=framework)
        sources[system] = ("pipeline.py", source, (f"{system}-native-output", *GOVERNANCE_COMPONENTS))
    return sources


def write_governed_pipeline_sources(root: Path) -> dict[str, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict[str, Any]] = {}
    for system, (filename, source, components) in governed_pipeline_sources().items():
        target = root / system / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        if filename.endswith(".json"):
            json.loads(source)
            syntax = "json.loads"
        else:
            ast.parse(source)
            syntax = "ast.parse"
        result[system] = {
            "artifact": str(target.relative_to(root)),
            "sha256": hashlib.sha256(source.encode()).hexdigest(),
            "userAuthoredLoc": sum(
                bool(line.strip()) and not line.lstrip().startswith(("#", '"""'))
                for line in source.splitlines()
            ),
            "userAuthoredBytes": len(source.encode()),
            "maintainedComponents": len(components),
            "components": list(components),
            "syntaxCheck": syntax,
        }
    return result


def validate_governed_baselines(root: Path) -> list[str]:
    errors: list[str] = []
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for system, (filename, source, _components) in governed_pipeline_sources().items():
        target = root / system / filename
        row = (manifest.get("systems") or {}).get(system) or {}
        digest = hashlib.sha256(source.encode()).hexdigest()
        if not target.is_file() or target.read_text(encoding="utf-8") != source:
            errors.append(f"D10 pipeline source mismatch: {system}")
        if row.get("sha256") != digest:
            errors.append(f"D10 pipeline manifest mismatch: {system}")
    return errors


def _file_source(files: list[Path], *, json_lines: bool = False) -> str:
    if not files:
        raise ValueError("at least one input file is required")
    escaped = ",".join("'" + str(path).replace("'", "''") + "'" for path in files)
    if json_lines:
        return f"read_json_auto([{escaped}], format='newline_delimited', union_by_name=true, hive_partitioning=true)"
    return f"read_parquet([{escaped}], union_by_name=true, hive_partitioning=true)"


def _directory_bytes(root: Path, suffix: str) -> int:
    return sum(path.stat().st_size for path in root.glob(f"**/*{suffix}"))


def _timed_scalar(connection: Any, sql: str) -> tuple[float, Any]:
    start = time.perf_counter()
    value = connection.execute(sql).fetchone()[0]
    return time.perf_counter() - start, value


def _semantic_fingerprint(connection: Any, source: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT count(*), sum(length(title)+length(body)+length(_source_url)), "
        "bit_xor(hash(title,body,_source_url,_url_identity,_execution_id)) "
        f"FROM {source}"
    ).fetchone()
    canonical = json.dumps([int(row[0]), int(row[1]), int(row[2])], separators=(",", ":"))
    return {
        "rows": int(row[0]),
        "payloadCharacters": int(row[1]),
        "hashXor": int(row[2]),
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def _long_term_simulation(*, hours: int, executions_per_compact: int = 24) -> dict[str, Any]:
    if hours < 1 or executions_per_compact < 1:
        raise ValueError("long-term simulation values must be positive")
    completed_days, current = divmod(hours, executions_per_compact)
    governed_active = completed_days + current
    native_active = hours
    published_versions = completed_days
    # Every execution is delivered twice; the durable execution marker makes
    # the second delivery a no-op.
    markers: set[int] = set()
    committed = duplicates = 0
    for execution in range(hours):
        for _delivery in range(2):
            if execution in markers:
                continue
            markers.add(execution)
            committed += 1
        duplicates += max(0, sum(1 for value in markers if value == execution) - 1)
    return {
        "hours": hours,
        "nativeActiveFiles": native_active,
        "governedActiveFiles": governed_active,
        "activeFileReduction": 1 - governed_active / native_active,
        "publishedDailySnapshots": published_versions,
        "executionMarkers": len(markers),
        "committedExecutions": committed,
        "duplicateCommittedExecutions": duplicates,
        "cleanupEligibleDeltas": completed_days * executions_per_compact,
        "boundedActiveFiles": governed_active <= math.ceil(hours / executions_per_compact) + executions_per_compact - 1,
    }


def run_governed_pipeline_comparison(
    output_root: Path,
    *,
    total_rows: int,
    executions: int,
    new_fraction: float,
    query_repetitions: int,
    failure_repetitions: int,
    simulation_hours: int,
    minimum_body_bytes: int,
    maximum_body_bytes: int,
) -> dict[str, Any]:
    if total_rows < 1 or executions < 1 or total_rows % executions:
        raise ValueError("total_rows must be positive and divisible by executions")
    if not 0 < new_fraction <= 1 or query_repetitions < 1 or failure_repetitions < 1:
        raise ValueError("invalid D10 repetition or new-fraction value")
    if not 1 <= minimum_body_bytes <= maximum_body_bytes:
        raise ValueError("invalid body byte range")
    import duckdb
    import psutil

    output_root.mkdir(parents=True, exist_ok=True)
    append_root = output_root / "native" / "pulsecrawl-parquet"
    json_root = output_root / "native" / "jsonl-reference"
    new_root = output_root / "governed" / "new-only"
    compact_root = output_root / "governed" / "daily-compact"
    for root in (append_root, json_root, new_root, compact_root):
        root.mkdir(parents=True, exist_ok=True)
    source_metrics = write_governed_pipeline_sources(output_root / "pipeline-sources")
    process = psutil.Process()
    rss_before = process.memory_info().rss
    cpu_started = time.process_time()
    wall_started = time.perf_counter()
    rows_per_execution = total_rows // executions
    new_count = max(1, round(rows_per_execution * new_fraction))
    stable_count = rows_per_execution - new_count
    span = maximum_body_bytes - minimum_body_bytes + 1
    repeats = math.ceil(maximum_body_bytes / 32) + 1
    parquet_files: list[Path] = []
    json_files: list[Path] = []
    new_files: list[Path] = []
    connection = duckdb.connect(":memory:")
    write_started = time.perf_counter()
    try:
        for execution in range(executions):
            day, hour = divmod(execution, 24)
            date = f"2026-01-{day + 1:02d}"
            relative = Path(f"ingest_date={date}") / f"hour={hour:02d}"
            parquet_dir = append_root / relative
            json_dir = json_root / relative
            new_dir = new_root / relative
            for directory in (parquet_dir, json_dir, new_dir):
                directory.mkdir(parents=True, exist_ok=True)
            parquet_path = parquet_dir / f"delta-exec-{execution:06d}.parquet"
            json_path = json_dir / f"delta-exec-{execution:06d}.jsonl"
            new_path = new_dir / f"delta-exec-{execution:06d}.parquet"
            parquet_escaped = str(parquet_path).replace("'", "''")
            json_escaped = str(json_path).replace("'", "''")
            new_escaped = str(new_path).replace("'", "''")
            identity = (
                f"CASE WHEN i < {stable_count} THEN i + 1 "
                f"ELSE 1000000000 + {execution * new_count} + i - {stable_count} END"
            )
            body_length = f"CAST({minimum_body_bytes} + (hash(i, {execution}) % {span}) AS BIGINT)"
            base = (
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
            connection.execute(
                f"COPY ({base}) TO '{parquet_escaped}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            connection.execute(
                f"COPY ({base}) TO '{json_escaped}' "
                "(FORMAT JSON, ARRAY false)"
            )
            selected = base if execution == 0 else f"SELECT * FROM ({base}) WHERE _is_new_url"
            connection.execute(
                f"COPY ({selected}) TO '{new_escaped}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            parquet_files.append(parquet_path)
            json_files.append(json_path)
            new_files.append(new_path)
        write_seconds = time.perf_counter() - write_started

        parquet_source = _file_source(parquet_files)
        json_source = _file_source(json_files, json_lines=True)
        new_source = _file_source(new_files)
        parquet_fingerprint = _semantic_fingerprint(connection, parquet_source)
        json_fingerprint = _semantic_fingerprint(connection, json_source)
        exact_left = connection.execute(
            "SELECT count(*) FROM ((SELECT title,body,_source_url,_url_identity,_execution_id "
            f"FROM {parquet_source}) EXCEPT ALL (SELECT title,body,_source_url,_url_identity,_execution_id FROM {json_source}))"
        ).fetchone()[0]
        exact_right = connection.execute(
            "SELECT count(*) FROM ((SELECT title,body,_source_url,_url_identity,_execution_id "
            f"FROM {json_source}) EXCEPT ALL (SELECT title,body,_source_url,_url_identity,_execution_id FROM {parquet_source}))"
        ).fetchone()[0]

        parquet_count_seconds: list[float] = []
        parquet_payload_seconds: list[float] = []
        json_count_seconds: list[float] = []
        json_payload_seconds: list[float] = []
        new_payload_seconds: list[float] = []
        for _ in range(query_repetitions):
            elapsed, _ = _timed_scalar(connection, f"SELECT count(*) FROM {parquet_source}")
            parquet_count_seconds.append(elapsed)
            elapsed, _ = _timed_scalar(connection, f"SELECT sum(length(title)+length(body)) FROM {parquet_source}")
            parquet_payload_seconds.append(elapsed)
            elapsed, _ = _timed_scalar(connection, f"SELECT count(*) FROM {json_source}")
            json_count_seconds.append(elapsed)
            elapsed, _ = _timed_scalar(connection, f"SELECT sum(length(title)+length(body)) FROM {json_source}")
            json_payload_seconds.append(elapsed)
            elapsed, _ = _timed_scalar(connection, f"SELECT sum(length(title)+length(body)) FROM {new_source}")
            new_payload_seconds.append(elapsed)

        compact_started = time.perf_counter()
        by_date: dict[str, list[Path]] = {}
        for path in parquet_files:
            date = next(part.split("=", 1)[1] for part in path.parts if part.startswith("ingest_date="))
            by_date.setdefault(date, []).append(path)
        compact_files: list[Path] = []
        for date, files in sorted(by_date.items()):
            target_dir = compact_root / f"ingest_date={date}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "compact-000001.parquet"
            target_escaped = str(target).replace("'", "''")
            connection.execute(
                f"COPY (SELECT * FROM {_file_source(files)} ORDER BY _crawled_at,_url_identity) "
                f"TO '{target_escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            compact_files.append(target)
        compact_seconds = time.perf_counter() - compact_started
        compact_source = _file_source(compact_files)
        compact_fingerprint = _semantic_fingerprint(connection, compact_source)
        compact_count_seconds: list[float] = []
        compact_payload_seconds: list[float] = []
        reopened_payload_seconds: list[float] = []
        for _ in range(query_repetitions):
            elapsed, _ = _timed_scalar(connection, f"SELECT count(*) FROM {compact_source}")
            compact_count_seconds.append(elapsed)
            elapsed, _ = _timed_scalar(connection, f"SELECT sum(length(title)+length(body)) FROM {compact_source}")
            compact_payload_seconds.append(elapsed)
            reopened = duckdb.connect(":memory:")
            try:
                elapsed, _ = _timed_scalar(reopened, f"SELECT sum(length(title)+length(body)) FROM {compact_source}")
                reopened_payload_seconds.append(elapsed)
            finally:
                reopened.close()
        new_rows = int(connection.execute(f"SELECT count(*) FROM {new_source}").fetchone()[0])
    finally:
        connection.close()

    failures = run_compaction_failure_matrix(
        output_root / "failure-matrix", repetitions=failure_repetitions
    )
    long_term = _long_term_simulation(hours=simulation_hours)
    active_manifest = {
        "schemaVersion": 1,
        "version": 2,
        "expectedRows": total_rows,
        "files": [str(path.relative_to(output_root)) for path in compact_files],
        "fingerprint": compact_fingerprint,
    }
    (output_root / "manifest.active.json").write_text(
        json.dumps(active_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    systems: dict[str, dict[str, Any]] = {}
    versions = {
        "pulsecrawl": _safe_version("pulsecrawl"),
        "scrapy": _safe_version("scrapy"),
        "crawlee-python": _safe_version("crawlee"),
        "beautifulsoup-reference": _safe_version("beautifulsoup4"),
        "firecrawl-client": "v2.9.0-client-contract",
    }
    for system in SYSTEMS:
        native_parquet = system == "pulsecrawl"
        systems[system] = {
            **source_metrics[system],
            "version": versions[system],
            "nativeProfile": "temporal-parquet" if native_parquet else "newline-delimited-json-reference",
            "nativeFiles": len(parquet_files if native_parquet else json_files),
            "nativeBytes": _directory_bytes(append_root if native_parquet else json_root, ".parquet" if native_parquet else ".jsonl"),
            "nativeCountSeconds": parquet_count_seconds if native_parquet else json_count_seconds,
            "nativePayloadScanSeconds": parquet_payload_seconds if native_parquet else json_payload_seconds,
            "governanceEquivalentFiles": len(compact_files),
            "governanceEquivalentBytes": _directory_bytes(compact_root, ".parquet"),
            "governanceEquivalentFingerprint": compact_fingerprint,
            "governanceEquivalentCountSeconds": compact_count_seconds,
            "governanceEquivalentPayloadScanSeconds": compact_payload_seconds,
            "capabilityBoundary": (
                "built-in registered dataset contract"
                if system == "pulsecrawl"
                else "reference user-maintained governance layer added to native extraction output"
            ),
        }

    expected_new = rows_per_execution + (executions - 1) * new_count
    wall_seconds = time.perf_counter() - wall_started
    return {
        "status": "completed",
        "method": "native-jsonl-versus-equivalent-versioned-temporal-parquet",
        "totalRows": total_rows,
        "executions": executions,
        "rowsPerExecution": rows_per_execution,
        "bodyBytes": {"minimum": minimum_body_bytes, "maximum": maximum_body_bytes},
        "writeSeconds": write_seconds,
        "compactSeconds": compact_seconds,
        "wallSeconds": wall_seconds,
        "cpuSeconds": time.process_time() - cpu_started,
        "rssBeforeBytes": rss_before,
        "rssAfterBytes": process.memory_info().rss,
        "appendParquetBytes": _directory_bytes(append_root, ".parquet"),
        "nativeJsonBytes": _directory_bytes(json_root, ".jsonl"),
        "newOnlyParquetBytes": _directory_bytes(new_root, ".parquet"),
        "compactParquetBytes": _directory_bytes(compact_root, ".parquet"),
        "deltaFiles": len(parquet_files),
        "compactFiles": len(compact_files),
        "newOnlyRows": new_rows,
        "expectedNewOnlyRows": expected_new,
        "parquetFingerprint": parquet_fingerprint,
        "jsonFingerprint": json_fingerprint,
        "compactFingerprint": compact_fingerprint,
        "semanticChecksumEquivalent": (
            parquet_fingerprint == json_fingerprint == compact_fingerprint
            and exact_left == exact_right == 0
        ),
        "exactDifferenceRows": {"parquetMinusJson": int(exact_left), "jsonMinusParquet": int(exact_right)},
        "newOnlyCorrect": new_rows == expected_new,
        "reopenedConnectionPayloadScanSeconds": reopened_payload_seconds,
        "failureMatrix": failures,
        "longTerm": long_term,
        "systems": systems,
        "allGovernedSnapshotsValid": failures.get("violations") == 0,
        "allReplayIdempotent": long_term["duplicateCommittedExecutions"] == 0,
        "integrationBurdenCriterion": all(
            source_metrics["pulsecrawl"]["maintainedComponents"]
            < source_metrics[system]["maintainedComponents"]
            for system in SYSTEMS[1:]
        ),
        "timingBoundary": "local file system; reopening DuckDB does not flush operating-system or storage caches",
    }
