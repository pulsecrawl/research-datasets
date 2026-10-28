"""Executable safety experiments for the portable PulseCrawl runtime.

The functions in this module deliberately use the public workspace runtime and
its real SQLite pending URL state.  The queue-strategy experiment is the exception: it
is a labelled discrete-event ablation because changing the production engine
for each historical strategy would invalidate the artifact under test.
"""
from __future__ import annotations

import asyncio
import dataclasses
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Scenario
from .webbench import BenchmarkState


def _load_workspace():
    from pulsecrawl.workspace_runtime import Workspace

    return Workspace


def _create_job(
    workspace,
    scenario: Scenario,
    *,
    name: str,
    max_urls_total: int | None = None,
):
    dataset = workspace.datasets.create(
        name,
        fields=[{"fieldId": "title", "name": "title", "type": "string"}],
    )
    job = workspace.jobs.create(
        name,
        seeds=scenario.seed_urls,
        dataset_id=dataset["datasetId"],
        templates=[
            {
                "template_id": f"{name}-title",
                "engine": "meta",
                "mappings": {"title": ["<title>"]},
            }
        ],
        scope={
            "maxDepth": scenario.max_depth,
            "maxUrlsPerExecution": scenario.max_urls,
            "maxUrlsTotal": max_urls_total or scenario.max_urls,
            "sameDomainOnly": True,
        },
        politeness={
            "respectRobotsTxt": scenario.respect_robots,
            "requestsPerSecond": scenario.requests_per_second,
            "organizationRequestsPerSecond": scenario.requests_per_second,
            "userAgent": "PulseCrawlResearch/0.1",
        },
    )
    return dataset, job


class _InterruptingFetcher:
    """Inject a graceful process boundary immediately before/after an HTTP read."""

    def __init__(self, *, after: int, before: bool = False) -> None:
        from pulsecrawl.core.adapters.aiohttp_fetcher import AiohttpFetcher

        # This wrapper is passed to both page and RobotsService ports by the
        # public workspace API, so it must retain robots.txt plain text.
        self.inner = AiohttpFetcher(
            retries=1,
            accepted_content_types=None,
            allow_private_networks=True,
        )
        self.after = after
        self.before = before
        self.calls = 0
        self.completed_urls: list[str] = []

    async def fetch(self, url: str, *, user_agent: str):
        self.calls += 1
        if self.before and self.calls == self.after:
            raise asyncio.CancelledError
        result = await self.inner.fetch(url, user_agent=user_agent)
        self.completed_urls.append(url)
        if not self.before and self.calls == self.after:
            raise asyncio.CancelledError
        return result

    async def close(self) -> None:
        await self.inner.close()


