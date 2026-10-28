"""Experiment registry and JSON-compatible YAML loaders."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RESEARCH_ROOT = Path(__file__).resolve().parents[2]


def load_document(path: Path) -> dict[str, Any]:
    """Load a JSON document stored as `.json`, `.yaml`, or `.yml`.

    Registry/config files intentionally use the JSON subset of YAML so the
    research smoke path has no non-standard parser dependency.
    """

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} must use the JSON-compatible YAML subset") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain an object")
    return raw


def registry() -> dict[str, Any]:
    return load_document(RESEARCH_ROOT / "registry.yaml")


def experiment_paths() -> list[Path]:
    return sorted((RESEARCH_ROOT / "experiments").glob("*/*/experiment.yaml"))


def experiments() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in experiment_paths():
        raw = load_document(path)
        experiment_id = str(raw.get("id") or "")
        if not experiment_id:
            raise ValueError(f"{path} does not define id")
        if experiment_id in found:
            raise ValueError(f"duplicate experiment id: {experiment_id}")
        raw["_path"] = str(path)
        found[experiment_id] = raw
    return found


def resolve_experiment(identifier: str) -> dict[str, Any]:
    all_experiments = experiments()
    if identifier in all_experiments:
        return all_experiments[identifier]
    for experiment in all_experiments.values():
        if identifier in experiment.get("aliases", []):
            return experiment
    raise KeyError(f"unknown experiment or alias: {identifier}")
