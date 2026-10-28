"""Statistical analysis and manuscript assets from immutable run artifacts."""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .metrics import summarize
from .registry import RESEARCH_ROOT


def _reader_system_name(value: object) -> object:
    """Return stable reader-facing names for historical adapter identifiers."""

    if value == "firecrawl-self-hosted":
        return "firecrawl-local"
    return value


def _cohens_d(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(right) < 2:
        return None
    variance = ((len(left) - 1) * statistics.variance(left) + (len(right) - 1) * statistics.variance(right)) / (len(left) + len(right) - 2)
    if variance == 0:
        return 0.0 if statistics.fmean(left) == statistics.fmean(right) else None
    return (statistics.fmean(left) - statistics.fmean(right)) / math.sqrt(variance)


def _cliffs_delta(left: list[float], right: list[float]) -> float | None:
    if not left or not right:
        return None
    greater = sum(a > b for a in left for b in right)
    lower = sum(a < b for a in left for b in right)
    return (greater - lower) / (len(left) * len(right))


def _crawl_rows(experiment: str, run_id: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        observed = result.get("observations") or {}
        rows.append({
            "experiment": experiment, "runId": run_id,
            "system": _reader_system_name(result.get("system")),
            "profile": result.get("profile", "default"), "status": result.get("status"),
            "durationSeconds": result.get("duration_seconds"),
            "httpRequests": observed.get("httpRequestsObserved"),
            "duplicateRequests": observed.get("duplicateRequestsObserved"),
            "minimumInterRequestSeconds": observed.get("minimumInterRequestSeconds"),
            "invariantViolations": len(observed.get("invariantViolations") or []),
            "robotsBlockedRequests": int((observed.get("requestPathCounts") or {}).get("/blocked/canary", 0)),
        })
    return rows


def collect_measurements(run_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(run_root.glob("*/summary.json")):
        experiment_path = summary_path.parent / "experiment.json"
        if not experiment_path.exists():
            continue
        experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
        experiment_id = str(experiment["id"])
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        results = summary.get("results")
        if summary.get("kind") == "crawl" and isinstance(results, list):
            rows.extend(_crawl_rows(experiment_id, summary_path.parent.name, results))
        elif summary.get("kind") == "crawl" and isinstance(results, dict):
            if experiment_id == "S02":
                for case in results.get("cases", []):
                    rows.append({
                        "experiment": experiment_id,
                        "runId": summary_path.parent.name,
                        "system": str(case.get("boundary") or "recovery"),
                        "profile": "recovery",
                        "status": case.get("status"),
                        "recoveryFailures": int(case.get("status") != "succeeded"),
                        "pendingUrlResiduals": int(
                            case.get("pendingUrlsRemaining", case.get("frontierRemaining", 0))
                        ),
                        "completedHttpRequests": case.get("completedHttpRequests"),
                        "duplicateCompletedHttpRequests": case.get(
                            "duplicateCompletedHttpRequests"
                        ),
                    })
                rows.append({
                    "experiment": experiment_id,
                    "runId": summary_path.parent.name,
                    "system": "lifetime-budget",
                    "profile": "recovery",
                    "status": results.get("status"),
                    "lifetimeInvariant": int(
                        bool((results.get("lifetimeBudget") or {}).get("invariantSatisfied"))
                    ),
                    "recoveryFailures": int(
                        not bool((results.get("lifetimeBudget") or {}).get("invariantSatisfied"))
                    ),
                })
            elif experiment_id in {"S03", "S09"}:
                allowance = (
                    results.get("configuredAllowancePhase")
                    or results.get("organizationPhase")
                    or {}
                )
                ceiling = (
                    results.get("originCeilingPhase")
                    or results.get("platformPhase")
                    or {}
                )
                groups = allowance.get("perGroup") or allowance.get("perOrganization") or {}
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "pulsecrawl",
                    "profile": (
                        "arrival-margin-remediation"
                        if experiment_id == "S09"
                        else "shared-origin"
                    ),
                    "status": results.get("status"),
                    "invariantViolations": int(not results.get("allInvariantsSatisfied")),
                    "timingAuthority": results.get("timingAuthority", "legacy-arrival"),
                    "configuredAllowanceMinimumAuthorizationGap": min((value.get("minimumGapSeconds") for value in groups.values() if value.get("minimumGapSeconds") is not None), default=None),
                    "originCeilingMinimumAuthorizationGap": (ceiling.get("global") or {}).get("minimumGapSeconds"),
                })
            elif experiment_id == "S05":
                for strategy, values in (results.get("strategies") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": strategy, "profile": "queue-ablation", "status": results.get("status"),
                        "storageCalls": values.get("storageCalls"), "deferrals": values.get("deferrals"),
                        "gateCallsPerUrl": values.get("gateCallsPerUrl"),
                    })
            elif experiment_id == "S06":
                for case, values in (results.get("cases") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": case, "profile": "state-ablation", "status": results.get("status"),
                        "invariantViolations": len(values.get("violations") or []),
                        "causalMatch": int(bool(values.get("causalMatch"))),
                    })
            elif experiment_id == "S07":
                for stress in results.get("runs") or []:
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": "pulsecrawl", "profile": "redelivery-cache-loss", "status": results.get("status"),
                        "invariantViolations": sum(int(stress.get(field, 0)) for field in (
                            "budgetViolations", "originIntervalViolations", "postTerminalHttpAttempts",
                            "unsettledReservations", "duplicateHttpAttempts",
                        )),
                        "httpRequests": stress.get("httpAttempts"),
                        "duplicateDeliveries": stress.get("duplicateDeliveries"),
                        "cacheLosses": stress.get("cacheLosses"),
                    })
            elif experiment_id == "S08":
                for regime, values in (results.get("regimes") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": regime, "profile": "operation-model", "status": results.get("status"),
                        "storageCalls": values.get("totalExternalOperations"),
                        "durableReads": values.get("durableReadsPerRepetition"),
                        "queueOperations": values.get("queueOperationsPerRepetition"),
                        "visibilityUpdates": values.get("visibilityUpdatesPerRepetition"),
                        "operationReduction": values.get("reductionVersusDurableOnly"),
                    })
        elif summary.get("kind") == "templates" and isinstance(results, dict):
            for strategy, values in (results.get("strategies") or {}).items():
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": strategy, "profile": "strategy", "status": results.get("status"),
                    "fieldAccuracy": values.get("fieldAccuracy"),
                    "recordCoverage": values.get("recordCoverage"),
                    "contaminationRate": values.get("contaminationRate"),
                })
            if "fieldF1" in results:
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "pulsecrawl-template-stack", "profile": "corpus",
                    "status": results.get("status"), "fieldAccuracy": results.get("fieldAccuracy"),
                    "fieldF1": results.get("fieldF1"), "recordCoverage": results.get("recordsMatched", 0) / max(results.get("documents", 1), 1),
                })
            if experiment_id == "T02":
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "scoped-plus-system-fallback", "profile": "fallback",
                    "status": results.get("status"), "fallbackRate": results.get("fallbackRate"),
                    "needsTemplateRate": results.get("needsTemplateRate"),
                    "recordCoverage": results.get("completeRecords", 0) / max(results.get("pages", 1), 1),
                })
            if experiment_id == "T03":
                for mutation, values in (results.get("mutations") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": mutation, "profile": "drift", "status": results.get("status"),
                        "recordAccuracy": values.get("recordAccuracy"),
                        "recordCoverage": values.get("recordCoverage"),
                    })
            if experiment_id == "T05":
                for system, values in (results.get("systems") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": system, "profile": "integration-surface", "status": results.get("status"),
                        "physicalLoc": values.get("physicalLoc"), "authoredBytes": values.get("bytes"),
                        "recordAccuracy": values.get("oracleAccuracy"),
                        "routeEntries": values.get("routeEntries"),
                    })
            if experiment_id == "T06":
                for system, values in (results.get("systems") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": system, "profile": "change-diffusion", "status": results.get("status"),
                        "changedFiles": values.get("changedFiles"), "changedLines": values.get("changedLines"),
                        "diffHunks": values.get("diffHunks"), "recordAccuracy": values.get("postChangeOracleAccuracy"),
                    })
            if experiment_id == "T07":
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "first-entity", "profile": "ambiguity", "status": results.get("status"),
                    "recordAccuracy": results.get("firstEntityAccuracy"), "ambiguousPages": results.get("ambiguousPages"),
                })
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "canonical-completeness", "profile": "ambiguity", "status": results.get("status"),
                    "recordAccuracy": results.get("canonicalCompletenessAccuracy"), "ambiguousPages": results.get("ambiguousPages"),
                })
            if experiment_id == "T08":
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "permission-gate", "profile": "external", "status": results.get("status"),
                    "externalDocuments": results.get("documents"),
                })
            if experiment_id in {"T09", "T10"}:
                leak = results.get("literalLeakAblation") or {}
                for system, values in (results.get("systems") or {}).items():
                    drift = values.get("drift") or {}
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": system, "profile": ("fully-synthetic-scoped-html"
                            if results.get("corpusClassification") == "fully-synthetic-scoped-html"
                            else "real-site-derived"), "status": results.get("status"),
                        "fieldPrecision": values.get("fieldPrecision"),
                        "fieldRecall": values.get("fieldRecall"), "fieldF1": values.get("fieldF1"),
                        "recordCoverage": values.get("records", 0) / max(values.get("documents", 1), 1),
                        "contaminationRate": leak.get("scopedContaminationRate"),
                        "unscopedContaminationRate": leak.get("unscopedContaminationRate"),
                        "physicalLoc": values.get("authoredLoc"),
                        "authoredBytes": values.get("authoredBytes"),
                        "maintainedComponents": values.get("maintainedComponents"),
                        "changedFiles": values.get("changedFiles"),
                        "changedLines": values.get("changedLines"),
                        "negativePageFalsePositiveRate": (
                            (drift.get("negative_page") or {}).get("falsePositiveRate")
                            if (drift.get("negative_page") or {}).get("falsePositiveRate") is not None
                            else (
                                (drift.get("negative_page") or {}).get("records", 0)
                                / max((drift.get("negative_page") or {}).get("documents", 1), 1)
                            )
                        ),
                        "ambiguityAccuracy": (drift.get("multiple_entities") or {}).get("fieldAccuracy"),
                        "canonicalChangeAccuracy": (drift.get("canonical_change") or {}).get("fieldAccuracy"),
                    })
        elif summary.get("kind") == "datalake" and isinstance(results, dict):
            if experiment_id == "D06":
                for case in results.get("cases") or []:
                    timing = list(case.get("allPayloadScanSeconds") or [])
                    for index, seconds in enumerate(timing or [None]):
                        rows.append({
                            "experiment": experiment_id, "runId": summary_path.parent.name,
                            "system": "pulsecrawl-parquet", "profile": f'{case.get("totalRows")}-rows', "status": case.get("status"),
                            "appendAllRows": case.get("appendAllRows"), "newOnlyRows": case.get("newOnlyRows"),
                            "deltaFiles": case.get("deltaFiles"), "compactFiles": case.get("dailyCompactFiles"),
                            "appendAllBytes": case.get("appendAllBytes"), "compactBytes": case.get("compactBytes"),
                            "payloadScanSeconds": seconds,
                            "compactPayloadScanSeconds": (case.get("compactPayloadScanSeconds") or [None])[min(index, len(case.get("compactPayloadScanSeconds") or [None]) - 1)],
                            "snapshotViolations": int(not case.get("snapshotConsistent")),
                        })
                continue
            if experiment_id == "D07":
                scale = results.get("scale") or {}
                timings = list(scale.get("allPayloadScanSeconds") or [])
                for index, seconds in enumerate(timings):
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": "pulsecrawl-parquet", "profile": "temporal-query", "status": results.get("status"),
                        "payloadScanSeconds": seconds,
                        "hourlyPayloadScanSeconds": (scale.get("lastHourPayloadScanSeconds") or [None])[index],
                        "newOnlyPayloadScanSeconds": (scale.get("newOnlyPayloadScanSeconds") or [None])[index],
                        "compactPayloadScanSeconds": (scale.get("compactPayloadScanSeconds") or [None])[index],
                        "appendAllRows": scale.get("appendAllRows"), "newOnlyRows": scale.get("newOnlyRows"),
                        "snapshotViolations": int(not results.get("allCountsCorrect")),
                    })
                continue
            if experiment_id == "D08":
                for stage, values in (results.get("byStage") or {}).items():
                    rows.append({
                        "experiment": experiment_id, "runId": summary_path.parent.name,
                        "system": "atomic-manifest", "profile": stage, "status": results.get("status"),
                        "snapshotViolations": values.get("violations"), "snapshotObservations": values.get("observations"),
                    })
                continue
            if experiment_id == "D09":
                local = results.get("local") or {}
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "local", "profile": "parity", "status": local.get("status"),
                    "appendAllRows": local.get("appendAllRows"), "newOnlyRows": local.get("newOnlyRows"),
                    "snapshotViolations": int(not (results.get("localEquivalence") or {}).get("equivalent")),
                })
                rows.append({
                    "experiment": experiment_id, "runId": summary_path.parent.name,
                    "system": "hosted", "profile": "parity", "status": (results.get("hosted") or {}).get("status"),
                })
                continue
            if experiment_id == "D10":
                common = {
                    "experiment": experiment_id,
                    "runId": summary_path.parent.name,
                    "status": results.get("status"),
                }
                for system, values in (results.get("systems") or {}).items():
                    rows.append({
                        **common, "system": system, "profile": "integration-burden",
                        "userAuthoredLoc": values.get("userAuthoredLoc"),
                        "authoredBytes": values.get("userAuthoredBytes"),
                        "maintainedComponents": values.get("maintainedComponents"),
                    })
                    native_count = values.get("nativeCountSeconds") or []
                    native_payload = values.get("nativePayloadScanSeconds") or []
                    for index, seconds in enumerate(native_payload):
                        rows.append({
                            **common, "system": system, "profile": "native-output",
                            "countQuerySeconds": native_count[index],
                            "payloadScanSeconds": seconds,
                            "activeFiles": values.get("nativeFiles"),
                            "storageBytes": values.get("nativeBytes"),
                        })
                    governed_count = values.get("governanceEquivalentCountSeconds") or []
                    governed_payload = values.get("governanceEquivalentPayloadScanSeconds") or []
                    for index, seconds in enumerate(governed_payload):
                        rows.append({
                            **common, "system": system, "profile": "governance-equivalent",
                            "countQuerySeconds": governed_count[index],
                            "payloadScanSeconds": seconds,
                            "activeFiles": values.get("governanceEquivalentFiles"),
                            "storageBytes": values.get("governanceEquivalentBytes"),
                            "snapshotViolations": int(not results.get("allGovernedSnapshotsValid")),
                        })
                rows.append({
                    **common, "system": "pulsecrawl", "profile": "long-term",
                    "appendAllRows": results.get("totalRows"),
                    "newOnlyRows": results.get("newOnlyRows"),
                    "activeFiles": (results.get("longTerm") or {}).get("governedActiveFiles"),
                    "nativeActiveFiles": (results.get("longTerm") or {}).get("nativeActiveFiles"),
                    "activeFileReduction": (results.get("longTerm") or {}).get("activeFileReduction"),
                    "replayDuplicates": (results.get("longTerm") or {}).get("duplicateCommittedExecutions"),
                    "snapshotViolations": (results.get("failureMatrix") or {}).get("violations"),
                    "semanticEquivalent": int(bool(results.get("semanticChecksumEquivalent"))),
                })
                continue
            if experiment_id == "D11":
                for mode, values in (results.get("modes") or {}).items():
                    rows.append({
                        "experiment": experiment_id,
                        "runId": summary_path.parent.name,
                        "system": mode,
                        "profile": "public-local-workspace",
                        "status": results.get("status"),
                        "appendAllRows": (
                            values.get("rowsBeforeCompaction")
                            if mode == "append_all" else None
                        ),
                        "newOnlyRows": (
                            values.get("rowsBeforeCompaction")
                            if mode == "new_urls_only" else None
                        ),
                        "storageBytes": values.get("bytesBeforeCompaction"),
                        "activeFiles": values.get("filesBeforeCompaction"),
                        "replayDuplicates": int(not values.get("replayIdempotent")),
                        "snapshotViolations": int(
                            not values.get("compactionPreservedRows")
                        ),
                    })
                continue
            row = {
                "experiment": experiment_id, "runId": summary_path.parent.name,
                "system": "pulsecrawl-parquet", "profile": "default", "status": results.get("status"),
                "allQuerySeconds": results.get("allQuerySeconds"),
                "hourlyQuerySeconds": results.get("hourlyQuerySeconds"),
                "compactQuerySeconds": results.get("compactQuerySeconds"),
                "appendAllRows": results.get("appendAllRows"), "newOnlyRows": results.get("newOnlyRows"),
                "snapshotViolations": (results.get("snapshotStress") or {}).get("violations"),
            }
            publication = results.get("publicationAblation") or {}
            if publication:
                row["snapshotViolations"] = (publication.get("atomicPublication") or {}).get("violations")
                row["unsafeSnapshotViolations"] = (publication.get("inPlacePublication") or {}).get("violations")
            rows.append(row)
    return rows