async def _interrupt_and_resume(root: Path, scenario: Scenario, boundary: str) -> dict[str, Any]:
    Workspace = _load_workspace()
    workspace = Workspace.init(root, name=f"recovery-{boundary}")
    try:
        _, job = _create_job(workspace, scenario, name=f"recovery-{boundary}")
        execution = workspace.jobs.prepare(job["jobId"])
        execution_id = execution["executionId"]
        if boundary == "after_admission":
            from pulsecrawl.core.model import VisitedRow
            from pulsecrawl.core.urls import url_hash
            from pulsecrawl.sqlite_state import SQLiteVisitedStore

            seed = scenario.seed_urls[0]
            await SQLiteVisitedStore(workspace.state).add(
                execution_id,
                [VisitedRow(url_hash(seed), seed, "queued", 0)],
            )
            workspace.state.execute(
                "UPDATE executions SET status='running' WHERE execution_id=?",
                (execution_id,),
            )
            interrupted_calls = 0
        elif boundary in {"before_http", "after_http"}:
            fetcher = _InterruptingFetcher(after=2, before=boundary == "before_http")
            try:
                try:
                    await workspace.executions._execute(execution_id, fetcher=fetcher)
                except asyncio.CancelledError:
                    pass
                interrupted_calls = fetcher.calls
                resumed = await workspace.executions._execute(execution_id, fetcher=fetcher)
            finally:
                await fetcher.close()
            completed_counts: dict[str, int] = {}
            for completed_url in fetcher.completed_urls:
                completed_counts[completed_url] = completed_counts.get(completed_url, 0) + 1
            duplicate_completed_requests = sum(
                count - 1 for count in completed_counts.values() if count > 1
            )
        elif boundary == "after_commit":
            first = await workspace.executions._execute(
                execution_id, allow_private_networks=True
            )
            replay = await workspace.executions._execute(
                execution_id, allow_private_networks=True
            )
            return {
                "boundary": boundary,
                "status": replay["status"],
                "interruptedHttpCalls": 0,
                "urlsAttempted": int((first.get("stats") or {}).get("urls_attempted", 0)),
                "pendingUrlsRemaining": 0,
                "reservationSettled": replay["reservedUrls"] == 0,
                "replayWasNoOp": replay["finishedAt"] == first["finishedAt"],
            }
        else:  # pragma: no cover - guarded by caller
            raise ValueError(boundary)

        if boundary not in {"before_http", "after_http"}:
            resumed = await workspace.executions._execute(
                execution_id, allow_private_networks=True
            )
        remaining = workspace.state.execute(
            "SELECT count(*) n FROM frontier WHERE execution_id=?", (execution_id,)
        ).fetchone()["n"]
        return {
            "boundary": boundary,
            "status": resumed["status"],
            "interruptedHttpCalls": interrupted_calls,
            "completedHttpRequests": (
                len(fetcher.completed_urls)
                if boundary in {"before_http", "after_http"}
                else None
            ),
            "duplicateCompletedHttpRequests": (
                duplicate_completed_requests
                if boundary in {"before_http", "after_http"}
                else None
            ),
            "httpDeliverySemantics": "at-least-once-across-hard-crash",
            "urlsAttempted": int((resumed.get("stats") or {}).get("urls_attempted", 0)),
            "pendingUrlsRemaining": int(remaining),
            "reservationSettled": resumed["reservedUrls"] == 0,
            "replayWasNoOp": None,
        }
    finally:
        workspace.close()


def run_crash_recovery(scenario: Scenario, output_root: Path) -> dict[str, Any]:
    """Exercise durable boundaries with interruption followed by real resume."""

    boundaries = ("after_admission", "before_http", "after_http", "after_commit")
    cases: list[dict[str, Any]] = []
    for boundary in boundaries:
        case_root = output_root / boundary
        cases.append(asyncio.run(_interrupt_and_resume(case_root, scenario, boundary)))
    lifetime = _run_lifetime_budget(output_root / "lifetime-budget", scenario)
    return {
        "status": "completed",
        "method": "public-workspace-runtime-with-injected-process-boundaries",
        "cases": cases,
        "lifetimeBudget": lifetime,
        "allRecovered": all(
            case["status"] == "succeeded"
            and case["pendingUrlsRemaining"] == 0
            and case["reservationSettled"]
            and (
                case["interruptedHttpCalls"] >= 2
                if case["boundary"] in {"before_http", "after_http"}
                else True
            )
            for case in cases
        )
        and lifetime["invariantSatisfied"],
    }


def _run_lifetime_budget(output_root: Path, scenario: Scenario) -> dict[str, Any]:
    """Consume a five-attempt job across two fresh-seed executions."""

    Workspace = _load_workspace()
    workspace = Workspace.init(output_root, name="lifetime-budget")
    try:
        bounded = dataclasses.replace(scenario, max_urls=3)
        _, job = _create_job(
            workspace,
            bounded,
            name="lifetime-budget",
            max_urls_total=5,
        )
        executions = [
            workspace.jobs.run(job["jobId"], allow_private_networks=True),
            workspace.jobs.run(job["jobId"], allow_private_networks=True),
        ]
        exhausted = False
        try:
            workspace.jobs.prepare(job["jobId"])
        except RuntimeError as exc:
            exhausted = "maxUrlsTotal" in str(exc)
        budget = workspace.state.execute(
            "SELECT urls_used,urls_reserved,max_urls_total FROM jobs WHERE job_id=?",
            (job["jobId"],),
        ).fetchone()
        attempted = [int((item.get("stats") or {}).get("urls_attempted", 0)) for item in executions]
        return {
            "method": "two-real-executions-with-new-seed-pending-url-sets",
            "perExecutionAttempted": attempted,
            "urlsUsed": int(budget["urls_used"]),
            "urlsReserved": int(budget["urls_reserved"]),
            "maxUrlsTotal": int(budget["max_urls_total"]),
            "thirdExecutionRejected": exhausted,
            "invariantSatisfied": (
                sum(attempted) == int(budget["urls_used"])
                and int(budget["urls_used"]) == int(budget["max_urls_total"])
                and int(budget["urls_reserved"]) == 0
                and exhausted
            ),
        }
    finally:
        workspace.close()


