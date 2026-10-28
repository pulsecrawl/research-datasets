"""Create a sanitized, checksum-linked manifest for a reviewed execution."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
PRIVATE_PATTERN = re.compile(
    r"/(?:Users|home)/[A-Za-z0-9_.-]+|[A-Za-z]:\\Users\\|"
    r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b",
    re.I,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog_entry(identifier: str) -> dict[str, object]:
    catalog = json.loads((ROOT / "experiments" / "catalog.json").read_text(encoding="utf-8"))
    for entry in catalog["experiments"]:
        if entry["id"] == identifier:
            return entry
    raise ValueError(f"unknown experiment identifier: {identifier}")


def ensure_publishable_text(values: list[str]) -> None:
    for value in values:
        if PRIVATE_PATTERN.search(value):
            raise ValueError("command contains a private path or credential-shaped value")


def create_manifest(
    *,
    experiment_id: str,
    execution_id: str,
    output_dir: Path,
    measurements: Path,
    summary: Path,
    command: list[str],
    status: str,
    started_at: str,
    completed_at: str,
) -> Path:
    entry = catalog_entry(experiment_id)
    ensure_publishable_text(command)
    if not measurements.is_file() or not summary.is_file():
        raise FileNotFoundError("measurements and summary must exist before evidence is recorded")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"evidence directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    resolved = output_dir / "resolved-experiment.json"
    destination_measurements = output_dir / measurements.name
    destination_summary = output_dir / summary.name
    resolved.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copyfile(measurements, destination_measurements)
    shutil.copyfile(summary, destination_summary)

    compatibility = json.loads(
        (ROOT / "docs/environment/compatibility.json").read_text(encoding="utf-8")
    )
    release_checksums = (
        ROOT
        / "experiments/releases/controlled-evidence-v0.3.3/checksums-v0.3.3.sha256"
    )
    manifest = {
        "schemaVersion": 1,
        "executionId": execution_id,
        "experimentId": experiment_id,
        "status": status,
        "startedAt": started_at,
        "completedAt": completed_at,
        "software": {
            "pulsecrawl": importlib.metadata.version("pulsecrawl"),
            "python": platform.python_version(),
            "platform": f"{platform.system()}-{platform.machine()}",
        },
        "inputs": {
            "artifactRelease": compatibility["artifactRelease"],
            "checksumsSha256": sha256(release_checksums),
        },
        "command": command,
        "configuration": entry["workload"],
        "outputs": {
            "measurements": destination_measurements.name,
            "summary": destination_summary.name,
            "checksums": "checksums.sha256",
        },
        "notes": [],
    }
    if manifest["software"]["pulsecrawl"] != compatibility["pulsecrawl"]:
        raise ValueError("installed PulseCrawl version does not match the registered version")

    manifest_path = output_dir / "execution-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifacts = [manifest_path, resolved, destination_measurements, destination_summary]
    lines = [f"{sha256(path)}  {path.name}\n" for path in sorted(artifacts)]
    (output_dir / "checksums.sha256").write_text("".join(lines), encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument(
        "--status",
        choices=["completed", "completed-with-observations", "failed", "stopped"],
        default="completed",
    )
    parser.add_argument("--started-at")
    parser.add_argument("--completed-at")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("record the executed command after --")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    create_manifest(
        experiment_id=args.experiment,
        execution_id=args.execution_id,
        output_dir=args.output,
        measurements=args.measurements,
        summary=args.summary,
        command=args.command,
        status=args.status,
        started_at=args.started_at or now,
        completed_at=args.completed_at or now,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
