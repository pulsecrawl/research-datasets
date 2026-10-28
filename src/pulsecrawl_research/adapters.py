"""Adapters that normalize external crawler execution."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .models import Capability, RunResult, Scenario
from .registry import RESEARCH_ROOT


REPO_ROOT = RESEARCH_ROOT.parent


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class BaselineAdapter(ABC):
    system_id: str

    @abstractmethod
    def availability(self) -> tuple[bool, str]: ...

    @abstractmethod
    def capabilities(self) -> list[Capability]: ...

    @abstractmethod
    def run(self, scenario: Scenario, profile: str) -> RunResult: ...

    def unavailable(self, scenario: Scenario, profile: str, reason: str) -> RunResult:
        now = utc_now()
        return RunResult(
            experiment_id=scenario.experiment_id,
            system=self.system_id,
            profile=profile,
            status="unavailable",
            started_at=now,
            finished_at=now,
            duration_seconds=0,
            capabilities=self.capabilities(),
            errors=[reason],
            configuration=scenario.to_dict(),
        )


class PythonSubprocessAdapter(BaselineAdapter):
    module_name: str
    runner_path: Path

    def availability(self) -> tuple[bool, str]:
        probe = subprocess.run(
            [sys.executable, "-c", f"import {self.module_name}"],
            capture_output=True,
            text=True,
        )
        return (
            probe.returncode == 0,
            "" if probe.returncode == 0 else probe.stderr.strip() or f"{self.module_name} is not installed",
        )

    def run(self, scenario: Scenario, profile: str) -> RunResult:
        available, reason = self.availability()
        if not available:
            return self.unavailable(scenario, profile, reason)
        started_at = utc_now()
        started = time.monotonic()
        env = os.environ.copy()
        env["PULSECRAWL_RESEARCH_PROFILE"] = profile
        try:
            completed = subprocess.run(
                [sys.executable, str(self.runner_path)],
                input=json.dumps(scenario.to_dict()),
                capture_output=True,
                text=True,
                timeout=scenario.timeout_seconds,
                cwd=REPO_ROOT,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return RunResult(
                experiment_id=scenario.experiment_id,
                system=self.system_id,
                profile=profile,
                status="timed_out",
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=time.monotonic() - started,
                capabilities=self.capabilities(),
                errors=[f"runner exceeded {scenario.timeout_seconds:g} seconds"],
                configuration=scenario.to_dict(),
            )
        errors: list[str] = []
        payload: dict[str, Any] = {}
        if completed.returncode != 0:
            errors.append(completed.stderr.strip() or f"runner exited {completed.returncode}")
        else:
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                errors.append(f"runner returned invalid JSON: {completed.stdout[-1000:]}")
        return RunResult(
            experiment_id=scenario.experiment_id,
            system=self.system_id,
            profile=profile,
            status="failed" if errors else "completed",
            started_at=started_at,
            finished_at=utc_now(),
            duration_seconds=time.monotonic() - started,
            system_version=payload.get("systemVersion"),
            metrics=dict(payload.get("metrics") or {}),
            capabilities=self.capabilities(),
            errors=errors + list(payload.get("errors") or []),
            configuration=scenario.to_dict(),
        )


class PulseCrawlAdapter(PythonSubprocessAdapter):
    system_id = "pulsecrawl"
    module_name = "pulsecrawl"
    runner_path = RESEARCH_ROOT / "baselines/pulsecrawl/run.py"

    def capabilities(self) -> list[Capability]:
        return [
            Capability("robots", "supported", "allow/disallow and crawl-delay"),
            Capability("depth_limit", "supported"),
            Capability("per_execution_budget", "supported"),
            Capability("recurring_job_outcome_budget", "supported", "local workspace state"),
            Capability("shared_origin_gate", "supported", "local SQLite gate"),
            Capability("scoped_templates", "supported"),
            Capability("versioned_parquet", "supported", "local workspace publication"),
        ]


class ScrapyAdapter(PythonSubprocessAdapter):
    system_id = "scrapy"
    module_name = "scrapy"
    runner_path = RESEARCH_ROOT / "baselines/scrapy/run.py"

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "robots",
                "partial",
                "allow/disallow; configured delay did not enforce a strict origin interval",
            ),
            Capability("depth_limit", "supported"),
            Capability("per_execution_budget", "partial", "close-spider page count"),
            Capability("recurring_job_outcome_budget", "not_supported", "requires user state"),
            Capability("shared_origin_gate", "not_supported", "requires extension"),
            Capability("scoped_templates", "partial", "manual spider routing"),
            Capability("versioned_parquet", "not_supported", "requires pipeline"),
        ]


class CrawleeAdapter(PythonSubprocessAdapter):
    system_id = "crawlee"
    module_name = "crawlee"
    runner_path = RESEARCH_ROOT / "baselines/crawlee/run.py"

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "robots",
                "partial",
                "allow/disallow; evaluated adapter did not enforce robots crawl-delay",
            ),
            Capability("depth_limit", "supported"),
            Capability("per_execution_budget", "partial", "may overshoot with concurrency"),
            Capability("recurring_job_outcome_budget", "not_supported", "requires user state"),
            Capability("shared_origin_gate", "not_supported", "requires shared adapter"),
            Capability("scoped_templates", "partial", "request router"),
            Capability("versioned_parquet", "not_supported", "requires exporter"),
        ]


class FirecrawlAdapter(BaselineAdapter):
    system_id = "firecrawl-local"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("FIRECRAWL_API_URL") or "http://127.0.0.1:3002").rstrip("/")

    def availability(self) -> tuple[bool, str]:
        try:
            with urlopen(f"{self.base_url}/v0/health/liveness", timeout=2) as response:
                return (response.status < 500, "")
        except (OSError, URLError, HTTPError) as exc:
            return (False, f"Firecrawl is not reachable at {self.base_url}: {exc}")

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "robots",
                "partial",
                "allow/disallow; the inspected local service did not enforce robots crawl-delay",
            ),
            Capability("depth_limit", "supported"),
            Capability("per_execution_budget", "supported", "crawl limit"),
            Capability("recurring_job_outcome_budget", "not_supported"),
            Capability("shared_origin_gate", "partial", "service concurrency/delay differs"),
            Capability("scoped_templates", "partial", "structured JSON extraction differs"),
            Capability("versioned_parquet", "not_supported"),
        ]

    def run(self, scenario: Scenario, profile: str) -> RunResult:
        available, reason = self.availability()
        if not available:
            return self.unavailable(scenario, profile, reason)
        started_at = utc_now()
        started = time.monotonic()
        seed = scenario.seed_urls[0]
        parsed_seed = urlsplit(seed)
        if parsed_seed.hostname in {"127.0.0.1", "localhost"}:
            port = f":{parsed_seed.port}" if parsed_seed.port else ""
            seed = urlunsplit(
                (
                    parsed_seed.scheme,
                    f"host.docker.internal{port}",
                    parsed_seed.path,
                    parsed_seed.query,
                    parsed_seed.fragment,
                )
            )
        body = json.dumps(
            {
                "url": seed,
                "limit": scenario.max_urls,
                "maxDiscoveryDepth": scenario.max_depth,
                "crawlEntireDomain": True,
                "maxConcurrency": scenario.concurrency,
                "sitemap": "skip",
                "scrapeOptions": {"formats": ["html"], "onlyMainContent": False},
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            request = Request(f"{self.base_url}/v2/crawl", data=body, headers=headers, method="POST")
            with urlopen(request, timeout=10) as response:
                created = json.load(response)
            job_id = created.get("id")
            if not job_id:
                raise RuntimeError(f"crawl response has no id: {created}")
            deadline = time.monotonic() + scenario.timeout_seconds
            latest: dict[str, Any] = created
            while time.monotonic() < deadline:
                with urlopen(f"{self.base_url}/v2/crawl/{job_id}", timeout=10) as response:
                    latest = json.load(response)
                if latest.get("status") in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError("Firecrawl job did not finish")
            status = "completed" if latest.get("status") == "completed" else "failed"
            errors = [] if status == "completed" else [str(latest.get("error") or latest.get("status"))]
            metrics = {
                "pagesCompleted": int(latest.get("completed") or len(latest.get("data") or [])),
                "pagesTotal": int(latest.get("total") or 0),
                "creditsUsed": latest.get("creditsUsed"),
                "jobId": job_id,
            }
        except TimeoutError as exc:
            status, errors, metrics = "timed_out", [str(exc)], {}
        except HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            status, errors, metrics = "failed", [f"{exc}: {detail}"], {}
        except (OSError, URLError, RuntimeError, ValueError) as exc:
            status, errors, metrics = "failed", [str(exc)], {}
        return RunResult(
            experiment_id=scenario.experiment_id,
            system=self.system_id,
            profile=profile,
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            finished_at=utc_now(),
            duration_seconds=time.monotonic() - started,
            metrics=metrics,
            capabilities=self.capabilities(),
            errors=errors,
            configuration=scenario.to_dict(),
        )


def adapters() -> dict[str, BaselineAdapter]:
    values: list[BaselineAdapter] = [
        PulseCrawlAdapter(),
        ScrapyAdapter(),
        CrawleeAdapter(),
        FirecrawlAdapter(),
    ]
    return {value.system_id: value for value in values}


def doctor() -> dict[str, Any]:
    report: dict[str, Any] = {
        "python": sys.version,
        "docker": shutil.which("docker"),
        "systems": {},
    }
    for name, adapter in adapters().items():
        available, reason = adapter.availability()
        report["systems"][name] = {
            "available": available,
            "reason": "" if available else reason,
            "capabilities": [capability.__dict__ for capability in adapter.capabilities()],
        }
    return report