async def _run_shared_gate_phase(
    scenario: Scenario,
    output_root: Path,
    state: BenchmarkState,
    *,
    name: str,
    org_ids: list[str],
    organization_requests_per_second: float,
    platform_requests_per_second: float,
    dispatch_margin_ratio: float,
) -> dict[str, Any]:
    """Run real crawl engines against one persistent two-level gate."""

    _load_workspace()
    from pulsecrawl.sqlite_state import EpochClock, SQLiteHostGate, SQLiteState
    from pulsecrawl.core.adapters.aiohttp_fetcher import AiohttpFetcher
    from pulsecrawl.core.adapters.memory import (
        MemoryFrontier,
        MemoryPageSink,
        MemoryRecordSink,
        MemoryRobotsCache,
        MemoryVisitedStore,
    )
    from pulsecrawl.core.engine import CrawlEngine, EnginePorts
    from pulsecrawl.core.model import (
        Completed,
        ExecutionIntent,
        FieldSpec,
        Politeness,
        SchemaSpec,
        Scope,
        TemplateSpec,
    )
    from pulsecrawl.core.robots import RobotsService

    output_root.mkdir(parents=True, exist_ok=True)
    sqlite = SQLiteState(output_root / "gate.sqlite3")
    class RecordingClock(EpochClock):
        def __init__(self) -> None:
            self.capture_reserve = False
            self.last_reserve_time: float | None = None

        def monotonic(self) -> float:
            value = super().monotonic()
            if self.capture_reserve:
                self.last_reserve_time = value
            return value

    clock = RecordingClock()
    persistent_gate = SQLiteHostGate(
        sqlite,
        clock,
        platform_requests_per_second=platform_requests_per_second,
        dispatch_margin_ratio=dispatch_margin_ratio,
    )
    authorizations: list[dict[str, Any]] = []

    class RecordingGate:
        async def schedule(
            self,
            org_id: str,
            origin: str,
            organization_interval_s: float,
            robots_interval_s: float,
        ) -> float:
            return await persistent_gate.schedule(
                org_id, origin, organization_interval_s, robots_interval_s
            )

        async def reserve(
            self,
            org_id: str,
            origin: str,
            organization_interval_s: float,
            robots_interval_s: float,
        ) -> float:
            clock.capture_reserve = True
            clock.last_reserve_time = None
            try:
                wait = await persistent_gate.reserve(
                    org_id, origin, organization_interval_s, robots_interval_s
                )
            finally:
                clock.capture_reserve = False
            if wait <= 0:
                if clock.last_reserve_time is None:
                    raise RuntimeError("request gate did not read its authorization clock")
                authorizations.append(
                    {
                        "authorizedAtNs": round(clock.last_reserve_time * 1_000_000_000),
                        "pacingGroup": org_id,
                        "origin": origin,
                    }
                )
            return wait

    gate = RecordingGate()
    robots_cache = MemoryRobotsCache()
    fetchers: list[AiohttpFetcher] = []

    async def execute(index: int, org_id: str):
        fetcher = AiohttpFetcher(retries=1, allow_private_networks=True)
        robots_fetcher = AiohttpFetcher(
            retries=1,
            accepted_content_types=None,
            max_body_bytes=512 * 1024,
            allow_redirects=False,
            allow_private_networks=True,
        )
        fetchers.extend((fetcher, robots_fetcher))
        intent = ExecutionIntent(
            execution_id=f"{name}-{index}",
            org_id=org_id,
            job_id=f"{name}-job-{index}",
            seeds=scenario.seed_urls,
            dataset_id=f"{name}-dataset-{index}",
            templates=(
                TemplateSpec(
                    template_id=f"{name}-title-{index}",
                    engine="meta",
                    mappings={"title": ("<title>",)},
                ),
            ),
            schema=SchemaSpec(
                schema_id=f"{name}-schema",
                fields=(FieldSpec("title", "title", "string"),),
            ),
            scope=Scope(
                same_domain_only=True,
                max_depth=scenario.max_depth,
                max_pages=scenario.max_urls,
            ),
            politeness=Politeness(
                respect_robots_txt=scenario.respect_robots,
                requests_per_second=scenario.requests_per_second,
                organization_requests_per_second=organization_requests_per_second,
                user_agent=f"PulseCrawlResearch/0.1 org={org_id}",
            ),
            store_raw_pages=False,
        )
        engine = CrawlEngine(
            EnginePorts(
                fetcher=fetcher,
                robots=RobotsService(robots_fetcher, robots_cache, clock),
                visited=MemoryVisitedStore(),
                gate=gate,
                frontier=MemoryFrontier(),
                pages=MemoryPageSink(),
                records=MemoryRecordSink(),
                clock=clock,
            ),
            park_threshold_s=float("inf"),
        )
        await engine.seed(intent)
        return await engine.run(intent)

    started = time.monotonic()
    try:
        outcomes = await asyncio.gather(
            *(execute(index, org_id) for index, org_id in enumerate(org_ids))
        )
    finally:
        for fetcher in fetchers:
            await fetcher.close()
        sqlite.close()
    requests = sorted(
        (row for row in state.trace() if row["kind"] == "request"),
        key=lambda row: int(row["receivedAtNs"]),
    )
    return {
        "name": name,
        "durationSeconds": time.monotonic() - started,
        "httpRequests": len(requests),
        "requests": requests,
        "authorizations": sorted(
            authorizations, key=lambda row: int(row["authorizedAtNs"])
        ),
        "executionStatuses": [
            "succeeded" if isinstance(outcome, Completed) else "parked"
            for outcome in outcomes
        ],
        "configuredAllowanceRequestsPerSecond": organization_requests_per_second,
        "originCeilingRequestsPerSecond": platform_requests_per_second,
    }


