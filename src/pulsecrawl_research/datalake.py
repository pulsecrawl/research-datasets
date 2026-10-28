"""Deterministic Parquet/data-lake comparison workloads."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class TemporalWorkload:
    executions: int
    rows_per_execution: int
    new_fraction: float = 0.10
    seed: int = 4703

    def __post_init__(self) -> None:
        if self.executions < 1 or self.rows_per_execution < 1:
            raise ValueError("execution and row counts must be positive")
        if not 0 < self.new_fraction <= 1:
            raise ValueError("new_fraction must be in (0, 1]")

    def execution_rows(self, execution: int) -> list[dict[str, Any]]:
        if not 0 <= execution < self.executions:
            raise IndexError(execution)
        new_count = max(1, round(self.rows_per_execution * self.new_fraction))
        stable_count = self.rows_per_execution - new_count
        base = execution * new_count
        identities = list(range(1, stable_count + 1)) + list(
            range(1_000_000 + base, 1_000_000 + base + new_count)
        )
        committed = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=execution)
        rows: list[dict[str, Any]] = []
        for offset, identity in enumerate(identities):
            url = f"https://source.example/item/{identity}"
            rows.append(
                {
                    "title": f"Item {identity} execution {execution}",
                    "_source_url": url,
                    "_url_identity": url,
                    "_execution_id": f"exec-{execution:06d}",
                    "_job_id": "job-research",
                    "_crawled_at": committed + timedelta(milliseconds=offset),
                    "_committed_at": committed,
                    "_is_new_url": execution == 0 or identity >= 1_000_000 + base,
                }
            )
        return rows

    def all_rows(self) -> Iterator[tuple[int, list[dict[str, Any]]]]:
        for execution in range(self.executions):
            yield execution, self.execution_rows(execution)


def _timed_query(connection, query: str) -> tuple[float, Any]:
    started = time.perf_counter()
    value = connection.execute(query).fetchone()[0]
    return time.perf_counter() - started, value


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _manifest(version: int, files: list[Path], root: Path, expected_rows: int) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schemaVersion": 1,
        "version": version,
        "expectedRows": expected_rows,
        "files": [path.relative_to(root).as_posix() for path in files],
    }
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    value["sha256"] = hashlib.sha256(payload).hexdigest()
    return value


def run_parquet_benchmark(
    workload: TemporalWorkload,
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    try:
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        return {"status": "unavailable", "reason": str(exc)}

    temporary = None
    if output_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="pulsecrawl-datalake-")
        output_root = Path(temporary.name)
    output_root.mkdir(parents=True, exist_ok=True)
    per_execution = output_root / "per-execution"
    partitioned = output_root / "partitioned"
    new_only = output_root / "new-only"
    for directory in (per_execution, partitioned, new_only):
        directory.mkdir(parents=True, exist_ok=True)

    all_files: list[Path] = []
    partition_files: list[Path] = []
    new_files: list[Path] = []
    seen: set[str] = set()
    write_started = time.perf_counter()
    for execution, rows in workload.all_rows():
        table = pa.Table.from_pylist(rows)
        execution_path = per_execution / f"exec-{execution:06d}.parquet"
        pq.write_table(table, execution_path, compression="zstd")
        all_files.append(execution_path)

        committed = rows[0]["_committed_at"]
        part_dir = (
            partitioned
            / f"ingest_date={committed.date().isoformat()}"
            / f"hour={committed.hour:02d}"
        )
        part_dir.mkdir(parents=True, exist_ok=True)
        part_path = part_dir / f"delta-exec-{execution:06d}.parquet"
        pq.write_table(table, part_path, compression="zstd")
        partition_files.append(part_path)

        emitted: list[dict[str, Any]] = []
        for row in rows:
            identity = str(row["_url_identity"])
            if identity in seen:
                continue
            seen.add(identity)
            emitted.append(row)
        if emitted:
            new_dir = (
                new_only
                / f"ingest_date={committed.date().isoformat()}"
                / f"hour={committed.hour:02d}"
            )
            new_dir.mkdir(parents=True, exist_ok=True)
            new_path = new_dir / f"delta-exec-{execution:06d}.parquet"
            pq.write_table(pa.Table.from_pylist(emitted), new_path, compression="zstd")
            new_files.append(new_path)
    write_seconds = time.perf_counter() - write_started

    expected_rows = sum(len(rows) for _, rows in workload.all_rows())
    manifest = _manifest(len(partition_files), partition_files, output_root, expected_rows)
    _atomic_json(output_root / "manifest.json", manifest)

    def source(files: list[Path]) -> str:
        escaped = ",".join("'" + str(path).replace("'", "''") + "'" for path in files)
        return f"read_parquet([{escaped}], union_by_name=true, hive_partitioning=true)"

    connection = duckdb.connect(":memory:")
    try:
        all_query_seconds, all_count = _timed_query(
            connection, f"SELECT count(*) FROM {source(partition_files)}"
        )
        new_query_seconds, new_count = _timed_query(
            connection, f"SELECT count(*) FROM {source(new_files)}"
        )
        latest = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=workload.executions)
        cutoff = latest - timedelta(hours=1)
        hourly_seconds, hourly_count = _timed_query(
            connection,
            f"SELECT count(*) FROM {source(partition_files)} "
            f"WHERE _crawled_at >= TIMESTAMPTZ '{cutoff.isoformat()}'",
        )
        compact_path = output_root / "compact.parquet"
        compact_sql_path = str(compact_path).replace("'", "''")
        compact_started = time.perf_counter()
        connection.execute(
            f"COPY (SELECT * FROM {source(partition_files)} ORDER BY _crawled_at, _url_identity) "
            f"TO '{compact_sql_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        compact_seconds = time.perf_counter() - compact_started
        compact_query_seconds, compact_count = _timed_query(
            connection, f"SELECT count(*) FROM read_parquet('{str(compact_path)}')"
        )
    finally:
        connection.close()

    def bytes_of(files: list[Path]) -> int:
        return sum(path.stat().st_size for path in files)

    compact_manifest = _manifest(
        int(manifest["version"]) + 1, [compact_path], output_root, int(compact_count)
    )
    _atomic_json(output_root / "manifest.compact.json", compact_manifest)
    result = {
        "status": "completed",
        "executions": workload.executions,
        "rowsPerExecution": workload.rows_per_execution,
        "appendAllRows": all_count,
        "newOnlyRows": new_count,
        "hourlyRows": hourly_count,
        "fileCount": len(partition_files),
        "newOnlyFileCount": len(new_files),
        "appendAllBytes": bytes_of(partition_files),
        "newOnlyBytes": bytes_of(new_files),
        "compactBytes": compact_path.stat().st_size,
        "writeSeconds": write_seconds,
        "allQuerySeconds": all_query_seconds,
        "newOnlyQuerySeconds": new_query_seconds,
        "hourlyQuerySeconds": hourly_seconds,
        "compactSeconds": compact_seconds,
        "compactQuerySeconds": compact_query_seconds,
        "snapshotCountBefore": all_count,
        "snapshotCountAfter": compact_count,
        "snapshotConsistent": all_count == compact_count,
        "manifestVersion": manifest["version"],
        "compactManifestVersion": compact_manifest["version"],
        "deltaFilesRetained": all(path.exists() for path in partition_files),
        "outputRoot": str(output_root),
    }
    if temporary is not None:
        temporary.cleanup()
    return result


def run_snapshot_stress(
    output_root: Path, *, readers: int = 8, publications: int = 100
) -> dict[str, Any]:
    """Verify readers observe complete old/new manifests during atomic publication."""

    if readers < 1 or publications < 1:
        raise ValueError("readers and publications must be positive")
    import pyarrow.parquet as pq

    original = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
    compact = json.loads((output_root / "manifest.compact.json").read_text(encoding="utf-8"))
    active = output_root / "manifest.active.json"
    _atomic_json(active, original)
    stop = threading.Event()
    lock = threading.Lock()
    reads = violations = 0
    observed_versions: set[int] = set()
    injected_before_swap = injected_after_swap = 0

    def read_loop() -> None:
        nonlocal reads, violations
        local_reads = local_violations = 0
        local_versions: set[int] = set()
        while not stop.is_set():
            try:
                snapshot = json.loads(active.read_text(encoding="utf-8"))
                count = sum(
                    pq.ParquetFile(output_root / relative).metadata.num_rows
                    for relative in snapshot["files"]
                )
                local_violations += int(count != int(snapshot["expectedRows"]))
                local_versions.add(int(snapshot["version"]))
            except (FileNotFoundError, json.JSONDecodeError, KeyError, OSError):
                local_violations += 1
            local_reads += 1
        with lock:
            reads += local_reads
            violations += local_violations
            observed_versions.update(local_versions)

    with ThreadPoolExecutor(max_workers=readers) as pool:
        futures = [pool.submit(read_loop) for _ in range(readers)]
        for index in range(publications):
            candidate = compact if index % 2 else original
            # A failed writer may leave any bytes in a private temporary file,
            # but must never expose them through the active pointer.
            if index % 10 == 0:
                failed_temp = active.with_name(f".{active.name}.failed-{index}")
                failed_temp.write_text('{"version":', encoding="utf-8")
                failed_temp.unlink()
                injected_before_swap += 1
                continue
            _atomic_json(active, candidate)
            # A crash after the atomic replacement leaves a complete new
            # snapshot. No rollback or mixed input/replacement set is valid.
            if index % 10 == 1:
                injected_after_swap += 1
        time.sleep(0.02)
        stop.set()
        for future in futures:
            future.result()
    return {
        "status": "completed",
        "readers": readers,
        "publications": publications,
        "reads": reads,
        "violations": violations,
        "injectedFailuresBeforeSwap": injected_before_swap,
        "injectedFailuresAfterSwap": injected_after_swap,
        "observedVersions": sorted(observed_versions),
        "atomic": violations == 0,
    }


def run_snapshot_publication_ablation(
    output_root: Path, *, readers: int = 4, publications: int = 30
) -> dict[str, Any]:
    """Compare atomic pointer replacement with an in-place manifest rewrite."""

    atomic_root = output_root / "atomic"
    atomic_workload = TemporalWorkload(2, 10)
    run_parquet_benchmark(atomic_workload, output_root=atomic_root)
    atomic = run_snapshot_stress(atomic_root, readers=readers, publications=publications)
    import pyarrow as pa
    import pyarrow.parquet as pq

    unsafe_root = output_root / "unsafe"
    unsafe_root.mkdir(parents=True, exist_ok=True)
    old_file = unsafe_root / "old.parquet"
    new_file = unsafe_root / "new.parquet"
    pq.write_table(pa.table({"value": [1, 2]}), old_file)
    pq.write_table(pa.table({"value": [1, 2, 3]}), new_file)
    snapshots = [_manifest(1, [old_file], unsafe_root, 2), _manifest(2, [new_file], unsafe_root, 3)]
    active = unsafe_root / "manifest.active.json"
    _atomic_json(active, snapshots[0])
    observed_reads = violations = 0

    def observe() -> None:
        nonlocal observed_reads, violations
        observed_reads += 1
        try:
            snapshot = json.loads(active.read_text(encoding="utf-8"))
            count = sum(pq.ParquetFile(unsafe_root / relative).metadata.num_rows for relative in snapshot["files"])
            violations += int(count != int(snapshot["expectedRows"]))
        except (json.JSONDecodeError, KeyError, OSError):
            violations += 1

    for index in range(publications):
        candidate = snapshots[index % 2]
        active.write_text('{"version":', encoding="utf-8")
        observe()
        active.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
        observe()
    unsafe = {"status": "completed", "method": "in-place-active-manifest-rewrite", "publications": publications, "reads": observed_reads, "violations": violations, "atomic": violations == 0}
    passed = atomic["violations"] == 0 and unsafe["violations"] > 0
    return {
        "status": "completed",
        "atomicPublication": atomic,
        "inPlacePublication": unsafe,
        "causalResult": {"atomicHasZeroViolations": atomic["violations"] == 0, "inPlaceExposesPartialState": unsafe["violations"] > 0},
        "allCausalChecksPassed": passed,
    }


def run_runtime_equivalence(workload: TemporalWorkload, output_root: Path) -> dict[str, Any]:
    """Compare reference truth with rows read back from the Parquet artifact."""

    try:
        import duckdb
    except ImportError as exc:
        return {"status": "unavailable", "reason": str(exc)}
    expected = sorted(
        (str(row["_execution_id"]), str(row["_url_identity"]), str(row["title"]))
        for _, rows in workload.all_rows()
        for row in rows
    )
    files = sorted((output_root / "partitioned").glob("**/*.parquet"))
    escaped = ",".join("'" + str(path).replace("'", "''") + "'" for path in files)
    connection = duckdb.connect(":memory:")
    try:
        actual = sorted(
            (str(execution), str(identity), str(title))
            for execution, identity, title in connection.execute(
                "SELECT _execution_id,_url_identity,title "
                f"FROM read_parquet([{escaped}], union_by_name=true, hive_partitioning=true)"
            ).fetchall()
        )
    finally:
        connection.close()
    expected_hash = hashlib.sha256(json.dumps(expected, separators=(",", ":")).encode()).hexdigest()
    actual_hash = hashlib.sha256(json.dumps(actual, separators=(",", ":")).encode()).hexdigest()
    return {
        "status": "completed",
        "expectedRows": len(expected),
        "actualRows": len(actual),
        "expectedSha256": expected_hash,
        "actualSha256": actual_hash,
        "equivalent": expected == actual,
    }


def _duckdb_source(files: list[Path]) -> str:
    if not files:
        raise ValueError("at least one Parquet file is required")
    escaped = ",".join("'" + str(path).replace("'", "''") + "'" for path in files)
    return f"read_parquet([{escaped}], union_by_name=true, hive_partitioning=true)"


def _directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.glob("**/*.parquet"))


def run_scale_benchmark(
    *,
    total_rows: int,
    executions: int,
    new_fraction: float,
    output_root: Path,
    query_repetitions: int = 5,
) -> dict[str, Any]:
    """Generate and query a large temporal lake without Python row materialization."""

    if total_rows < 1 or executions < 1 or total_rows % executions:
        raise ValueError("total_rows must be positive and divisible by executions")
    if not 0 < new_fraction <= 1 or query_repetitions < 1:
        raise ValueError("invalid new_fraction or query_repetitions")
    try:
        import duckdb
    except ImportError as exc:
        return {"status": "unavailable", "reason": str(exc)}

    rows_per_execution = total_rows // executions
    new_count = max(1, round(rows_per_execution * new_fraction))
    stable_count = rows_per_execution - new_count
    append_root = output_root / "append-all"
    new_root = output_root / "new-only"
    compact_root = output_root / "compact"
    for directory in (append_root, new_root, compact_root):
        directory.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    append_files: list[Path] = []
    new_files: list[Path] = []
    write_started = time.perf_counter()
    try:
        for execution in range(executions):
            committed = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=execution)
            relative = Path(f"ingest_date={committed.date().isoformat()}") / f"hour={committed.hour:02d}"
            append_dir = append_root / relative
            new_dir = new_root / relative
            append_dir.mkdir(parents=True, exist_ok=True)
            new_dir.mkdir(parents=True, exist_ok=True)
            append_path = append_dir / f"delta-exec-{execution:06d}.parquet"
            new_path = new_dir / f"delta-exec-{execution:06d}.parquet"
            append_escaped = str(append_path).replace("'", "''")
            new_escaped = str(new_path).replace("'", "''")
            timestamp = committed.isoformat()
            identity = (
                f"CASE WHEN i < {stable_count} THEN i + 1 "
                f"ELSE 1000000000 + {execution * new_count} + i - {stable_count} END"
            )
            base_select = (
                "SELECT "
                f"'Item ' || ({identity})::VARCHAR || ' execution {execution}' AS title, "
                f"'https://source.example/item/' || ({identity})::VARCHAR AS _source_url, "
                f"'https://source.example/item/' || ({identity})::VARCHAR AS _url_identity, "
                f"'exec-{execution:06d}' AS _execution_id, 'job-research' AS _job_id, "
                f"TIMESTAMPTZ '{timestamp}' + i * INTERVAL '1 microsecond' AS _crawled_at, "
                f"TIMESTAMPTZ '{timestamp}' AS _committed_at, "
                f"({str(execution == 0).upper()} OR i >= {stable_count}) AS _is_new_url "
                f"FROM range({rows_per_execution}) AS t(i)"
            )
            connection.execute(
                f"COPY ({base_select}) TO '{append_escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            append_files.append(append_path)
            if execution == 0:
                new_select = base_select
            else:
                new_select = f"SELECT * FROM ({base_select}) WHERE _is_new_url"
            connection.execute(
                f"COPY ({new_select}) TO '{new_escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            new_files.append(new_path)
        write_seconds = time.perf_counter() - write_started

        append_source = _duckdb_source(append_files)
        new_source = _duckdb_source(new_files)
        expected_new = rows_per_execution + (executions - 1) * new_count
        count_seconds: list[float] = []
        hourly_seconds: list[float] = []
        new_seconds: list[float] = []
        all_scan_seconds: list[float] = []
        hourly_scan_seconds: list[float] = []
        new_scan_seconds: list[float] = []
        cutoff = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=executions - 1)
        append_count = new_only_count = hourly_count = 0
        append_scan_value = new_scan_value = hourly_scan_value = 0
        for _ in range(query_repetitions):
            elapsed, append_count = _timed_query(connection, f"SELECT count(*) FROM {append_source}")
            count_seconds.append(elapsed)
            elapsed, new_only_count = _timed_query(connection, f"SELECT count(*) FROM {new_source}")
            new_seconds.append(elapsed)
            elapsed, hourly_count = _timed_query(
                connection,
                f"SELECT count(*) FROM {append_source} WHERE _crawled_at >= TIMESTAMPTZ '{cutoff.isoformat()}'",
            )
            hourly_seconds.append(elapsed)
            elapsed, append_scan_value = _timed_query(
                connection, f"SELECT sum(length(title) + length(_source_url)) FROM {append_source}"
            )
            all_scan_seconds.append(elapsed)
            elapsed, new_scan_value = _timed_query(
                connection, f"SELECT sum(length(title) + length(_source_url)) FROM {new_source}"
            )
            new_scan_seconds.append(elapsed)
            elapsed, hourly_scan_value = _timed_query(
                connection,
                f"SELECT sum(length(title) + length(_source_url)) FROM {append_source} "
                f"WHERE _crawled_at >= TIMESTAMPTZ '{cutoff.isoformat()}'",
            )
            hourly_scan_seconds.append(elapsed)

        by_date: dict[str, list[Path]] = {}
        for path in append_files:
            date_part = next(part for part in path.parts if part.startswith("ingest_date="))
            by_date.setdefault(date_part.split("=", 1)[1], []).append(path)
        compact_files: list[Path] = []
        compact_started = time.perf_counter()
        for date, files in sorted(by_date.items()):
            target_dir = compact_root / f"ingest_date={date}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "compact-000001.parquet"
            target_escaped = str(target).replace("'", "''")
            connection.execute(
                f"COPY (SELECT * FROM {_duckdb_source(files)} ORDER BY _crawled_at, _url_identity) "
                f"TO '{target_escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            compact_files.append(target)
        compact_seconds = time.perf_counter() - compact_started
        compact_source = _duckdb_source(compact_files)
        compact_query_seconds: list[float] = []
        compact_scan_seconds: list[float] = []
        compact_count = 0
        compact_scan_value = 0
        for _ in range(query_repetitions):
            elapsed, compact_count = _timed_query(connection, f"SELECT count(*) FROM {compact_source}")
            compact_query_seconds.append(elapsed)
            elapsed, compact_scan_value = _timed_query(
                connection, f"SELECT sum(length(title) + length(_source_url)) FROM {compact_source}"
            )
            compact_scan_seconds.append(elapsed)
    finally:
        connection.close()

    manifest = _manifest(1, append_files, output_root, total_rows)
    compact_manifest = _manifest(2, compact_files, output_root, total_rows)
    _atomic_json(output_root / "manifest.v1.json", manifest)
    _atomic_json(output_root / "manifest.v2.json", compact_manifest)
    _atomic_json(output_root / "manifest.active.json", compact_manifest)
    return {
        "status": "completed",
        "method": "duckdb-generated-hourly-parquet-deltas-and-daily-compaction",
        "totalRows": total_rows,
        "executions": executions,
        "rowsPerExecution": rows_per_execution,
        "newFraction": new_fraction,
        "appendAllRows": int(append_count),
        "newOnlyRows": int(new_only_count),
        "expectedNewOnlyRows": int(expected_new),
        "lastHourRows": int(hourly_count),
        "deltaFiles": len(append_files),
        "dailyCompactFiles": len(compact_files),
        "appendAllBytes": _directory_bytes(append_root),
        "newOnlyBytes": _directory_bytes(new_root),
        "compactBytes": _directory_bytes(compact_root),
        "writeSeconds": write_seconds,
        "allQuerySeconds": count_seconds,
        "newOnlyQuerySeconds": new_seconds,
        "lastHourQuerySeconds": hourly_seconds,
        "allPayloadScanSeconds": all_scan_seconds,
        "newOnlyPayloadScanSeconds": new_scan_seconds,
        "lastHourPayloadScanSeconds": hourly_scan_seconds,
        "allPayloadChecksum": int(append_scan_value),
        "newOnlyPayloadChecksum": int(new_scan_value),
        "lastHourPayloadChecksum": int(hourly_scan_value),
        "compactSeconds": compact_seconds,
        "compactQuerySeconds": compact_query_seconds,
        "compactPayloadScanSeconds": compact_scan_seconds,
        "compactPayloadChecksum": int(compact_scan_value),
        "snapshotVersions": [1, 2],
        "snapshotConsistent": int(append_count) == int(compact_count) == total_rows and int(append_scan_value) == int(compact_scan_value),
        "newOnlyCorrect": int(new_only_count) == expected_new,
        "deltaFilesRetainedAfterPublication": all(path.exists() for path in append_files),
        "cleanupPolicy": "eligible only after active manifest v2 is durable; retained in experiment",
        "syntheticCompressionCaveat": "deterministic repeated strings compress unusually well; bytes and latency apply only to this registered local workload",
        "outputRoot": str(output_root),
    }


def run_scale_matrix(output_root: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        rows = int(case["totalRows"])
        results.append(
            run_scale_benchmark(
                total_rows=rows,
                executions=int(case["executions"]),
                new_fraction=float(case.get("newFraction", 0.01)),
                output_root=output_root / f"rows-{rows}",
                query_repetitions=int(case.get("queryRepetitions", 5)),
            )
        )
    return {
        "status": "completed" if all(row["status"] == "completed" for row in results) else "unavailable",
        "cases": results,
        "allCorrect": all(row.get("snapshotConsistent") and row.get("newOnlyCorrect") for row in results),
    }


def run_temporal_query_benchmark(output_root: Path, *, query_repetitions: int = 30) -> dict[str, Any]:
    scale = run_scale_benchmark(
        total_rows=1_000_000,
        executions=100,
        new_fraction=0.01,
        output_root=output_root,
        query_repetitions=query_repetitions,
    )
    if scale.get("status") != "completed":
        return scale
    return {
        "status": "completed",
        "method": "one-million-row-ingestion-time-versus-source-time-query-matrix",
        "scale": scale,
        "queries": {
            "lastIngestHour": {"expectedRows": scale["rowsPerExecution"], "actualRows": scale["lastHourRows"], "seconds": scale["lastHourQuerySeconds"]},
            "allAppendRows": {"expectedRows": 1_000_000, "actualRows": scale["appendAllRows"], "seconds": scale["allQuerySeconds"]},
            "newUrlRows": {"expectedRows": scale["expectedNewOnlyRows"], "actualRows": scale["newOnlyRows"], "seconds": scale["newOnlyQuerySeconds"]},
            "dailyCompactedRows": {"expectedRows": 1_000_000, "actualRows": scale["appendAllRows"], "seconds": scale["compactQuerySeconds"]},
            "allAppendPayloadScan": {"checksum": scale["allPayloadChecksum"], "seconds": scale["allPayloadScanSeconds"]},
            "lastIngestHourPayloadScan": {"checksum": scale["lastHourPayloadChecksum"], "seconds": scale["lastHourPayloadScanSeconds"]},
            "newUrlPayloadScan": {"checksum": scale["newOnlyPayloadChecksum"], "seconds": scale["newOnlyPayloadScanSeconds"]},
            "dailyCompactedPayloadScan": {"checksum": scale["compactPayloadChecksum"], "seconds": scale["compactPayloadScanSeconds"]},
        },
        "allCountsCorrect": all(row["expectedRows"] == row["actualRows"] for row in {
            "last": {"expectedRows": scale["rowsPerExecution"], "actualRows": scale["lastHourRows"]},
            "all": {"expectedRows": 1_000_000, "actualRows": scale["appendAllRows"]},
            "new": {"expectedRows": scale["expectedNewOnlyRows"], "actualRows": scale["newOnlyRows"]},
        }.values()),
    }


def run_compaction_failure_matrix(output_root: Path, *, repetitions: int = 30) -> dict[str, Any]:
    """Inject every publication boundary and verify active snapshots remain whole."""

    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    import pyarrow as pa
    import pyarrow.parquet as pq

    output_root.mkdir(parents=True, exist_ok=True)
    old = output_root / "delta.parquet"
    new = output_root / "compact.parquet"
    pq.write_table(pa.table({"value": list(range(10))}), old)
    pq.write_table(pa.table({"value": list(range(10))}), new)
    old_manifest = _manifest(1, [old], output_root, 10)
    new_manifest = _manifest(2, [new], output_root, 10)
    active = output_root / "manifest.active.json"
    stages = ("before_compact", "after_compact_before_swap", "during_pointer_write", "after_swap_before_cleanup", "after_cleanup")
    rows: list[dict[str, Any]] = []

    def observe() -> bool:
        try:
            snapshot = json.loads(active.read_text(encoding="utf-8"))
            count = sum(pq.ParquetFile(output_root / relative).metadata.num_rows for relative in snapshot["files"])
            return count == int(snapshot["expectedRows"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return False

    for repetition in range(repetitions):
        for stage in stages:
            if not old.exists():
                pq.write_table(pa.table({"value": list(range(10))}), old)
            _atomic_json(active, old_manifest)
            if stage == "during_pointer_write":
                temporary = active.with_name(f".{active.name}.candidate-{repetition}")
                temporary.write_text('{"version":', encoding="utf-8")
                # Crash leaves invalid private candidate; active remains old.
                temporary.unlink()
            elif stage in {"after_swap_before_cleanup", "after_cleanup"}:
                _atomic_json(active, new_manifest)
                if stage == "after_cleanup":
                    old.unlink()
            rows.append({"repetition": repetition, "stage": stage, "snapshotValid": observe()})
    return {
        "status": "completed",
        "method": "atomic-pointer-compaction-boundary-failure-matrix",
        "repetitions": repetitions,
        "observations": len(rows),
        "violations": sum(not row["snapshotValid"] for row in rows),
        "byStage": {
            stage: {"observations": repetitions, "violations": sum(not row["snapshotValid"] for row in rows if row["stage"] == stage)}
            for stage in stages
        },
        "allSnapshotsValid": all(row["snapshotValid"] for row in rows),
    }


def run_local_hosted_parity(output_root: Path, *, hosted_manifest: Path | None = None) -> dict[str, Any]:
    """Run local reference validation and compare only an explicitly supplied hosted export."""

    workload = TemporalWorkload(3, 100, 0.1)
    local = run_parquet_benchmark(workload, output_root=output_root / "local")
    local_equivalence = run_runtime_equivalence(workload, output_root / "local")
    result: dict[str, Any] = {
        "status": "completed",
        "local": local,
        "localEquivalence": local_equivalence,
        "hosted": {"status": "not_run_external", "reason": "no immutable hosted manifest supplied"},
        "claimBoundary": "local correctness is complete; hosted parity is not inferred",
    }
    if hosted_manifest is not None:
        hosted = json.loads(hosted_manifest.read_text(encoding="utf-8"))
        result["hosted"] = {
            "status": "completed",
            "manifest": str(hosted_manifest),
            "expectedRows": hosted.get("expectedRows"),
            "sha256": hosted.get("sha256"),
            "rowCountMatches": hosted.get("expectedRows") == local.get("appendAllRows"),
        }
    return result


class _WorkspaceDatasetFetcher:
    """Return deterministic product pages without contacting an external site."""

    async def fetch(self, url: str, *, user_agent: str):
        from pulsecrawl.core.model import FetchResult

        identifier = url.rstrip("/").rsplit("/", 1)[-1]
        body = (
            "<html><head>"
            f"<title>Product {identifier}</title>"
            "</head><body></body></html>"
        )
        return FetchResult(
            url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=body,
            error=None,
            fetched_at=datetime.now(UTC),
            body_bytes=len(body.encode("utf-8")),
        )

    async def close(self) -> None:
        return None


def _workspace_row_count(workspace, dataset_id: str, *, version: int | None = None) -> int:
    result = workspace.datasets.query(
        dataset_id,
        "SELECT count(*) AS row_count FROM dataset",
        version=version,
    )
    return int(result["rows"][0][0])


def run_workspace_publication(
    output_root: Path,
    *,
    executions: int = 5,
    urls_per_execution: int = 20,
) -> dict[str, Any]:
    """Exercise publication, replay, query, and compaction through the public API.

    Two local jobs crawl the same deterministic URL set repeatedly.  One dataset
    retains every observation and the other publishes only first-observed URL
    identities.  The workload therefore tests the actual SQLite/Parquet
    workspace path rather than the reference publication model used by D01--D08.
    """

    if executions < 2 or urls_per_execution < 2:
        raise ValueError("workspace publication needs at least two executions and two URLs")

    from pulsecrawl import Workspace

    workspace_root = output_root / "workspace"
    workspace = Workspace.init(workspace_root, name="research-workspace-publication")
    fetcher = _WorkspaceDatasetFetcher()
    fields = [{"fieldId": "title", "name": "title", "type": "string"}]
    seeds = [f"https://products.example/item/{index:04d}" for index in range(urls_per_execution)]
    modes: dict[str, dict[str, Any]] = {}
    try:
        for mode in ("append_all", "new_urls_only"):
            dataset = workspace.datasets.create(
                f"Products {mode}",
                fields=fields,
                mode=mode,
            )
            job = workspace.jobs.create(
                f"Products {mode}",
                seeds=seeds,
                dataset_id=dataset["datasetId"],
                templates=[{
                    "template_id": f"product-title-{mode}",
                    "engine": "meta",
                    "mappings": {"title": ["<title>"]},
                }],
                scope={
                    "maxDepth": 0,
                    "maxUrlsPerExecution": urls_per_execution,
                    "maxUrlsTotal": executions * urls_per_execution,
                    "sameDomainOnly": True,
                },
                politeness={
                    "respectRobotsTxt": False,
                    "requestsPerSecond": 1_000,
                    "organizationRequestsPerSecond": 1_000,
                    "userAgent": "PulseCrawlResearch/0.1",
                },
            )
            execution_rows: list[int] = []
            execution_ids: list[str] = []
            for sequence in range(executions):
                execution_id = f"exec_{mode}_{sequence:03d}"
                execution = workspace.jobs.run(
                    job["jobId"],
                    fetcher=fetcher,
                    execution_id=execution_id,
                )
                if execution["status"] != "succeeded":
                    raise RuntimeError(f"workspace execution did not succeed: {execution_id}")
                execution_ids.append(execution_id)
                execution_rows.append(int(execution["stats"]["materializedRows"]))

            files_before = workspace.datasets.files(dataset["datasetId"])
            rows_before = _workspace_row_count(workspace, dataset["datasetId"])
            bytes_before = sum(int(item["sizeBytes"]) for item in files_before)

            replay_id = execution_ids[-1]
            files_before_replay = list(files_before)
            rows_before_replay = rows_before
            replay = workspace.jobs.run(
                job["jobId"],
                fetcher=fetcher,
                execution_id=replay_id,
            )
            files_after_replay = workspace.datasets.files(dataset["datasetId"])
            rows_after_replay = _workspace_row_count(workspace, dataset["datasetId"])
            replay_idempotent = (
                replay["status"] == "succeeded"
                and rows_after_replay == rows_before_replay
                and files_after_replay == files_before_replay
            )

            compacted_files = workspace.datasets.compact(
                dataset["datasetId"], minimum_files=2
            )
            files_after_compaction = workspace.datasets.files(dataset["datasetId"])
            rows_after_compaction = _workspace_row_count(workspace, dataset["datasetId"])
            modes[mode] = {
                "datasetId": dataset["datasetId"],
                "jobId": job["jobId"],
                "executionIds": execution_ids,
                "materializedRowsPerExecution": execution_rows,
                "rowsBeforeCompaction": rows_before,
                "bytesBeforeCompaction": bytes_before,
                "filesBeforeCompaction": len(files_before),
                "replayExecutionId": replay_id,
                "replayIdempotent": replay_idempotent,
                "compactedInputFiles": int(compacted_files),
                "filesAfterCompaction": len(files_after_compaction),
                "rowsAfterCompaction": rows_after_compaction,
                "compactionPreservedRows": rows_after_compaction == rows_before,
            }
    finally:
        workspace.close()

    append = modes["append_all"]
    new_only = modes["new_urls_only"]
    all_checks = {
        "appendAllExpectedRows": append["rowsBeforeCompaction"] == executions * urls_per_execution,
        "newOnlyExpectedRows": new_only["rowsBeforeCompaction"] == urls_per_execution,
        "newOnlyStoresFewerRows": new_only["rowsBeforeCompaction"] < append["rowsBeforeCompaction"],
        "newOnlyStoresFewerBytes": new_only["bytesBeforeCompaction"] < append["bytesBeforeCompaction"],
        "replayIsIdempotent": all(value["replayIdempotent"] for value in modes.values()),
        "compactionPreservesRows": all(value["compactionPreservedRows"] for value in modes.values()),
    }
    return {
        "status": "completed",
        "method": "public-local-workspace-end-to-end",
        "executions": executions,
        "urlsPerExecution": urls_per_execution,
        "inputObservations": executions * urls_per_execution,
        "modes": modes,
        "checks": all_checks,
        "allChecksPassed": all(all_checks.values()),
    }