def _group_statistics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    identity = {"experiment", "runId", "system", "profile", "status"}
    for row in rows:
        if row.get("status") != "completed":
            continue
        for metric, value in row.items():
            if metric not in identity and isinstance(value, (int, float)) and not isinstance(value, bool):
                grouped[(str(row["experiment"]), str(row["system"]), str(row["profile"]), metric)].append(float(value))
    result = []
    for (experiment, system, profile, metric), values in sorted(grouped.items()):
        summary = summarize(values)
        if values and min(values) >= 0 and "confidence95Low" in summary:
            summary["confidence95Low"] = max(0.0, float(summary["confidence95Low"]))
        result.append({"experiment": experiment, "system": system, "profile": profile, "metric": metric, **summary})
    return result


def _effects(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row.get("status") != "completed":
            continue
        for metric in ("durationSeconds", "httpRequests", "invariantViolations"):
            value = row.get(metric)
            if isinstance(value, (int, float)):
                values[(str(row["experiment"]), str(row["system"]), str(row["profile"]), metric)].append(float(value))
    effects = []
    for (experiment, system, profile, metric), right in sorted(values.items()):
        if system == "pulsecrawl":
            continue
        left = values.get((experiment, "pulsecrawl", "default", metric), [])
        if left and right:
            effects.append({
                "experiment": experiment, "metric": metric,
                "left": "pulsecrawl:default", "right": f"{system}:{profile}",
                "cohensD": _cohens_d(left, right),
                "cliffsDelta": _cliffs_delta(left, right),
                "leftN": len(left), "rightN": len(right),
            })
    return effects


def _svg_bars(path: Path, title: str, labels: list[str], values: list[float]) -> None:
    width, height, margin = 760, 360, 55
    maximum = max(values or [1]) or 1
    step = (width - 2 * margin) / max(len(values), 1)
    bars = []
    for index, (label, value) in enumerate(zip(labels, values)):
        x = margin + index * step + step * 0.15
        bar_height = (height - 2 * margin) * value / maximum
        y = height - margin - bar_height
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{step * .7:.1f}" height="{bar_height:.1f}" fill="#315b7d"/><text x="{x + step * .35:.1f}" y="{height - 30}" text-anchor="middle" font-size="12">{label}</text><text x="{x + step * .35:.1f}" y="{max(y - 6, 25):.1f}" text-anchor="middle" font-size="12">{value:g}</text>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img"><title>{title}</title><text x="{width/2}" y="20" text-anchor="middle" font-size="16">{title}</text>{"".join(bars)}</svg>\n', encoding="utf-8")


def _latex_text(value: object) -> str:
    """Escape evidence labels before placing them in generated TeX."""

    text = str(value)
    for source, target in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ):
        text = text.replace(source, target)
    return text