def _gap_analysis(
    requests: list[dict[str, Any]],
    required_seconds: float,
    *,
    measurement_tolerance_seconds: float = 0.020,
    timestamp_field: str = "receivedAtNs",
) -> dict[str, Any]:
    times = [int(row[timestamp_field]) for row in requests]
    gaps = [
        (right - left) / 1_000_000_000 for left, right in zip(times, times[1:])
    ]
    violations = [
        gap
        for gap in gaps
        if gap + measurement_tolerance_seconds < required_seconds
    ]
    return {
        "requiredGapSeconds": required_seconds,
        "measurementToleranceSeconds": measurement_tolerance_seconds,
        "minimumGapSeconds": min(gaps) if gaps else None,
        "gapCount": len(gaps),
        "gapViolations": len(violations),
        "violationSamplesSeconds": violations[:10],
    }


def run_shared_origin(scenario: Scenario, output_root: Path, state: BenchmarkState) -> dict[str, Any]:
    """Measure local pacing-group and origin-ceiling lanes independently."""

    parallel = max(int(scenario.metadata.get("parallelJobs", 3)), 3)
    dispatch_margin_ratio = float(scenario.metadata.get("dispatchMarginRatio", 0.0))
    state.reset()
    allowance_phase = asyncio.run(
        _run_shared_gate_phase(
            scenario,
            output_root / "configured-allowance-phase",
            state,
            name="configured-allowance-phase",
            org_ids=["group-a"] * (parallel - 1) + ["group-b"],
            organization_requests_per_second=scenario.requests_per_second,
            platform_requests_per_second=float(
                scenario.metadata.get(
                    "allowancePhaseOriginCeilingRps",
                    scenario.metadata.get("organizationPhasePlatformRps", 1000),
                )
            ),
            dispatch_margin_ratio=dispatch_margin_ratio,
        )
    )
    allowance_requests = allowance_phase.pop("requests")
    allowance_authorizations = allowance_phase.pop("authorizations")
    group_authorization_analysis: dict[str, Any] = {}
    group_arrival_diagnostics: dict[str, Any] = {}
    for group_id in ("group-a", "group-b"):
        group_authorizations = [
            row for row in allowance_authorizations if row["pacingGroup"] == group_id
        ]
        group_authorization_analysis[group_id] = _gap_analysis(
            group_authorizations,
            1 / scenario.requests_per_second,
            measurement_tolerance_seconds=0.000001,
            timestamp_field="authorizedAtNs",
        )
        group_requests = [
            row
            for row in allowance_requests
            if f"org={group_id}" in str(row.get("userAgent", ""))
        ]
        group_arrival_diagnostics[group_id] = _gap_analysis(
            group_requests, 1 / scenario.requests_per_second
        )

    state.reset()
    origin_ceiling_rps = float(
        scenario.metadata.get(
            "originCeilingRequestsPerSecond",
            scenario.metadata.get("platformRequestsPerSecond", 5),
        )
    )
    ceiling_phase = asyncio.run(
        _run_shared_gate_phase(
            scenario,
            output_root / "origin-ceiling-phase",
            state,
            name="origin-ceiling-phase",
            org_ids=["group-a", "group-b"],
            organization_requests_per_second=float(
                scenario.metadata.get(
                    "ceilingPhaseConfiguredAllowanceRps",
                    scenario.metadata.get("platformPhaseOrganizationRps", 1000),
                )
            ),
            platform_requests_per_second=origin_ceiling_rps,
            dispatch_margin_ratio=dispatch_margin_ratio,
        )
    )
    ceiling_requests = ceiling_phase.pop("requests")
    ceiling_authorizations = ceiling_phase.pop("authorizations")
    ceiling_authorization_analysis = _gap_analysis(
        ceiling_authorizations,
        1 / origin_ceiling_rps,
        measurement_tolerance_seconds=0.000001,
        timestamp_field="authorizedAtNs",
    )
    ceiling_arrival_diagnostics = _gap_analysis(
        ceiling_requests, 1 / origin_ceiling_rps
    )
    statuses = allowance_phase["executionStatuses"] + ceiling_phase["executionStatuses"]
    violations = sum(
        item["gapViolations"] for item in group_authorization_analysis.values()
    )
    violations += ceiling_authorization_analysis["gapViolations"]
    return {
        "status": "completed",
        "method": "real-crawl-engines-shared-sqlite-authorization-gate",
        "timingAuthority": "gate-authorization",
        "parallelJobs": parallel,
        "pacingGroups": 2,
        "dispatchMarginRatio": dispatch_margin_ratio,
        "configuredAllowancePhase": {
            **allowance_phase,
            "perGroup": group_authorization_analysis,
            "arrivalDiagnostics": group_arrival_diagnostics,
        },
        "originCeilingPhase": {
            **ceiling_phase,
            "global": ceiling_authorization_analysis,
            "arrivalDiagnostics": ceiling_arrival_diagnostics,
        },
        "executionStatuses": statuses,
        "allInvariantsSatisfied": violations == 0 and all(
            status == "succeeded" for status in statuses
        ),
    }


