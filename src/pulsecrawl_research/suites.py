"""Named, reproducible experiment suites."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import build_report
from .runner import run


SUITES = {
    "smoke": ("S01", "S07", "S09", "T01", "T04", "T05", "T09", "D01", "D08"),
    "nightly": tuple(f"S0{i}" for i in range(1, 10))
    + tuple(f"T0{i}" for i in range(1, 10))
    + tuple(f"D0{i}" for i in range(1, 10) if i != 6),
    "release": tuple(f"S0{i}" for i in range(1, 10))
    + tuple(f"T0{i}" for i in range(1, 10))
    + tuple(f"D0{i}" for i in range(1, 9)) + ("D10",),
    "final-local-core": (
        "S01", "S02", "S03", "S04", "S07",
        "T01", "T02", "T04", "T09", "T10",
        "D01", "D02", "D03", "D04", "D05", "D08", "D11",
    ),
    "final-local-supporting": (
        "S05", "S06", "S08",
        "T03", "T05", "T06", "T07",
        "D06", "D07", "D10",
    ),
}

RELEASE_REPETITIONS = {
    "S01": 30, "S02": 1, "S03": 30, "S04": 30, "S05": 1, "S06": 1,
    "T01": 1, "T02": 1, "T03": 5, "T04": 1,
    "D01": 30, "D02": 30, "D03": 30, "D04": 30, "D05": 1,
    "S07": 1, "S08": 1,
    "S09": 30,
    "T05": 1, "T06": 1, "T07": 5, "T08": 1, "T09": 5, "T10": 1,
    "D06": 1, "D07": 1, "D08": 1, "D09": 1, "D10": 1, "D11": 1,
}

FINAL_LOCAL_REPETITIONS = {
    "S01": 30,
    "S02": 3,
    "S03": 30,
    "S04": 30,
    "S07": 1,
}


def _existing_completed(output_root: Path) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    repetitions: dict[str, int] = {}
    for summary_path in sorted(output_root.glob("*/summary.json")):
        experiment_path = summary_path.parent / "experiment.json"
        if not experiment_path.is_file():
            continue
        experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        identifier = str(experiment["id"])
        repetition = repetitions.get(identifier, 0)
        repetitions[identifier] = repetition + 1
        completed.append({
            "experimentId": identifier,
            "repetition": repetition,
            "runDirectory": summary_path.parent.name,
            "kind": summary["kind"],
        })
    return completed


def run_suite(name: str, output_root: Path, *, resume: bool = False) -> dict[str, Any]:
    if name not in SUITES:
        raise ValueError(f"unknown suite: {name}")
    output_root.mkdir(parents=True, exist_ok=True)
    completed = _existing_completed(output_root) if resume else []
    existing_counts: dict[str, int] = {}
    for item in completed:
        identifier = str(item["experimentId"])
        existing_counts[identifier] = existing_counts.get(identifier, 0) + 1
    for identifier in SUITES[name]:
        if name == "release":
            repetitions = RELEASE_REPETITIONS.get(identifier, 1)
        elif name.startswith("final-local"):
            repetitions = FINAL_LOCAL_REPETITIONS.get(identifier, 1)
        else:
            repetitions = 1
        start = min(existing_counts.get(identifier, 0), repetitions)
        for repetition in range(start, repetitions):
            path, result = run(identifier, output_root=output_root)
            completed.append(
                {"experimentId": identifier, "repetition": repetition, "runDirectory": path.name, "kind": result["kind"]}
            )
    report = build_report(output_root, output_root / "report")
    manifest = {
        "schemaVersion": 1,
        "suite": name,
        "createdAt": datetime.now(UTC).isoformat(),
        "experiments": completed,
        "report": report,
    }
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    # Keep the conventional filename for existing tooling and a suite-specific
    # copy so core and supporting runs can share one analysis root without one
    # execution erasing the other's orchestration record.
    (output_root / "suite-manifest.json").write_text(serialized, encoding="utf-8")
    (output_root / f"suite-manifest-{name}.json").write_text(serialized, encoding="utf-8")
    return manifest