def _format_metric(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "--"
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}"
    if number != 0 and (abs(number) < 0.001 or abs(number) >= 1_000_000):
        return f"{number:.3e}"
    return f"{number:.4g}"


def _metric_mean(rows: list[dict[str, Any]], name: str) -> float | None:
    values = [
        float(row[name])
        for row in rows
        if isinstance(row.get(name), (int, float)) and not isinstance(row.get(name), bool)
    ]
    return statistics.fmean(values) if values else None


def _write_manuscript_tables(output: Path, rows: list[dict[str, Any]]) -> None:
    """Write compact result tables; ``tables.tex`` remains the full metric surface."""

    def selected(
        experiment: str,
        system: str | None = None,
        profile: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if row.get("experiment") == experiment
            and (system is None or row.get("system") == system)
            and (profile is None or row.get("profile") == profile)
        ]

    def table(
        caption: str,
        label: str,
        heading: str,
        specs: tuple[tuple[str, str, str, str | None, str | None], ...],
    ) -> list[str]:
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            f"\\caption{{{_latex_text(caption)}}}",
            f"\\label{{{label}}}",
            r"\begin{tabularx}{\textwidth}{L{0.14\textwidth}Yr}",
            r"\toprule",
            f"Experiment & {_latex_text(heading)} & Mean \\\\",
            r"\midrule",
        ]
        for experiment, metric, description, system, profile in specs:
            lines.append(
                f"{experiment} & {_latex_text(description)} & "
                f"{_format_metric(_metric_mean(selected(experiment, system, profile), metric))} \\\\"
            )
        lines.extend([r"\bottomrule", r"\end{tabularx}", r"\end{table}", ""])
        return lines

    tex = ["% Generated from immutable run summaries; do not edit."]
    tex.extend(table(
        "Selected safety and recovery outcomes generated by the analysis pipeline.",
        "tab:generated-safety",
        "Registered observation",
        (
            ("S02", "duplicateCompletedHttpRequests", "after-HTTP completed requests repeated", "after_http", "recovery"),
            ("S03", "invariantViolations", "authorization-interval violations", "pulsecrawl", "shared-origin"),
            ("S07", "invariantViolations", "redelivery and cache-loss violations", "pulsecrawl", "redelivery-cache-loss"),
            ("S08", "operationReduction", "external-operation reduction with cache and crawlBy", "volatile-cache-crawlby", "operation-model"),
        ),
    ))
    tex.extend(table(
        "Selected extraction outcomes generated from registered corpora.",
        "tab:generated-templates",
        "Metric",
        (
            ("T01", "fieldAccuracy", "generic field accuracy", "generic", "strategy"),
            ("T01", "fieldAccuracy", "scoped field accuracy", "scoped", "strategy"),
            ("T01", "contaminationRate", "unscoped literal contamination", "unscoped", "strategy"),
            ("T04", "fieldF1", "field F1 on the exact controlled corpus", "pulsecrawl-template-stack", "corpus"),
            ("T09", "negativePageFalsePositiveRate", "PulseCrawl negative-page false-positive rate", "pulsecrawl", "fully-synthetic-scoped-html"),
            ("T10", "fieldF1", "field F1 on the 1,000-page controlled corpus", "pulsecrawl", "fully-synthetic-scoped-html"),
        ),
    ))
    tex.extend(table(
        "Selected temporal data outcomes generated by the analysis pipeline.",
        "tab:generated-datalake",
        "Metric",
        (
            ("D01", "appendAllRows", "append-all rows", "pulsecrawl-parquet", "default"),
            ("D01", "newOnlyRows", "new-URL-only rows", "pulsecrawl-parquet", "default"),
            ("D06", "payloadScanSeconds", "payload scan seconds", "pulsecrawl-parquet", "10000000-rows"),
            ("D08", "snapshotViolations", "snapshot violations", "atomic-manifest", None),
            ("D10", "activeFileReduction", "one-year active-file reduction", "pulsecrawl", "long-term"),
            ("D11", "newOnlyRows", "new-URL-only rows through the public local workspace", "new_urls_only", "public-local-workspace"),
        ),
    ))
    (output / "manuscript-results.tex").write_text("\n".join(tex), encoding="utf-8")


