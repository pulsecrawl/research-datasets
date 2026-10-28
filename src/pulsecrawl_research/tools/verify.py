"""Verify public inputs, controlled evidence, live runs, links, and privacy."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import struct
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CONTROLLED_RELEASE = ROOT / "experiments/releases/controlled-evidence-v0.3.2"
QUALIFICATION_RELEASE = ROOT / "experiments/releases/multi-category-qualification-v0.4.0-rc.1"
EXPECTED_DATASETS = {"fixed-html": 60, "site-pattern-html": 100, "commerce-html": 20}
EXPECTED_FAMILIES = {"policy-and-recovery", "template-extraction", "versioned-datasets"}
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path.relative_to(ROOT)}")
    return value


def verify_manifests() -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, expected in EXPECTED_DATASETS.items():
        folder = ROOT / "datasets" / name
        entries = [json.loads(line) for line in (folder / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        if len(entries) != expected or len({row["id"] for row in entries}) != expected:
            raise ValueError(f"invalid manifest count or IDs: {name}")
        listed: set[Path] = set()
        for row in entries:
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe manifest path: {name}/{relative}")
            target = folder / relative
            if hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError(f"HTML checksum mismatch: {name}/{relative}")
            listed.add(target)
        if listed != set(folder.rglob("*.html")):
            raise ValueError(f"unlisted HTML: {name}")
        counts[name] = len(entries)
    return counts


def verify_research_metadata() -> dict[str, object]:
    compatibility = _json(ROOT / "docs/environment/compatibility.json")
    catalog = _json(ROOT / "experiments/catalog.json")
    experiments = catalog["experiments"]
    identifiers = [entry["id"] for entry in experiments]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("controlled experiment identifiers must be unique")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]+", value) for value in identifiers):
        raise ValueError("controlled experiment identifiers must be readable slugs")
    families = {entry["family"] for entry in experiments}
    if families != EXPECTED_FAMILIES:
        raise ValueError(f"unexpected experiment families: {sorted(families)}")
    version = compatibility["pulsecrawl"]
    requirement = f"pulsecrawl[workspace]=={version}"
    requirements = (ROOT / "docs/environment/requirements.txt").read_text().splitlines()
    if requirement not in requirements or catalog["package"] != requirement:
        raise ValueError("PulseCrawl package pins are inconsistent")
    installed = importlib.metadata.version("pulsecrawl")
    if installed != version:
        raise ValueError(f"installed pulsecrawl {installed} does not match {version}")
    live = _json(ROOT / "experiments/live/catalog.json")
    if len(live["categories"]) != 9 or sum(row["sites"] for row in live["categories"]) != 119:
        raise ValueError("live catalog does not contain the registered 119 candidates")
    for category in live["categories"]:
        folder = ROOT / "experiments/live" / category["id"]
        sites = _json(folder / "input/sites.json")["sites"]
        if len(sites) != category["sites"]:
            raise ValueError(f"live site count differs: {category['id']}")
        if not (folder / "README.md").is_file() or not (folder / "experiment.yaml").is_file():
            raise ValueError(f"live category lacks a reader guide: {category['id']}")
        for site in sites:
            if site.get("retainedEnabled") is False and not site.get("retainedExclusion"):
                raise ValueError(f"excluded live source lacks a reason: {site['id']}")
    return {
        "controlledExperiments": len(experiments),
        "families": sorted(families),
        "liveCategories": len(live["categories"]),
        "liveCandidates": sum(row["sites"] for row in live["categories"]),
        "pulsecrawl": installed,
    }


def verify_directory_checksums(folder: Path) -> str:
    checksum_path = folder / "checksums.sha256"
    if not checksum_path.is_file():
        raise ValueError(f"missing checksum manifest: {folder.relative_to(ROOT)}")
    listed: set[Path] = set()
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(f"invalid checksum in {checksum_path.relative_to(ROOT)}")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"unsafe checksum path in {checksum_path.relative_to(ROOT)}")
        target = folder / relative_path
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"evidence checksum mismatch: {target.relative_to(ROOT)}")
        listed.add(target)
    actual = {path for path in folder.rglob("*") if path.is_file() and path.name not in {"checksums.sha256", "README.md"}}
    if listed != actual:
        raise ValueError(f"checksum coverage mismatch: {folder.relative_to(ROOT)}")
    return hashlib.sha256(checksum_path.read_bytes()).hexdigest()


def verify_controlled_evidence() -> dict[str, object]:
    reviewed = _json(CONTROLLED_RELEASE / "reviewed-release.json")
    reviewed_rows = {row["executionId"]: row for row in reviewed["controlledExecutions"]}
    found: dict[str, str] = {}
    experiment_counts: dict[str, int] = {}
    for experiment in sorted((ROOT / "experiments/controlled").iterdir()):
        if not experiment.is_dir():
            continue
        runs = sorted((experiment / "runs").glob("run-*"))
        if not runs:
            continue
        if not (experiment / "README.md").is_file():
            raise ValueError(f"controlled experiment lacks README: {experiment.name}")
        for run in runs:
            manifest = _json(run / "execution-manifest.json")
            execution_id = manifest["executionId"]
            if execution_id in found:
                raise ValueError(f"duplicate controlled execution: {execution_id}")
            if manifest["experimentId"] != experiment.name or manifest["status"] != "completed":
                raise ValueError(f"invalid controlled execution: {run.relative_to(ROOT)}")
            found[execution_id] = verify_directory_checksums(run)
        experiment_counts[experiment.name] = len(runs)
    if set(found) != set(reviewed_rows):
        raise ValueError("controlled execution set differs from the reviewed release")
    for execution_id, digest in found.items():
        if reviewed_rows[execution_id]["publicChecksumsSha256"] != digest:
            raise ValueError(f"controlled checksum differs: {execution_id}")
    analysis = CONTROLLED_RELEASE / "analysis"
    if verify_directory_checksums(analysis) != reviewed["analysis"]["checksumsSha256"]:
        raise ValueError("controlled analysis checksum differs")
    completed_live = ROOT / "experiments/live/completed-news-and-commerce"
    live_studies = []
    for row in reviewed["liveStudies"]:
        folder = completed_live / row["study"]
        if verify_directory_checksums(folder) != row["checksumsSha256"]:
            raise ValueError(f"earlier live-study checksum differs: {row['study']}")
        live_studies.append(row["study"])
    return {
        "controlledExecutions": len(found),
        "controlledExperimentsWithEvidence": len(experiment_counts),
        "earlierLiveStudies": live_studies,
    }


def verify_qualification_release() -> dict[str, object]:
    manifest = _json(QUALIFICATION_RELEASE / "release-manifest.json")
    summary = _json(QUALIFICATION_RELEASE / "qualification-summary.json")
    if manifest["release"] != "0.4.0-rc.1" or manifest["retainedStudyStarted"] is not False:
        raise ValueError("qualification release identity or phase boundary differs")
    if not summary.get("readyForRetainedStudy") or summary.get("retainedStudyStarted") is not False:
        raise ValueError("published qualification did not pass both readiness gates")
    if len(manifest["categories"]) != 9 or len(summary["categories"]) != 9:
        raise ValueError("qualification release must include all nine categories")
    for row in manifest["categories"]:
        folder = ROOT / row["path"]
        if not folder.resolve().is_relative_to(ROOT) or not folder.is_dir():
            raise ValueError(f"unsafe qualification path: {row['path']}")
        if verify_directory_checksums(folder) != row["checksumsSha256"]:
            raise ValueError(f"qualification checksum differs: {row['categoryId']}")
        if not list(folder.glob("workspace-evidence/workspace/state/*.sqlite")):
            raise ValueError(f"qualification lacks SQLite evidence: {row['categoryId']}")
        if not list(folder.glob("workspace-evidence/workspace/datasets/**/*.parquet")):
            raise ValueError(f"qualification lacks Parquet evidence: {row['categoryId']}")
        access = _json(folder / "workspace-evidence/access-review.json")
        if access.get("retainsHtml") is not False:
            raise ValueError(f"qualification publication boundary differs: {row['categoryId']}")
    verify_directory_checksums(QUALIFICATION_RELEASE)
    return {
        "release": manifest["release"],
        "categories": len(manifest["categories"]),
        "candidateSites": manifest["candidateSites"],
        "enabledSites": sum(row["enabledSites"] for row in manifest["categories"]),
        "retainedStudyStarted": False,
    }


def verify_documentation() -> dict[str, int]:
    required = {
        "README.md", "docs/README.md", "datasets/README.md", "experiments/README.md",
        "experiments/controlled/INDEX.md", "experiments/live/README.md",
        "experiments/releases/README.md", "runners/README.md",
        "src/pulsecrawl_research/README.md",
    }
    for relative in required:
        if not (ROOT / relative).is_file():
            raise ValueError(f"missing reader guide: {relative}")
    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    checked = 0
    for path in ROOT.rglob("*.md"):
        if any(part in {".git", ".venv"} for part in path.relative_to(ROOT).parts):
            continue
        for raw in pattern.findall(path.read_text(encoding="utf-8")):
            target = raw.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            destination = (path.parent / target).resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                raise ValueError(f"broken local link in {path.relative_to(ROOT)}: {target}")
            checked += 1
    images = sorted((ROOT / "docs/images").glob("*.png"))
    for path in images:
        body = path.read_bytes()
        length = struct.unpack(">I", body[8:12])[0]
        width, height = struct.unpack(">II", body[16:24])
        if body[:8] != b"\x89PNG\r\n\x1a\n" or body[12:16] != b"IHDR" or length != 13 or (width, height) != (1000, 400):
            raise ValueError(f"invalid documentation image: {path.name}")
    return {"readerGuides": len(required), "localLinks": checked, "syntheticImages": len(images)}


def publication_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and not any(part in {".git", ".venv", "__pycache__"} for part in path.relative_to(ROOT).parts))


def privacy_scan(deny: list[str] | None = None) -> None:
    rules = {
        "absolute home path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+|[A-Za-z]:\\Users\\", re.I),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "credential": re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    }
    for index, value in enumerate(deny or []):
        rules[f"reviewer deny rule {index + 1}"] = re.compile(value, re.I)
    allowed = {"341176098+pulsecrawl@users.noreply.github.com"}
    for path in publication_files():
        relative = path.relative_to(ROOT).as_posix()
        try:
            body = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in rules.items():
            for match in pattern.finditer(relative + "\n" + body):
                if label == "email" and match.group(0) in allowed:
                    continue
                raise ValueError(f"publication scan failed ({label}) in {relative}")


def main() -> int:
    result = {
        "datasets": verify_manifests(),
        "metadata": verify_research_metadata(),
        "controlledEvidence": verify_controlled_evidence(),
        "qualificationRelease": verify_qualification_release(),
        "documentation": verify_documentation(),
    }
    privacy_scan()
    result["publicationScan"] = "passed"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
