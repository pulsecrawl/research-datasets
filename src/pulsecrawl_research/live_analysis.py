"""Aggregate bounded live-study runs into readable evidence tables."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .store import atomic_json


def _read_live_result(run_dir: Path) -> dict[str, Any] | None:
    for name in ("live-metrics.json", "live-progress.json"):
        path = run_dir / name
        if path.is_file():
            result = json.loads(path.read_text(encoding="utf-8"))
            interruption = run_dir / "interruption.json"
            if interruption.is_file():
                stopped = json.loads(interruption.read_text(encoding="utf-8"))
                result["status"] = stopped.get("status", "incomplete")
                result["interruption"] = stopped
            return result
    return None


def summarize_live_runs(run_root: Path, output: Path) -> dict[str, Any]:
    """Summarize live runs without combining engineering and retained phases."""
    output.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    site_rows: list[dict[str, Any]] = []
    for run_dir in sorted(path for path in run_root.iterdir() if path.is_dir()):
        result = _read_live_result(run_dir)
        if result is None:
            continue
        totals: defaultdict[str, int] = defaultdict(int)
        by_site: dict[str, defaultdict[str, int]] = {}
        for cycle in result.get("executions", []):
            for site in cycle.get("sites", []):
                site_id = str(site.get("siteId"))
                current = by_site.setdefault(site_id, defaultdict(int))
                current["executions"] += 1
                current[f"status_{site.get('status', 'unknown')}"] += 1
                for key, value in (site.get("stats") or {}).items():
                    if isinstance(value, int) and not isinstance(value, bool):
                        current[key] += value
                        totals[key] += value
        for site_id, values in sorted(by_site.items()):
            site_rows.append({
                "runId": run_dir.name,
                "study": result.get("study"),
                "phase": result.get("phase"),
                "siteId": site_id,
                **dict(values),
            })
        query_rows = ((result.get("querySummary") or {}).get("rows") or [[None, None, None]])[0]
        runs.append({
            "runId": run_dir.name,
            "study": result.get("study"),
            "phase": result.get("phase"),
            "status": result.get("status"),
            "requestedSites": result.get("requestedSites", 0),
            "enabledSites": result.get("enabledSites", 0),
            "excludedSites": result.get("excludedSites", 0),
            "completedCycles": len(result.get("executions", [])),
            "plannedCycles": (result.get("settings") or {}).get("executions", 0),
            "rows": query_rows[0] if len(query_rows) > 0 else None,
            "publishedExecutions": query_rows[1] if len(query_rows) > 1 else None,
            "sourceUrls": query_rows[2] if len(query_rows) > 2 else None,
            **dict(totals),
        })
    summary = {
        "schemaVersion": 1,
        "method": "live-study-summary-with-phases-kept-separate",
        "runs": runs,
        "sites": site_rows,
    }
    atomic_json(output / "live-summary.json", summary)
    for name, rows in (("live-runs.csv", runs), ("live-sites.csv", site_rows)):
        columns = sorted({key for row in rows for key in row})
        with (output / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    return summary


def prepare_review_sample(run_dir: Path, output_csv: Path, *, sample_size: int = 30) -> int:
    """Create a deterministic, site-balanced worksheet for manual page checks."""
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    result = _read_live_result(run_dir)
    if result is None or not result.get("datasetId"):
        raise ValueError("run directory has no completed live dataset")
    from pulsecrawl import Workspace

    workspace = Workspace(run_dir / "artifacts" / "live-study" / "workspace")
    try:
        query = workspace.datasets.query(
            str(result["datasetId"]),
            "SELECT * FROM dataset ORDER BY _source_url, _crawled_at",
            row_cap=100_000,
        )
    finally:
        workspace.close()
    columns = list(query.get("columns") or [])
    records = [dict(zip(columns, row, strict=True)) for row in query.get("rows") or []]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        group = str(record.get("source_name") or record.get("brand") or "")
        if not group:
            group = (urlsplit(str(record.get("_source_url") or "")).hostname or "unknown")
        groups[group].append(record)
    selected: list[dict[str, Any]] = []
    offset = 0
    while len(selected) < sample_size:
        added = False
        for group in sorted(groups):
            if offset < len(groups[group]):
                selected.append(groups[group][offset])
                added = True
                if len(selected) == sample_size:
                    break
        if not added:
            break
        offset += 1
    review_columns = columns + ["review_result", "reviewed_at", "review_notes"]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=review_columns)
        writer.writeheader()
        for record in selected:
            writer.writerow({**record, "review_result": "", "reviewed_at": "", "review_notes": ""})
    return len(selected)