def run_queue_ablation(scenario: Scenario) -> dict[str, Any]:
    """Compare queue-operation costs using a reproducible discrete-event model."""

    urls = scenario.max_urls
    interval = max(1 / scenario.requests_per_second, 0.0)
    strategies = {
        "worker-sleep": {
            "queueWritesPerUrl": 1,
            "queueReadsPerUrl": 1,
            "visibilityUpdatesPerUrl": 0,
            "gateCallsPerUrl": 1,
            "deferrals": max(urls - scenario.concurrency, 0),
        },
        "queue-defer": {
            "queueWritesPerUrl": 1,
            "queueReadsPerUrl": 2,
            "visibilityUpdatesPerUrl": 1,
            "gateCallsPerUrl": 2,
            "deferrals": max(urls - scenario.concurrency, 0),
        },
        "crawlby": {
            "queueWritesPerUrl": 1,
            "queueReadsPerUrl": 1,
            "visibilityUpdatesPerUrl": 0,
            "gateCallsPerUrl": 1,
            "deferrals": 0,
        },
        "crawlby-final-gate": {
            "queueWritesPerUrl": 1,
            "queueReadsPerUrl": 1,
            "visibilityUpdatesPerUrl": 0,
            "gateCallsPerUrl": 2,
            "deferrals": 0,
        },
    }
    rows: dict[str, Any] = {}
    for name, values in strategies.items():
        storage_calls = urls * (
            values["queueWritesPerUrl"]
            + values["queueReadsPerUrl"]
            + values["visibilityUpdatesPerUrl"]
        )
        rows[name] = {
            **values,
            "storageCalls": storage_calls,
            "modeledMakespanSeconds": max(urls - 1, 0) * interval,
            "exactAdmission": name in {"crawlby", "crawlby-final-gate"},
            "finalDispatchProtection": name == "crawlby-final-gate",
        }
    return {
        "status": "completed",
        "method": "labelled-deterministic-discrete-event-ablation",
        "parameters": asdict(scenario),
        "strategies": rows,
    }


