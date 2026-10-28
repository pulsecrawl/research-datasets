"""Parallel ten-minute qualification for all registered live categories."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .registry import RESEARCH_ROOT
from .runner import run
from .store import atomic_json


CATALOG_PATH = RESEARCH_ROOT / "corpora" / "live-studies" / "catalog.json"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _catalog() -> list[dict[str, Any]]:
    value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return list(value["categories"])


def _category_result(category: dict[str, Any], output_root: Path) -> dict[str, Any]:
    identifier = f"live-{category['id']}"
    path, wrapped = run(identifier, output_root=output_root, phase="qualification")
    result = dict(wrapped["results"])
    site_executions = [
        site
        for cycle in result.get("executions", [])
        for site in cycle.get("sites", [])
    ]
    failed = [site for site in site_executions if site.get("status") not in {"completed", "succeeded"}]
    quality = result.get("qualitySummary") or {}
    quality_columns = list(quality.get("columns") or [])
    quality_values = list((quality.get("rows") or [[]])[0])
    quality_row = dict(zip(quality_columns, quality_values))
    complete_sources = int(quality_row.get("source_urls_with_all_required_fields") or 0)
    enabled_sites = int(result.get("enabledSites") or 0)
    passes_runtime = (
        result.get("status") == "completed"
        and len(result.get("executions", [])) == 2
        and not failed
        and bool(result.get("workspaceValidation", {}).get("valid"))
    )
    passes_evidence = enabled_sites > 0 and complete_sources == enabled_sites
    return {
        "categoryId": category["id"],
        "displayName": category["name"],
        "schemaProfile": category["schemaProfile"],
        "runDirectory": str(path),
        "status": result.get("status"),
        "requestedSites": result.get("requestedSites", 0),
        "enabledSites": enabled_sites,
        "excludedSites": result.get("excludedSites", 0),
        "cycles": len(result.get("executions", [])),
        "siteExecutions": len(site_executions),
        "failedSiteExecutions": len(failed),
        "querySummary": result.get("querySummary"),
        "qualitySummary": result.get("qualitySummary"),
        "sourceUrlsWithAllRequiredFields": complete_sources,
        "workspaceValidation": result.get("workspaceValidation"),
        "checksumsSha256": _digest(path / "checksums.sha256"),
        "passesRuntimeGate": passes_runtime,
        "passesEvidenceGate": passes_evidence,
        "readyForRetainedStudy": passes_runtime and passes_evidence,
    }


def run_qualification(output_root: Path, *, workers: int = 9) -> dict[str, Any]:
    """Run all categories concurrently; never invokes a retained phase."""
    categories = _catalog()
    output_root.mkdir(parents=True, exist_ok=True)
    progress_path = output_root / "qualification-progress.json"
    started = datetime.now(UTC).isoformat()
    progress: dict[str, Any] = {
        "schemaVersion": 1,
        "phase": "qualification",
        "retainedStudyStarted": False,
        "startedAt": started,
        "expectedCategories": len(categories),
        "expectedSites": sum(int(category["sites"]) for category in categories),
        "completedCategories": [],
    }
    atomic_json(progress_path, progress)
    completed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(categories))) as executor:
        futures = {
            executor.submit(_category_result, category, output_root): category
            for category in categories
        }
        for future in as_completed(futures):
            category = futures[future]
            try:
                completed.append(future.result())
            except Exception as exc:  # a category failure must not erase the other evidence
                errors.append({
                    "categoryId": str(category["id"]),
                    "error": f"{type(exc).__name__}: {exc}",
                })
            progress["completedCategories"] = sorted(
                [item["categoryId"] for item in completed]
                + [item["categoryId"] for item in errors]
            )
            progress["errors"] = errors
            atomic_json(progress_path, progress)
    completed.sort(key=lambda item: item["categoryId"])
    finished = datetime.now(UTC).isoformat()
    summary = {
        **progress,
        "finishedAt": finished,
        "categories": completed,
        "errors": errors,
        "passedRuntimeGate": not errors and all(item["passesRuntimeGate"] for item in completed),
        "passedEvidenceGate": not errors and all(item["passesEvidenceGate"] for item in completed),
        "readyForRetainedStudy": not errors and all(
            item["readyForRetainedStudy"] for item in completed
        ),
        "retainedStudyStarted": False,
    }
    atomic_json(output_root / "qualification-summary.json", summary)
    atomic_json(progress_path, summary)
    return summary
