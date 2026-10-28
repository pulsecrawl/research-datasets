"""Immutable run directories and artifact checksums."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .registry import RESEARCH_ROOT


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


class RunStore:
    def __init__(self, experiment_id: str, root: Path | None = None) -> None:
        root = root or RESEARCH_ROOT / "results" / "runs"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"{timestamp}-{experiment_id.lower()}-{uuid4().hex[:8]}"
        self.path = root / self.run_id
        self.path.mkdir(parents=True, exist_ok=False)

    def write(self, name: str, value: Any) -> Path:
        path = self.path / name
        atomic_json(path, value)
        return path

    def finalize(self) -> Path:
        lines: list[str] = []
        for path in sorted(self.path.rglob("*")):
            if not path.is_file() or path.name == "checksums.sha256":
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(self.path).as_posix()}")
        checksum_path = self.path / "checksums.sha256"
        checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return checksum_path
