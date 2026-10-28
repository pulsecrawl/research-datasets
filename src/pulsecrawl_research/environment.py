"""Reproducibility metadata capture."""
from __future__ import annotations

import os
import hashlib
import platform
import shutil
import subprocess
import sys
from importlib import metadata, util
from pathlib import Path
from typing import Any


def _git_value(repo: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def capture(repo: Path) -> dict[str, Any]:
    memory_bytes: int | None = None
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        memory_bytes = int(page_size * pages)
    except (AttributeError, OSError, ValueError):
        pass
    try:
        pulsecrawl_version = metadata.version("pulsecrawl")
    except metadata.PackageNotFoundError:
        pulsecrawl_version = None
    specification = util.find_spec("pulsecrawl")
    pulsecrawl_location = (
        str(Path(specification.origin).resolve())
        if specification is not None and specification.origin is not None
        else None
    )
    research_source = repo / "research" / "src" / "pulsecrawl_research"
    source_files: dict[str, str] = {}
    if research_source.is_dir():
        for path in sorted(research_source.rglob("*.py")):
            source_files[path.relative_to(repo).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    aggregate = hashlib.sha256()
    for name, digest in source_files.items():
        aggregate.update(f"{name}\0{digest}\n".encode())
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpuCount": os.cpu_count(),
        "memoryBytes": memory_bytes,
        "gitCommit": _git_value(repo, "rev-parse", "HEAD"),
        "gitBranch": _git_value(repo, "branch", "--show-current"),
        "gitDirty": bool(_git_value(repo, "status", "--porcelain")),
        "dockerAvailable": shutil.which("docker") is not None,
        "pulsecrawlDistributionVersion": pulsecrawl_version,
        "pulsecrawlImportLocation": pulsecrawl_location,
        "researchSourceFiles": source_files,
        "researchSourceSha256": aggregate.hexdigest() if source_files else None,
    }
