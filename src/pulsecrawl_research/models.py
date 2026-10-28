"""Stable cross-system experiment models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping


CapabilityState = Literal["supported", "partial", "not_supported"]
RunStatus = Literal["completed", "failed", "unavailable", "timed_out"]


@dataclass(frozen=True)
class Capability:
    name: str
    state: CapabilityState
    detail: str = ""


@dataclass(frozen=True)
class Scenario:
    experiment_id: str
    name: str
    seed_urls: tuple[str, ...]
    max_urls: int
    max_depth: int = 3
    concurrency: int = 1
    timeout_seconds: float = 60.0
    respect_robots: bool = True
    requests_per_second: float = 100.0
    expected: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.experiment_id:
            raise ValueError("experiment_id is required")
        if not self.seed_urls:
            raise ValueError("at least one seed URL is required")
        if self.max_urls < 1:
            raise ValueError("max_urls must be positive")
        if self.max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        if self.concurrency < 1:
            raise ValueError("concurrency must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Scenario":
        return cls(
            experiment_id=str(raw["experimentId"]),
            name=str(raw.get("name") or raw["experimentId"]),
            seed_urls=tuple(str(value) for value in raw["seedUrls"]),
            max_urls=int(raw["maxUrls"]),
            max_depth=int(raw.get("maxDepth", 3)),
            concurrency=int(raw.get("concurrency", 1)),
            timeout_seconds=float(raw.get("timeoutSeconds", 60)),
            respect_robots=bool(raw.get("respectRobots", True)),
            requests_per_second=float(raw.get("requestsPerSecond", 100)),
            expected=dict(raw.get("expected") or {}),
            metadata=dict(raw.get("metadata") or {}),
        )


@dataclass
class RunResult:
    experiment_id: str
    system: str
    profile: str
    status: RunStatus
    started_at: str
    finished_at: str
    duration_seconds: float
    system_version: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    capabilities: list[Capability] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    observations: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = [asdict(value) for value in self.capabilities]
        return payload
