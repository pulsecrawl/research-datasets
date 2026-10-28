"""Build the repetitive reviewer guides from checked-in manifests."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def build_live_guides() -> int:
    catalog = json.loads((ROOT / "experiments/live/catalog.json").read_text())
    written = 0
    for category in catalog["categories"]:
        folder = ROOT / "experiments/live" / category["id"]
        sites = json.loads((folder / "input/sites.json").read_text())["sites"]
        eligible = [site for site in sites if site.get("retainedEnabled") is not False]
        rows = []
        for site in sites:
            status = "eligible for qualification"
            if site.get("retainedEnabled") is False:
                status = "excluded after pilot"
            rows.append(
                f"| {site['name']} | `{site['id']}` | {status} | "
                f"{site['qualificationSeedUrls'][0]} |"
            )
        body = f"""# {category['name']} live study

This category contains {len(sites)} reviewed candidates. {len(eligible)} are
currently eligible for the two-cycle qualification. A later 24-hour study is
configured separately and is not started by the qualification command.

| Website | Stable ID | Current status | Qualification URL |
|---|---|---|---|
{chr(10).join(rows)}

Exact hosts, discovery limits, template mappings, and exclusion reasons are in
[`input/sites.json`](input/sites.json). Completed evidence appears under
`runs/`; an empty `runs/` folder means that no public run has been released.
"""
        (folder / "README.md").write_text(body, encoding="utf-8")
        written += 1
    return written


def build_controlled_guides() -> int:
    written = 0
    for folder in sorted((ROOT / "experiments/controlled").iterdir()):
        if not folder.is_dir():
            continue
        runs = sorted((folder / "runs").glob("run-*"))
        if not runs:
            continue
        resolved = json.loads((runs[0] / "resolved-experiment.json").read_text())
        manifests = [
            json.loads((run / "execution-manifest.json").read_text()) for run in runs
        ]
        body = f"""# {resolved.get('title', folder.name)}

**Experiment ID:** `{folder.name}`  
**Retained runs:** {len(runs)}

{resolved.get('description', 'Controlled experiment with fixed registered inputs.')}

The registered acceptance rule is recorded in each run's
`resolved-experiment.json`. Direct measurements are in `measurements.json`;
`summary.json` contains the run-level result used by the reviewed analysis.

| Public folder | Original execution ID | Status |
|---|---|---|
{chr(10).join(f"| [`{run.name}`](runs/{run.name}/) | `{manifest['executionId']}` | {manifest['status']} |" for run, manifest in zip(runs, manifests))}
"""
        (folder / "README.md").write_text(body, encoding="utf-8")
        written += 1
    return written


def main() -> int:
    print(json.dumps({
        "liveGuides": build_live_guides(),
        "controlledGuides": build_controlled_guides(),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