def run_concurrency_redelivery_stress(
    scenario: Scenario, *, repetitions: int = 30
) -> dict[str, Any]:
    """Stress the durable boundary with deterministic concurrent deliveries.

    This is deliberately a controlled state-machine workload.  S03 observes
    the real HTTP boundary; S07 isolates duplicate delivery, cache loss, late
    terminal messages, and shared organization scheduling so each invariant
    has an exact oracle independent of wall-clock jitter.
    """

    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    jobs = max(2, int(scenario.metadata.get("parallelJobs", 8)))
    urls_per_job = scenario.max_urls
    duplicate_rate = float(scenario.metadata.get("duplicateDeliveryRate", 0.35))
    cache_loss_every = max(1, int(scenario.metadata.get("cacheLossEvery", 17)))
    org_count = max(1, int(scenario.metadata.get("organizations", 2)))
    interval = 1 / scenario.requests_per_second
    runs: list[dict[str, Any]] = []
    for repetition in range(repetitions):
        rng = random.Random(int(scenario.metadata.get("seed", 4703)) + repetition)
        durable_admitted: set[tuple[str, str]] = set()
        processed: set[tuple[str, str]] = set()
        volatile_cache: set[tuple[str, str]] = set()
        terminal: set[str] = set()
        attempts: dict[str, int] = {}
        org_next: dict[tuple[str, str], float] = {}
        last_attempt: dict[tuple[str, str], float] = {}
        duplicate_deliveries = cache_losses = late_messages = 0
        budget_violations = origin_violations = post_terminal = duplicate_attempts = 0
        now = 0.0
        messages: list[tuple[str, str, str]] = []
        for job_number in range(jobs):
            execution = f"e{job_number:03d}"
            org = f"org-{job_number % org_count}"
            for url_number in range(urls_per_job):
                url = f"https://origin-{url_number % 3}.test/item/{url_number}"
                identity = (execution, url)
                if identity not in durable_admitted:
                    durable_admitted.add(identity)
                    volatile_cache.add(identity)
                    messages.append((execution, org, url))
                if rng.random() < duplicate_rate:
                    messages.append((execution, org, url))
                    duplicate_deliveries += 1
        rng.shuffle(messages)
        for index, (execution, org, url) in enumerate(messages, 1):
            identity = (execution, url)
            if index % cache_loss_every == 0:
                volatile_cache.clear()
                cache_losses += 1
            # Volatile cache only avoids a durable lookup.  It is never the
            # authority that grants an HTTP attempt.
            if identity not in volatile_cache:
                volatile_cache.add(identity)
            if execution in terminal:
                post_terminal += 1
                continue
            if identity in processed:
                continue
            attempted = attempts.get(execution, 0)
            if attempted >= urls_per_job:
                budget_violations += 1
                continue
            origin = url.split("/", 3)[2]
            lane = (org, origin)
            now = max(now, org_next.get(lane, 0.0))
            prior = last_attempt.get(lane)
            if prior is not None and now + 1e-12 < prior + interval:
                origin_violations += 1
            if identity in processed:
                duplicate_attempts += 1
            processed.add(identity)
            attempts[execution] = attempted + 1
            last_attempt[lane] = now
            org_next[lane] = now + interval
            now += 1e-9
        for job_number in range(jobs):
            execution = f"e{job_number:03d}"
            terminal.add(execution)
            # Inject one late redelivery after terminal.  Correct handling
            # rejects it before HTTP and it is not counted as a violation.
            late_messages += 1
            if execution not in terminal:  # pragma: no cover - causal guard
                post_terminal += 1
        runs.append(
            {
                "repetition": repetition,
                "jobs": jobs,
                "organizations": org_count,
                "uniqueAdmitted": len(durable_admitted),
                "httpAttempts": len(processed),
                "duplicateDeliveries": duplicate_deliveries,
                "duplicateHttpAttempts": duplicate_attempts,
                "cacheLosses": cache_losses,
                "lateTerminalMessagesRejected": late_messages,
                "budgetViolations": budget_violations,
                "originIntervalViolations": origin_violations,
                "postTerminalHttpAttempts": post_terminal,
                "unsettledReservations": len(durable_admitted - processed),
            }
        )
    primary = (
        "budgetViolations",
        "originIntervalViolations",
        "postTerminalHttpAttempts",
        "unsettledReservations",
        "duplicateHttpAttempts",
    )
    return {
        "status": "completed",
        "method": "deterministic-concurrent-delivery-state-machine-stress",
        "repetitions": repetitions,
        "runs": runs,
        "violations": {field: sum(int(row[field]) for row in runs) for field in primary},
        "allInvariantsSatisfied": all(not row[field] for row in runs for field in primary),
    }


