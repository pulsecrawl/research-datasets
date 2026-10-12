"""Verify release inputs, checksums, and publication boundaries."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"fixed-html": 60, "site-pattern-html": 100, "commerce-html": 20}


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
    privacy_scan(args.deny)
    expected = checksum_lines()
    checksum_file = ROOT / "checksums.sha256"
    if args.write_checksums:
        checksum_file.write_text(expected, encoding="utf-8")
    elif checksum_file.read_text(encoding="utf-8") != expected:
        raise ValueError("release checksum coverage or contents changed")
    print(json.dumps({"htmlCounts": counts, "checksums": "valid", "publicationScan": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
