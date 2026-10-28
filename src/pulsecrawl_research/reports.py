"""Aggregate immutable runs into reviewable CSV/Markdown artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .registry import RESEARCH_ROOT


def _flatten(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), item, output)
    elif isinstance(value, (str, int, float, bool)) or value is None:
        output[prefix] = value


def build_report(run_root: Path | None = None, output: Path | None = None) -> dict[str, Any]:
    run_root = run_root or RESEARCH_ROOT / "results/runs"
    output = output or RESEARCH_ROOT / "results/published/latest"
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    summary_paths = sorted(run_root.glob("*/summary.json"))
    for summary_path in summary_paths:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        results = summary.get("results")
        values = results if isinstance(results, list) else [summary]
        for index, value in enumerate(values):
            row: dict[str, Any] = {
                "runId": summary_path.parent.name,
                "resultIndex": index,
                "kind": summary.get("kind"),
            }
            _flatten("result" if isinstance(results, list) else "", value, row)
            rows.append(row)
    fields = sorted({field for row in rows for field in row})
    csv_path = output / "summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "runs": len(summary_paths),
        "runDirectories": len(summary_paths),
        "normalizedRows": len(rows),
        "summary": csv_path.name,
        "fields": fields,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown = [
        "# Research run summary", "",
        f"Immutable run directories: {len(summary_paths)}", "",
        f"Normalized result rows: {len(rows)}", "",
    ]
    if rows:
        preferred = [
            field
            for field in ("runId", "kind", "result.system", "result.profile", "result.status")
            if field in fields
        ]
        markdown.extend(
            [
                "| " + " | ".join(preferred) + " |",
                "| " + " | ".join("---" for _ in preferred) + " |",
                *[
                    "| " + " | ".join(str(row.get(field, "")) for field in preferred) + " |"
                    for row in rows
                ],
                "",
            ]
        )
    (output / "summary.md").write_text("\n".join(markdown), encoding="utf-8")
    manifest["markdown"] = "summary.md"
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
