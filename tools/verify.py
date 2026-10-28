"""Verify release inputs, checksums, and publication boundaries."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"fixed-html": 60, "site-pattern-html": 100, "commerce-html": 20}
EXPECTED_FAMILIES = {"policy-and-recovery", "template-extraction", "versioned-datasets"}
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}")


def release_files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and ".git" not in p.relative_to(ROOT).parts
                  and "__pycache__" not in p.parts
                  and ".venv" not in p.parts
                  and "storage-output" not in p.relative_to(ROOT).parts
                  and p.name != "checksums.sha256")


def verify_manifests() -> dict[str, int]:
    counts = {}
    for name, expected in EXPECTED.items():
        folder = ROOT / "datasets" / name
        entries = [json.loads(line) for line in (folder / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        if len(entries) != expected or len({r["id"] for r in entries}) != expected:
            raise ValueError(f"invalid manifest count or IDs: {name}")
        listed = set()
        for row in entries:
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("manifest paths must stay inside the collection")
            target = folder / relative
            if hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError(f"HTML checksum mismatch: {name}/{relative}")
            listed.add(target)
        if listed != set(folder.rglob("*.html")):
            raise ValueError(f"unlisted HTML: {name}")
        counts[name] = len(entries)
    return counts


def verify_research_metadata() -> dict[str, object]:
    compatibility = json.loads((ROOT / "environment" / "compatibility.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "experiments" / "catalog.json").read_text(encoding="utf-8"))

    experiments = catalog["experiments"]
    identifiers = [entry["id"] for entry in experiments]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("experiment identifiers must be unique")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]+", identifier) for identifier in identifiers):
        raise ValueError("experiment identifiers must be descriptive lowercase slugs")
    families = {entry["family"] for entry in experiments}
    if families != EXPECTED_FAMILIES:
        raise ValueError(f"unexpected experiment families: {sorted(families)}")
    required = {"id", "family", "title", "seed", "status", "workload", "measurements", "acceptance"}
    for entry in experiments:
        missing = required - entry.keys()
        if missing:
            raise ValueError(f"experiment {entry.get('id', '<unknown>')} is missing {sorted(missing)}")
        if not entry["measurements"] or not entry["acceptance"].strip():
            raise ValueError(f"experiment {entry['id']} lacks an evidence rule")

    package_version = compatibility["pulsecrawl"]
    expected_requirement = f"pulsecrawl[workspace]=={package_version}"
    requirements = (ROOT / "environment" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    if expected_requirement not in requirements:
        raise ValueError("public package pin does not match compatibility.json")
    if catalog["package"] != expected_requirement:
        raise ValueError("experiment catalog package pin does not match compatibility.json")
    if release["softwareUnderEvaluation"]["version"] != package_version:
        raise ValueError("release manifest package version does not match compatibility.json")
    if release["release"] != compatibility["artifactRelease"]:
        raise ValueError("release and compatibility artifact versions differ")

    installed_version = importlib.metadata.version("pulsecrawl")
    if installed_version != package_version:
        raise ValueError(
            f"installed pulsecrawl {installed_version} does not match registered {package_version}"
        )

    return {
        "experiments": len(experiments),
        "families": sorted(families),
        "pulsecrawl": installed_version,
    }


def verify_directory_checksums(directory: Path) -> str:
    checksum_path = directory / "checksums.sha256"
    if not checksum_path.is_file():
        raise ValueError(f"missing checksum manifest: {directory.relative_to(ROOT)}")
    listed: set[Path] = set()
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(f"invalid checksum in {checksum_path.relative_to(ROOT)}")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"unsafe checksum path in {checksum_path.relative_to(ROOT)}")
        target = directory / relative_path
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"evidence checksum mismatch: {target.relative_to(ROOT)}")
        listed.add(target)
    actual = {path for path in directory.iterdir() if path.is_file() and path != checksum_path}
    if listed != actual:
        raise ValueError(f"checksum coverage mismatch: {directory.relative_to(ROOT)}")
    return hashlib.sha256(checksum_path.read_bytes()).hexdigest()


def verify_reviewed_evidence() -> dict[str, object]:
    release = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    reviewed = json.loads((ROOT / "evidence" / "reviewed-release.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "experiments" / "catalog.json").read_text(encoding="utf-8"))
    experiment_ids = {entry["id"] for entry in catalog["experiments"]}
    execution_root = ROOT / "evidence" / "executions"
    execution_dirs = sorted(path for path in execution_root.iterdir() if path.is_dir())
    expected_files = {
        "execution-manifest.json",
        "resolved-experiment.json",
        "measurements.json",
        "summary.json",
        "checksums.sha256",
    }
    execution_ids: list[str] = []
    execution_checksums: dict[str, str] = {}
    for directory in execution_dirs:
        if {path.name for path in directory.iterdir() if path.is_file()} != expected_files:
            raise ValueError(f"unexpected evidence layout: {directory.relative_to(ROOT)}")
        manifest = json.loads((directory / "execution-manifest.json").read_text(encoding="utf-8"))
        if manifest["executionId"] != directory.name:
            raise ValueError(f"execution ID does not match directory: {directory.name}")
        if manifest["experimentId"] not in experiment_ids:
            raise ValueError(f"unknown experiment in execution {directory.name}")
        if manifest["status"] != "completed":
            raise ValueError(f"reviewed execution is not complete: {directory.name}")
        inputs = manifest["inputs"]
        if inputs["artifactRelease"] != release["release"]:
            raise ValueError(f"artifact release mismatch: {directory.name}")
        if not SHA256_PATTERN.fullmatch(inputs["checksumsSha256"]):
            raise ValueError(f"invalid input-release checksum: {directory.name}")
        if not re.fullmatch(r"[a-f0-9]{40}", inputs["sourceRepositoryCommit"]):
            raise ValueError(f"invalid source commit: {directory.name}")
        if not SHA256_PATTERN.fullmatch(inputs["sourceRunChecksumsSha256"]):
            raise ValueError(f"invalid source-run checksum: {directory.name}")
        resolved = json.loads((directory / "resolved-experiment.json").read_text(encoding="utf-8"))
        if resolved["id"] != manifest["experimentId"]:
            raise ValueError(f"resolved experiment mismatch: {directory.name}")
        execution_ids.append(directory.name)
        execution_checksums[directory.name] = verify_directory_checksums(directory)

    if len(execution_ids) != len(set(execution_ids)):
        raise ValueError("reviewed execution IDs are not unique")
    if len(execution_ids) != release["evidence"]["reviewedExecutions"]:
        raise ValueError("release manifest reviewed-execution count differs")
    if reviewed["controlledExecutionCount"] != len(execution_ids):
        raise ValueError("reviewed release execution count differs")
    reviewed_rows = {row["executionId"]: row for row in reviewed["controlledExecutions"]}
    if set(reviewed_rows) != set(execution_ids):
        raise ValueError("reviewed release execution list differs")
    for execution_id, digest in execution_checksums.items():
        if reviewed_rows[execution_id]["publicChecksumsSha256"] != digest:
            raise ValueError(f"reviewed-release checksum differs: {execution_id}")

    analysis_dir = ROOT / "analysis" / "releases" / reviewed["analysis"]["analysisId"]
    analysis_manifest = json.loads((analysis_dir / "analysis-manifest.json").read_text(encoding="utf-8"))
    if set(analysis_manifest["includedExecutions"]) != set(execution_ids):
        raise ValueError("analysis execution set differs from reviewed executions")
    if analysis_manifest["excludedExecutions"]:
        raise ValueError("frozen confirmatory analysis unexpectedly excludes executions")
    analysis_checksum = verify_directory_checksums(analysis_dir)
    if analysis_checksum != reviewed["analysis"]["checksumsSha256"]:
        raise ValueError("analysis checksum differs from reviewed release")

    live_studies: list[str] = []
    for row in reviewed["liveStudies"]:
        study = row["study"]
        directory = ROOT / "evidence" / "live-studies" / study
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest["study"] != study or manifest["status"] != "completed-supporting-observation":
            raise ValueError(f"invalid live-study manifest: {study}")
        if hashlib.sha256((directory / "summary.json").read_bytes()).hexdigest() != manifest["publishedSummarySha256"]:
            raise ValueError(f"live-study summary checksum differs: {study}")
        if verify_directory_checksums(directory) != row["checksumsSha256"]:
            raise ValueError(f"live-study checksum differs: {study}")
        live_studies.append(study)

    if release["analysis"]["reviewedAnalyses"] != 1:
        raise ValueError("release manifest reviewed-analysis count differs")
    if release["liveCaseStudy"]["aggregateSummariesIncluded"] != len(live_studies):
        raise ValueError("release manifest live-summary count differs")
    return {
        "controlledExecutions": len(execution_ids),
        "controlledAnalysis": reviewed["analysis"]["analysisId"],
        "liveStudies": live_studies,
    }


def privacy_scan(deny: list[str] | None = None) -> None:
    rules = {
        "absolute home path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+|[A-Za-z]:\\Users\\", re.I),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "credential": re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    }
    for index, pattern in enumerate(deny or []):
        rules[f"reviewer deny rule {index + 1}"] = re.compile(pattern, re.I)
    allowed_emails = {"341176098+pulsecrawl@users.noreply.github.com"}
    for path in release_files():
        relative = path.relative_to(ROOT).as_posix()
        body = path.read_text(encoding="utf-8")
        for label, pattern in rules.items():
            for match in pattern.finditer(relative + "\n" + body):
                if label == "email" and match.group(0) in allowed_emails:
                    continue
                raise ValueError(f"publication scan failed ({label}) in {relative}")


def checksum_lines() -> str:
    return "".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  "
                   + p.relative_to(ROOT).as_posix() + "\n" for p in release_files())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-checksums", action="store_true")
    parser.add_argument("--deny", action="append", default=[])
    args = parser.parse_args()
    counts = verify_manifests()
    metadata = verify_research_metadata()
    evidence = verify_reviewed_evidence()
    privacy_scan(args.deny)
    expected = checksum_lines()
    checksum_file = ROOT / "checksums.sha256"
    if args.write_checksums:
        checksum_file.write_text(expected, encoding="utf-8")
    elif checksum_file.read_text(encoding="utf-8") != expected:
        raise ValueError("release checksum coverage or contents changed")
    print(json.dumps({
        "htmlCounts": counts,
        "researchMetadata": metadata,
        "reviewedEvidence": evidence,
        "checksums": "valid",
        "publicationScan": "passed",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
