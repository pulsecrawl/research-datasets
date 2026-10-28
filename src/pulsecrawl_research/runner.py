"""Experiment orchestration."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .adapters import REPO_ROOT, adapters
from .datalake import (
    TemporalWorkload,
    run_parquet_benchmark,
    run_runtime_equivalence,
    run_snapshot_publication_ablation,
    run_snapshot_stress,
    run_compaction_failure_matrix,
    run_local_hosted_parity,
    run_scale_matrix,
    run_temporal_query_benchmark,
    run_workspace_publication,
)
from .environment import capture
from .formal_model import run_safety_ablations
from .governed_comparison import run_governed_pipeline_comparison
from .live_websites import run_live_study
from .metrics import invariant_violations, request_metrics
from .models import Scenario
from .real_site_comparison import run_real_site_comparison
from .registry import resolve_experiment
from .safety import (
    run_concurrency_redelivery_stress,
    run_crash_recovery,
    run_operation_cost_matrix,
    run_queue_ablation,
    run_shared_origin,
)
from .store import RunStore
from .templates import run_template_benchmark
from .template_maintenance import (
    audit_external_corpus,
    run_ambiguity_diagnostics,
    run_change_diffusion,
    run_code_volume,
)
from .webbench import PROFILES, WebBenchConfig, WebBenchServer


def _replace_base_url(value: Any, base_url: str) -> Any:
    if isinstance(value, str):
        return value.replace("{baseUrl}", base_url)
    if isinstance(value, list):
        return [_replace_base_url(item, base_url) for item in value]
    if isinstance(value, dict):
        return {key: _replace_base_url(item, base_url) for key, item in value.items()}
    return value


def _run_crawl(experiment: dict[str, Any], store: RunStore) -> dict[str, Any]:
    web = experiment.get("webbench") or {}
    profile = str(web.get("profile", "smoke"))
    config = WebBenchConfig(
        items_per_site=int(web.get("itemsPerSite", PROFILES[profile])),
        sites_per_vertical=int(web.get("sitesPerVertical", 2)),
        seed=int(experiment.get("seed", 4703)),
        epoch=int(web.get("epoch", 1)),
        crawl_delay_seconds=float(web.get("crawlDelaySeconds", 0)),
        include_fault_links=bool(web.get("faultLinks", False)),
    )
    selected = experiment.get("systems") or ["pulsecrawl"]
    repetitions = int(experiment.get("repetitions", 1))
    results: list[dict[str, Any]] = []
    with WebBenchServer(config) as server:
        raw_scenario = _replace_base_url(copy.deepcopy(experiment["scenario"]), server.base_url)
        scenario = Scenario.from_dict(raw_scenario)
        experiment_id = str(experiment["id"])
        if experiment_id == "S02":
            recovery = run_crash_recovery(scenario, store.path / "artifacts" / "recovery")
            recovery["requestTrace"] = request_metrics(server.state.trace())
            store.write("observations.json", recovery)
            return {"kind": "crawl", "results": recovery}
        if experiment_id in {"S03", "S09"}:
            shared = run_shared_origin(
                scenario, store.path / "artifacts" / "shared-origin", server.state
            )
            store.write("observations.json", shared)
            return {"kind": "crawl", "results": shared}
        if experiment_id == "S05":
            queue = run_queue_ablation(scenario)
            store.write("observations.json", queue)
            return {"kind": "crawl", "results": queue}
        if experiment_id == "S06":
            ablation = run_safety_ablations()
            store.write("observations.json", ablation)
            return {"kind": "crawl", "results": ablation}
        if experiment_id == "S07":
            stress = run_concurrency_redelivery_stress(
                scenario, repetitions=int(experiment.get("repetitions", 30))
            )
            store.write("observations.json", stress)
            return {"kind": "crawl", "results": stress}
        if experiment_id == "S08":
            operations = run_operation_cost_matrix(
                scenario, repetitions=int(experiment.get("repetitions", 30))
            )
            store.write("observations.json", operations)
            return {"kind": "crawl", "results": operations}
        for repetition in range(repetitions):
            for system_entry in selected:
                if isinstance(system_entry, str):
                    system_id, profiles = system_entry, ["default"]
                else:
                    system_id = str(system_entry["id"])
                    profiles = list(system_entry.get("profiles") or ["default"])
                adapter = adapters().get(system_id)
                if adapter is None:
                    raise ValueError(f"unknown system adapter: {system_id}")
                for profile_name in profiles:
                    server.state.reset()
                    result = adapter.run(scenario, str(profile_name))
                    trace = server.state.trace()
                    observed = request_metrics(trace)
                    observed["invariantViolations"] = invariant_violations(
                        observed, scenario.expected
                    )
                    result.observations = observed
                    payload = result.to_dict()
                    payload["repetition"] = repetition
                    results.append(payload)
    store.write("observations.json", results)
    return {"kind": "crawl", "results": results}


def _run_templates(experiment: dict[str, Any], store: RunStore) -> dict[str, Any]:
    parameters = experiment.get("parameters") or {}
    experiment_id = str(experiment["id"])
    if experiment_id == "T05":
        result = run_code_volume(
            store.path / "artifacts" / "integrations",
            sites=int(parameters.get("sites", 20)),
            items_per_site=int(parameters.get("itemsPerSite", 10)),
        )
        store.write("template-metrics.json", result)
        return {"kind": "templates", "results": result}
    if experiment_id == "T06":
        result = run_change_diffusion(
            store.path / "artifacts" / "change-diffusion",
            sites=int(parameters.get("sites", 20)),
            changed_sites=int(parameters.get("changedSites", 5)),
        )
        store.write("template-metrics.json", result)
        return {"kind": "templates", "results": result}
    if experiment_id == "T07":
        result = run_ambiguity_diagnostics(
            sites=int(parameters.get("sites", 20)),
            items_per_site=int(parameters.get("itemsPerSite", 10)),
        )
        store.write("template-metrics.json", result)
        return {"kind": "templates", "results": result}
    if experiment_id == "T08":
        result = audit_external_corpus(REPO_ROOT / "research" / str(parameters["manifest"]))
        store.write("template-metrics.json", result)
        return {"kind": "templates", "results": result}
    if experiment_id in {"T09", "T10"}:
        result = run_real_site_comparison(
            REPO_ROOT / "research" / str(parameters["catalog"]),
            store.path / "artifacts" / "real-site-integrations",
            documents_per_site=int(parameters.get("documentsPerSite", 5)),
            drift_cases=list(parameters.get("driftCases") or []),
        )
        store.write("template-metrics.json", result)
        return {"kind": "templates", "results": result}
    modes = {"T01": "scoping", "T02": "fallback", "T03": "drift", "T04": "corpus"}
    corpus = parameters.get("corpus")
    result = run_template_benchmark(
        sites_per_vertical=int(parameters.get("sitesPerVertical", 5)),
        items_per_site=int(parameters.get("itemsPerSite", 20)),
        seed=int(experiment.get("seed", 4703)),
        mode=modes.get(experiment_id, "scoping"),
        mutations=list(parameters.get("mutations") or []),
        corpus_path=(REPO_ROOT / "research" / str(corpus)) if corpus else None,
    )
    store.write("template-metrics.json", result)
    return {"kind": "templates", "results": result}


def _run_datalake(experiment: dict[str, Any], store: RunStore) -> dict[str, Any]:
    parameters = experiment.get("parameters") or {}
    experiment_id = str(experiment["id"])
    artifact_root = store.path / "artifacts" / "datalake"
    if experiment_id == "D06":
        result = run_scale_matrix(artifact_root, list(parameters.get("cases") or []))
        store.write("datalake-metrics.json", result)
        return {"kind": "datalake", "results": result}
    if experiment_id == "D07":
        result = run_temporal_query_benchmark(
            artifact_root,
            query_repetitions=int(parameters.get("queryRepetitions", 30)),
        )
        store.write("datalake-metrics.json", result)
        return {"kind": "datalake", "results": result}
    if experiment_id == "D08":
        result = run_compaction_failure_matrix(
            artifact_root,
            repetitions=int(parameters.get("repetitions", 30)),
        )
        store.write("datalake-metrics.json", result)
        return {"kind": "datalake", "results": result}
    if experiment_id == "D09":
        hosted = parameters.get("hostedManifest")
        result = run_local_hosted_parity(
            artifact_root,
            hosted_manifest=(REPO_ROOT / str(hosted)) if hosted else None,
        )
        store.write("datalake-metrics.json", result)
        return {"kind": "datalake", "results": result}
    if experiment_id == "D10":
        body_bytes = parameters.get("bodyBytes") or {}
        result = run_governed_pipeline_comparison(
            artifact_root,
            total_rows=int(parameters.get("totalRows", 1_000_000)),
            executions=int(parameters.get("executions", 100)),
            new_fraction=float(parameters.get("newFraction", 0.01)),
            query_repetitions=int(parameters.get("queryRepetitions", 10)),
            failure_repetitions=int(parameters.get("failureRepetitions", 30)),
            simulation_hours=int(parameters.get("simulationHours", 8_760)),
            minimum_body_bytes=int(body_bytes.get("minimum", 128)),
            maximum_body_bytes=int(body_bytes.get("maximum", 2_048)),
        )
        store.write("datalake-metrics.json", result)
        return {"kind": "datalake", "results": result}
    if experiment_id == "D11":
        result = run_workspace_publication(
            artifact_root,
            executions=int(parameters.get("executions", 5)),
            urls_per_execution=int(parameters.get("urlsPerExecution", 20)),
        )
        store.write("datalake-metrics.json", result)
        return {"kind": "datalake", "results": result}
    workload = TemporalWorkload(
        executions=int(parameters.get("executions", 10)),
        rows_per_execution=int(parameters.get("rowsPerExecution", 1_000)),
        new_fraction=float(parameters.get("newFraction", 0.10)),
        seed=int(experiment.get("seed", 4703)),
    )
    result = run_parquet_benchmark(workload, output_root=artifact_root)
    if result.get("status") == "completed" and experiment_id == "D03":
        result["snapshotStress"] = run_snapshot_stress(
            artifact_root,
            readers=int(parameters.get("concurrentReaders", 8)),
        )
    if result.get("status") == "completed" and experiment_id == "D04":
        result["runtimeEquivalence"] = run_runtime_equivalence(workload, artifact_root)
    if result.get("status") == "completed" and experiment_id == "D05":
        result["publicationAblation"] = run_snapshot_publication_ablation(
            artifact_root / "publication-ablation",
            readers=int(parameters.get("concurrentReaders", 4)),
            publications=int(parameters.get("publications", 30)),
        )
    store.write("datalake-metrics.json", result)
    return {"kind": "datalake", "results": result}


def _run_live(
    experiment: dict[str, Any], store: RunStore, *, phase: str | None = None
) -> dict[str, Any]:
    result = run_live_study(
        experiment,
        store.path / "artifacts" / "live-study",
        phase=phase,
        progress_path=store.path / "live-progress.json",
    )
    store.write("live-metrics.json", result)
    return {"kind": "live", "results": result}


def run(
    identifier: str,
    *,
    output_root: Path | None = None,
    phase: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    experiment = resolve_experiment(identifier)
    store = RunStore(str(experiment["id"]), output_root)
    store.write("experiment.json", {key: value for key, value in experiment.items() if key != "_path"})
    store.write("environment.json", capture(REPO_ROOT))
    kind = experiment.get("kind")
    if kind == "crawl":
        result = _run_crawl(experiment, store)
    elif kind == "templates":
        result = _run_templates(experiment, store)
    elif kind == "datalake":
        result = _run_datalake(experiment, store)
    elif kind == "live":
        result = _run_live(experiment, store, phase=phase)
    else:
        raise ValueError(f"unsupported experiment kind: {kind}")
    store.write("summary.json", result)
    store.finalize()
    return store.path, result
