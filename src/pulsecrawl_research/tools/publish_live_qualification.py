"""Publish a completed, sanitized live qualification into this repository."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RELEASE_ID = "multi-category-qualification-v0.4.1-rc.1"
RUN_NAME = "qualification-2026-10-28"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _checksums(folder: Path) -> str:
    paths = sorted(
        path for path in folder.rglob("*")
        if path.is_file() and path.name not in {"checksums.sha256", "README.md"}
    )
    return "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(folder).as_posix()}\n"
        for path in paths
    )


def _sanitized_environment(source: Path) -> dict[str, Any]:
    environment = _json(source)
    environment.pop("executable", None)
    environment.pop("pulsecrawlImportLocation", None)
    environment["publicationNote"] = (
        "Absolute executable and package-import paths were removed before publication."
    )
    return environment


def _copy_category(category: dict[str, Any], source_run: Path) -> dict[str, Any]:
    destination = ROOT / "experiments/live" / category["categoryId"] / "runs" / RUN_NAME
    if destination.exists():
        raise FileExistsError(f"refusing to replace published evidence: {destination}")
    destination.mkdir(parents=True)

    for name in ("experiment.json", "live-metrics.json", "live-progress.json", "summary.json"):
        shutil.copy2(source_run / name, destination / name)
    _write_json(destination / "environment.json", _sanitized_environment(source_run / "environment.json"))
    shutil.copytree(source_run / "artifacts/live-study", destination / "workspace-evidence")

    readme = f"""# Two-cycle qualification: {category['displayName']}

This folder is the published output of the short qualification completed on
28 October 2026. It contains the access review, execution state, SQLite
metadata, Parquet dataset parts, dataset-version manifests, direct metrics,
and checksums. Third-party response bodies are not included.

- Selected websites: {category['requestedSites']}
- Completed cycles: {category['cycles']}
- Websites with a complete required-field record: {category['sourceUrlsWithAllRequiredFields']}
- Ready for the separately configured retained study: {str(category['readyForRetainedStudy']).lower()}

Start with `live-progress.json`, then inspect
`workspace-evidence/access-review.json`. The SQLite database and Parquet files
are retained so reviewers can reproduce the summary queries.
"""
    (destination / "README.md").write_text(readme, encoding="utf-8")
    (destination / "checksums.sha256").write_text(_checksums(destination), encoding="utf-8")
    return {
        "categoryId": category["categoryId"],
        "path": destination.relative_to(ROOT).as_posix(),
        "requestedSites": category["requestedSites"],
        "enabledSites": category["enabledSites"],
        "excludedSites": category["excludedSites"],
        "sourceUrlsWithAllRequiredFields": category["sourceUrlsWithAllRequiredFields"],
        "checksumsSha256": hashlib.sha256(
            (destination / "checksums.sha256").read_bytes()
        ).hexdigest(),
    }


def publish(source_root: Path) -> Path:
    summary = _json(source_root / "qualification-summary.json")
    if not summary.get("readyForRetainedStudy"):
        raise ValueError("qualification is not ready for publication")
    if summary.get("retainedStudyStarted") is not False:
        raise ValueError("qualification unexpectedly started the retained phase")

    published = []
    for category in summary["categories"]:
        source_run = Path(category["runDirectory"])
        if not source_run.is_absolute():
            source_run = source_root.parent.parent.parent / source_run
        if not source_run.is_dir():
            matches = list(source_root.glob(f"*live-{category['categoryId']}-*"))
            if len(matches) != 1:
                raise ValueError(f"cannot locate run for {category['categoryId']}")
            source_run = matches[0]
        published.append(_copy_category(category, source_run))

    release = ROOT / "experiments/releases" / RELEASE_ID
    if release.exists():
        raise FileExistsError(f"refusing to replace release: {release}")
    release.mkdir(parents=True)
    public_summary = dict(summary)
    by_category = {item["categoryId"]: item["path"] for item in published}
    for category in public_summary["categories"]:
        category["runDirectory"] = by_category[category["categoryId"]]
    _write_json(release / "qualification-summary.json", public_summary)

    manifest = {
        "schemaVersion": 1,
        "release": "0.4.1-rc.1",
        "status": "qualification-completed",
        "publicRepository": "https://github.com/pulsecrawl/research-datasets",
        "softwareUnderEvaluation": {"distribution": "pulsecrawl", "version": "0.1.0"},
        "phase": "qualification",
        "retainedStudyStarted": False,
        "selectedSites": summary["expectedSites"],
        "categories": published,
        "thirdPartyHtmlIncluded": False,
        "personalMetadataIncluded": False,
        "note": (
            "This release records the two-cycle readiness check. It is not the "
            "separately configured 24-hour study."
        ),
    }
    _write_json(release / "release-manifest.json", manifest)
    (release / "README.md").write_text(
        "# Multi-category qualification v0.4.1-rc.1\n\n"
        "This release indexes the nine-category, two-cycle readiness check. "
        "The 24-hour study was not started. Open `release-manifest.json` for "
        "category paths and `qualification-summary.json` for the measured gates.\n",
        encoding="utf-8",
    )
    (release / "checksums.sha256").write_text(_checksums(release), encoding="utf-8")
    return release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    print(publish(args.source_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
