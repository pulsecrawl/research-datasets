"""Neutral metrics and statistical summaries."""
from __future__ import annotations

import math
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(values: Iterable[float]) -> dict[str, float | int]:
    materialized = [float(value) for value in values]
    if not materialized:
        return {"count": 0}
    mean = statistics.fmean(materialized)
    stdev = statistics.stdev(materialized) if len(materialized) > 1 else 0.0
    margin = 1.96 * stdev / math.sqrt(len(materialized))
    return {
        "count": len(materialized),
        "min": min(materialized),
        "max": max(materialized),
        "mean": mean,
        "median": statistics.median(materialized),
        "stdev": stdev,
        "p50": percentile(materialized, 0.50),
        "p95": percentile(materialized, 0.95),
        "p99": percentile(materialized, 0.99),
        "confidence95Low": mean - margin,
        "confidence95High": mean + margin,
    }


def request_metrics(observations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(observations)
    urls = [str(row["path"]) for row in rows if row.get("kind") == "request"]
    statuses = [
        str(int(row["status"]))
        for row in rows
        if row.get("kind") == "request" and row.get("status") is not None
    ]
    timestamps = sorted(
        int(row["receivedAtNs"])
        for row in rows
        if row.get("kind") == "request" and row.get("receivedAtNs") is not None
    )
    gaps = [(right - left) / 1_000_000_000 for left, right in zip(timestamps, timestamps[1:])]
    return {
        "httpRequestsObserved": len(urls),
        "distinctRequestPaths": len(set(urls)),
        "duplicateRequestsObserved": len(urls) - len(set(urls)),
        "requestPathCounts": dict(sorted(Counter(urls).items())),
        "responseStatusCounts": dict(sorted(Counter(statuses).items())),
        "minimumInterRequestSeconds": min(gaps) if gaps else None,
        "interRequestSeconds": summarize(gaps),
    }


def invariant_violations(
    metrics: Mapping[str, Any], expected: Mapping[str, Any]
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    maximum = expected.get("maximumHttpRequests")
    if maximum is not None and int(metrics.get("httpRequestsObserved", 0)) > int(maximum):
        violations.append(
            {
                "invariant": "http_requests_within_budget",
                "expectedMaximum": int(maximum),
                "observed": int(metrics["httpRequestsObserved"]),
            }
        )
    minimum_interval = expected.get("minimumInterRequestSeconds")
    observed_interval = metrics.get("minimumInterRequestSeconds")
    if (
        minimum_interval is not None
        and observed_interval is not None
        and float(observed_interval) + 1e-9 < float(minimum_interval)
    ):
        violations.append(
            {
                "invariant": "minimum_request_interval",
                "expectedMinimum": float(minimum_interval),
                "observed": float(observed_interval),
            }
        )
    forbidden = [str(path) for path in expected.get("forbiddenRequestPaths", ())]
    path_counts = metrics.get("requestPathCounts") or {}
    for path in forbidden:
        if int(path_counts.get(path, 0)) > 0:
            violations.append(
                {
                    "invariant": "forbidden_path_not_requested",
                    "path": path,
                    "observed": int(path_counts[path]),
                }
            )
    for path in (str(value) for value in expected.get("requiredRequestPaths", ())):
        if int(path_counts.get(path, 0)) == 0:
            violations.append(
                {
                    "invariant": "required_path_requested",
                    "path": path,
                    "observed": 0,
                }
            )
    status_counts = metrics.get("responseStatusCounts") or {}
    for status in (str(int(value)) for value in expected.get("requiredStatusCodes", ())):
        if int(status_counts.get(status, 0)) == 0:
            violations.append(
                {
                    "invariant": "required_status_observed",
                    "status": int(status),
                    "observed": 0,
                }
            )
    return violations
