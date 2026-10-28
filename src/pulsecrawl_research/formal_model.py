"""Executable trace model for the registered crawl-safety invariants."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class SafetyEvent:
    event: str
    execution: str
    url: str | None = None
    at: float | None = None
    reservations: int | None = None
    pending_urls: int | None = None


_NEXT = {
    None: {"discover"},
    "discovered": {"admit"},
    "admitted": {"schedule"},
    "scheduled": {"enqueue"},
    "queued": {"dispatch"},
    "dispatch_authorized": {"attempt"},
    "attempted": {"process"},
    "processed": {"settle"},
    "settled": set(),
}
_STATE_AFTER = {
    "discover": "discovered",
    "admit": "admitted",
    "schedule": "scheduled",
    "enqueue": "queued",
    "dispatch": "dispatch_authorized",
    "attempt": "attempted",
    "process": "processed",
    "settle": "settled",
}
_WORK_EVENTS = frozenset(_STATE_AFTER)


def evaluate_trace(
    events: Iterable[SafetyEvent],
    *,
    max_per_execution: int,
    max_total: int,
    minimum_origin_interval: float,
    timing_tolerance: float = 0.0,
) -> dict[str, Any]:
    """Evaluate state transitions and global invariants over one origin."""

    materialized = list(events)
    states: dict[tuple[str, str], str] = {}
    terminal: set[str] = set()
    attempts: dict[str, int] = defaultdict(int)
    attempt_times: list[float] = []
    violations: list[dict[str, Any]] = []

    def violate(invariant: str, event: SafetyEvent, **details: Any) -> None:
        violations.append({"invariant": invariant, "event": asdict(event), **details})

    for item in materialized:
        if item.event == "terminal":
            terminal.add(item.execution)
            if item.reservations != 0 or item.pending_urls != 0:
                violate(
                    "terminal_cleanup",
                    item,
                    observedReservations=item.reservations,
                    observedPendingUrls=item.pending_urls,
                )
            continue
        if item.event not in _WORK_EVENTS or item.url is None:
            violate("known_event", item)
            continue
        if item.execution in terminal:
            violate("terminal_no_new_work", item)
        key = (item.execution, item.url)
        prior = states.get(key)
        if item.event not in _NEXT.get(prior, set()):
            violate("valid_state_transition", item, priorState=prior, expectedEvents=sorted(_NEXT.get(prior, set())))
        states[key] = _STATE_AFTER[item.event]
        if item.event == "attempt":
            attempts[item.execution] += 1
            if attempts[item.execution] > max_per_execution:
                violate("execution_budget", item, maximum=max_per_execution, observed=attempts[item.execution])
            if sum(attempts.values()) > max_total:
                violate("lifetime_budget", item, maximum=max_total, observed=sum(attempts.values()))
            if item.at is None:
                violate("attempt_has_timestamp", item)
            else:
                if attempt_times:
                    gap = item.at - attempt_times[-1]
                    if gap + timing_tolerance < minimum_origin_interval:
                        violate("origin_interval", item, minimum=minimum_origin_interval, observed=gap)
                attempt_times.append(item.at)
    return {
        "events": len(materialized),
        "attemptsByExecution": dict(sorted(attempts.items())),
        "attemptsTotal": sum(attempts.values()),
        "violations": violations,
        "invariantsSatisfied": not violations,
    }


def _url_lifecycle(execution: str, url: str, at: float) -> list[SafetyEvent]:
    return [
        SafetyEvent("discover", execution, url), SafetyEvent("admit", execution, url),
        SafetyEvent("schedule", execution, url), SafetyEvent("enqueue", execution, url),
        SafetyEvent("dispatch", execution, url), SafetyEvent("attempt", execution, url, at=at),
        SafetyEvent("process", execution, url), SafetyEvent("settle", execution, url),
    ]


def run_safety_ablations() -> dict[str, Any]:
    """Produce deterministic counterexamples for each removed mechanism."""

    full = _url_lifecycle("e1", "https://site.test/a", 0.0)
    full += _url_lifecycle("e1", "https://site.test/b", 0.1)
    full.append(SafetyEvent("terminal", "e1", reservations=0, pending_urls=0))
    no_admission = [event for event in full if event.event != "admit"]
    no_gate = [*_url_lifecycle("e1", "https://site.test/a", 0.0), *_url_lifecycle("e1", "https://site.test/b", 0.001), SafetyEvent("terminal", "e1", reservations=0, pending_urls=0)]
    no_lifetime: list[SafetyEvent] = []
    for number in range(6):
        no_lifetime.extend(_url_lifecycle("e1" if number < 3 else "e2", f"https://site.test/{number}", number * 0.11))
    no_terminal_guard = [*full, SafetyEvent("discover", "e1", "https://site.test/late")]
    no_cleanup = [*full[:-1], SafetyEvent("terminal", "e1", reservations=1, pending_urls=1)]
    cases = {
        "complete": (full, set()),
        "without_durable_admission": (no_admission, {"valid_state_transition"}),
        "without_final_dispatch_gate": (no_gate, {"origin_interval"}),
        "without_lifetime_reservation": (no_lifetime, {"lifetime_budget"}),
        "without_terminal_guard": (no_terminal_guard, {"terminal_no_new_work"}),
        "without_terminal_cleanup": (no_cleanup, {"terminal_cleanup"}),
    }
    results: dict[str, Any] = {}
    for name, (trace, expected) in cases.items():
        evaluated = evaluate_trace(trace, max_per_execution=10, max_total=5, minimum_origin_interval=0.1)
        observed = {row["invariant"] for row in evaluated["violations"]}
        results[name] = {**evaluated, "expectedCausalViolations": sorted(expected), "causalMatch": expected == observed}
    return {"status": "completed", "method": "executable-deterministic-state-trace-ablation", "cases": results, "allCausalChecksPassed": all(case["causalMatch"] for case in results.values())}