def analyze_runs(
    run_root: Path, output: Path | None = None, *, phase: str = "pilot"
) -> dict[str, Any]:
    if phase not in {"pilot", "confirmatory", "remediation"}:
        raise ValueError("phase must be pilot, confirmatory, or remediation")
    output = output or RESEARCH_ROOT / "results/published/analysis"
    output.mkdir(parents=True, exist_ok=True)
    rows = collect_measurements(run_root)
    statistics_rows = _group_statistics(rows)
    effects = _effects(rows)
    fields = sorted({key for row in rows for key in row})
    with (output / "measurements.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    stat_fields = sorted({key for row in statistics_rows for key in row})
    with (output / "statistics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=stat_fields); writer.writeheader(); writer.writerows(statistics_rows)
    payload = {"schemaVersion": 1, "phase": phase, "measurements": len(rows), "groups": statistics_rows, "effects": effects}
    (output / "analysis.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    safety = [row for row in statistics_rows if row["metric"] == "invariantViolations"]
    _svg_bars(output / "figures/safety-violations.svg", "Observed safety violations", [f'{r["experiment"]}:{r["system"]}' for r in safety], [r["mean"] for r in safety])
    markdown = [
        "# Statistical analysis", "", f"Phase: **{phase}**", f"Measurements: {len(rows)}",
        f"Metric groups: {len(statistics_rows)}", "",
        "Pilot, confirmatory, and remediation runs must not be pooled. Inspect `experiment.json` and the release manifest before publication.", "",
        "## Crawl safety", "",
        "| Experiment | System | Profile | Runs | Zero-violation runs | Mean HTTP requests | Mean duration (s) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    crawl_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    unavailable_crawl = [
        row for row in rows
        if row.get("httpRequests") is not None and row.get("status") != "completed"
    ]
    for row in rows:
        if row.get("httpRequests") is not None and row.get("status") == "completed":
            crawl_groups[(str(row["experiment"]), str(row["system"]), str(row["profile"]))].append(row)
    for (experiment, system, profile), group in sorted(crawl_groups.items()):
        requests = [float(row["httpRequests"]) for row in group]
        durations = [float(row["durationSeconds"]) for row in group if row.get("durationSeconds") is not None]
        zero = sum(int(row.get("invariantViolations", 0)) == 0 for row in group)
        duration_text = f"{statistics.fmean(durations):.3f}" if durations else ""
        markdown.append(f"| {experiment} | {system} | {profile} | {len(group)} | {zero} | {statistics.fmean(requests):.3f} | {duration_text} |")
    markdown.extend(["", "Safety compliance and performance are reported separately; a faster run that violates a configured invariant is not ranked as superior.", ""])
    if unavailable_crawl:
        unavailable = sorted({
            f'{row["experiment"]}:{row["system"]}:{row["profile"]}'
            for row in unavailable_crawl
        })
        markdown.extend([
            "Unavailable profiles were excluded from compliance and performance totals: "
            + ", ".join(unavailable)
            + ".",
            "",
        ])
    mechanism_rows = [
        row for row in rows
        if row["experiment"] in {"S02", "S03", "S05", "S06", "S07", "S08", "S09"}
    ]
    markdown.extend([
        "## Safety mechanisms", "",
        "| Experiment | Case | Runs | Zero-violation/recovery runs | Causal matches | Mean storage calls | Mean deferrals |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    mechanism_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in mechanism_rows:
        mechanism_groups[(str(row["experiment"]), str(row["system"]))].append(row)
    for (experiment, system), group in sorted(mechanism_groups.items()):
        observed = [
            int(row.get("invariantViolations", row.get("recoveryFailures", 0)))
            for row in group
            if row.get("invariantViolations") is not None or row.get("recoveryFailures") is not None
        ]
        causal = [int(row["causalMatch"]) for row in group if row.get("causalMatch") is not None]
        storage = [float(row["storageCalls"]) for row in group if row.get("storageCalls") is not None]
        deferrals = [float(row["deferrals"]) for row in group if row.get("deferrals") is not None]
        storage_text = f"{statistics.fmean(storage):.6g}" if storage else ""
        deferral_text = f"{statistics.fmean(deferrals):.6g}" if deferrals else ""
        markdown.append(
            f"| {experiment} | {system} | {len(group)} | "
            f"{sum(value == 0 for value in observed) if observed else ''} | "
            f"{sum(causal) if causal else ''} | "
            f"{storage_text} | {deferral_text} |"
        )
    markdown.append("")
    template_rows = [row for row in rows if row["experiment"].startswith("T")]
    markdown.extend(["## Extraction", "", "| Experiment | Strategy/case | Field F1/accuracy | Record coverage | Contamination |", "|---|---|---:|---:|---:|"])
    template_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in template_rows:
        template_groups[(str(row["experiment"]), str(row["system"]))].append(row)
    for (experiment, system), group in sorted(template_groups.items()):
        def average(*names: str) -> str:
            values = [float(row[name]) for row in group for name in names if isinstance(row.get(name), (int, float))]
            return f"{statistics.fmean(values):.6g}" if values else ""
        markdown.append(f"| {experiment} | {system} | {average('fieldF1', 'fieldAccuracy', 'recordAccuracy')} | {average('recordCoverage')} | {average('contaminationRate')} |")
    markdown.extend(["", "## Data lake", "", "| Experiment | Append-all rows | New-only rows | Snapshot violations | Unsafe-publication violations |", "|---|---:|---:|---:|---:|"])
    lake_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in (value for value in rows if value["experiment"].startswith("D")):
        experiment = str(row["experiment"])
        profile = str(row.get("profile") or "") if experiment in {"D06", "D10"} else ""
        lake_groups[(experiment, profile)].append(row)
    for (experiment, profile), group in sorted(lake_groups.items()):
        def lake_average(name: str) -> str:
            values = [float(row[name]) for row in group if isinstance(row.get(name), (int, float))]
            return f"{statistics.fmean(values):.6g}" if values else ""
        label = f"{experiment} ({profile})" if profile else experiment
        markdown.append(f"| {label} | {lake_average('appendAllRows')} | {lake_average('newOnlyRows')} | {lake_average('snapshotViolations')} | {lake_average('unsafeSnapshotViolations')} |")
    markdown.append("")
    (output / "findings.md").write_text("\n".join(markdown), encoding="utf-8")
    latex = ["% Generated; do not edit", "\\begin{tabular}{llllrr}", "Experiment & System & Profile & Metric & $n$ & Mean \\\\ \\hline"]
    for row in statistics_rows:
        latex.append(f'{row["experiment"]} & {row["system"]} & {row["profile"]} & {row["metric"]} & {row["count"]} & {row["mean"]:.6g} \\\\')
    latex.append("\\end{tabular}")
    (output / "tables.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")
    _write_manuscript_tables(output, rows)
    return {"status": "completed", "phase": phase, "measurements": len(rows), "groups": len(statistics_rows), "effects": len(effects), "output": str(output)}