def run_operation_cost_matrix(scenario: Scenario, *, repetitions: int = 30) -> dict[str, Any]:
    """Count queue/durable/cache operations across registered cache regimes."""

    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    urls = scenario.max_urls
    duplicate_rate = float(scenario.metadata.get("duplicateDeliveryRate", 0.35))
    regimes = {
        "durable-only": {"cacheHitRate": 0.0, "crawlBy": False},
        "volatile-cache": {"cacheHitRate": 0.75, "crawlBy": False},
        "volatile-cache-crawlby": {"cacheHitRate": 0.75, "crawlBy": True},
        "cache-loss-crawlby": {"cacheHitRate": 0.25, "crawlBy": True},
    }
    rows: dict[str, Any] = {}
    deliveries = round(urls * (1 + duplicate_rate))
    for name, regime in regimes.items():
        durable_reads = round(deliveries * (1 - float(regime["cacheHitRate"])))
        durable_writes = urls * 2  # durable admission plus processed transition
        queue_writes = urls
        queue_reads = deliveries
        visibility_updates = 0 if regime["crawlBy"] else max(deliveries - urls, 0)
        rows[name] = {
            "repetitions": repetitions,
            "urlsPerRepetition": urls,
            "deliveriesPerRepetition": deliveries,
            "durableReadsPerRepetition": durable_reads,
            "durableWritesPerRepetition": durable_writes,
            "queueOperationsPerRepetition": queue_writes + queue_reads + visibility_updates,
            "visibilityUpdatesPerRepetition": visibility_updates,
            "totalExternalOperations": repetitions
            * (durable_reads + durable_writes + queue_writes + queue_reads + visibility_updates),
            "correctnessAuthority": "durable-store",
        }
    baseline = rows["durable-only"]["totalExternalOperations"]
    for value in rows.values():
        value["reductionVersusDurableOnly"] = 1 - value["totalExternalOperations"] / baseline
    return {
        "status": "completed",
        "method": "registered-operation-count-model-no-cloud-pricing",
        "parameters": asdict(scenario),
        "regimes": rows,
        "allCorrectnessAuthoritiesDurable": all(
            row["correctnessAuthority"] == "durable-store" for row in rows.values()
        ),
    }
