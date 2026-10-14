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
        "checksums": "valid",
        "publicationScan": "passed",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
