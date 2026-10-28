"""Bounded live studies executed through the public local package.

Live observations are supporting evidence, separate from controlled hypothesis
tests. Current access decisions and workspace files are retained, but fetched
third-party HTML is never written to the research repository.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from .live_profiles import profile, quality_query, templates_for
from .store import atomic_json

USER_AGENT = "PulseCrawlResearchBot/0.1 (+https://github.com/pulsecrawl/research-datasets)"
MAX_PREFLIGHT_BYTES = 5_000_000


def load_live_manifest(path: Path, *, expected_study: str | None = None) -> dict[str, Any]:
    """Load and validate a live-site configuration without contacting a site."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schemaVersion") not in {1, 2}:
        raise ValueError("live manifest schemaVersion must be 1 or 2")
    study = str(value.get("studyId") or value.get("study") or "")
    schema_profile = str(value.get("schemaProfile") or value.get("study") or "")
    if schema_profile == "news":
        schema_profile = "article"
    elif schema_profile == "commerce":
        schema_profile = "product"
    profile(schema_profile)
    if expected_study is not None and study != expected_study:
        raise ValueError(f"expected {expected_study} manifest, found {study}")
    sites = value.get("sites")
    if not isinstance(sites, list) or not sites:
        raise ValueError("live manifest needs at least one site")
    identifiers: set[str] = set()
    for index, site in enumerate(sites, 1):
        if not isinstance(site, dict):
            raise ValueError(f"live manifest site {index} must be an object")
        required = {"id", "name", "seedUrls", "hosts", "templatePatterns"}
        missing = sorted(required.difference(site))
        if missing:
            raise ValueError(f"live manifest site {index} lacks {', '.join(missing)}")
        identifier = str(site["id"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", identifier):
            raise ValueError(f"invalid live site id: {identifier}")
        if identifier in identifiers:
            raise ValueError(f"duplicate live site id: {identifier}")
        identifiers.add(identifier)
        seeds = site["seedUrls"]
        hosts = {str(host).lower().removeprefix("www.") for host in site["hosts"]}
        if not isinstance(seeds, list) or not seeds or not hosts:
            raise ValueError(f"live site {identifier} needs seeds and hosts")
        seed_groups = [seeds]
        if site.get("qualificationSeedUrls") is not None:
            qualification_seeds = site["qualificationSeedUrls"]
            if not isinstance(qualification_seeds, list) or not qualification_seeds:
                raise ValueError(f"live site {identifier} has invalid qualification seeds")
            seed_groups.append(qualification_seeds)
        for group in seed_groups:
            for seed in group:
                parts = urlsplit(str(seed))
                host = (parts.hostname or "").lower().removeprefix("www.")
                if parts.scheme not in {"http", "https"} or not host:
                    raise ValueError(f"live site {identifier} has an invalid seed URL")
                if host not in hosts:
                    raise ValueError(f"live site {identifier} seed host is outside its scope")
        default_depth = int(profile(schema_profile)["defaultMaxDepth"])
        if int(site.get("maxDepth", value.get("defaultMaxDepth", default_depth))) > 0 and not site.get("discoveryPatterns"):
            raise ValueError(f"live site {identifier} needs discoveryPatterns when maxDepth is greater than zero")
        for pattern in site.get("discoveryPatterns") or ():
            try:
                re.compile(str(pattern))
            except re.error as exc:
                raise ValueError(
                    f"live site {identifier} has an invalid discovery pattern: {exc}"
                ) from exc
    return value


class LiveAccessReviewer:
    """Fail-closed robots and seed-availability checker."""

    def __init__(self, *, timeout_seconds: float = 20, max_bytes: int = MAX_PREFLIGHT_BYTES):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def review(self, site: Mapping[str, Any]) -> dict[str, Any]:
        seed = str(site["seedUrls"][0])
        parts = urlsplit(seed)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots_url = f"{origin}/robots.txt"
        parser = urllib.robotparser.RobotFileParser(robots_url)
        row: dict[str, Any] = {
            "siteId": site["id"], "siteName": site["name"], "seedUrl": seed,
            "robotsUrl": robots_url, "checkedAt": datetime.now(UTC).isoformat(),
            "enabled": False,
        }
        try:
            request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                robots = response.read(self.max_bytes + 1)
                row["robotsHttpStatus"] = int(response.status)
            if len(robots) > self.max_bytes:
                raise ValueError("robots.txt exceeds byte limit")
            parser.parse(robots.decode("utf-8", errors="replace").splitlines())
            row["robotsSha256"] = hashlib.sha256(robots).hexdigest()
            if not parser.can_fetch(USER_AGENT, seed):
                row.update({"status": "robots_excluded", "reason": "seed is disallowed"})
                return row

            request = urllib.request.Request(seed, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read(self.max_bytes + 1)
                content_type = str(response.headers.get("Content-Type") or "")
                final_url, status = response.geturl(), int(response.status)
            if len(body) > self.max_bytes:
                raise ValueError("seed response exceeds byte limit")
            final_host = (urlsplit(final_url).hostname or "").lower().removeprefix("www.")
            allowed = {str(host).lower().removeprefix("www.") for host in site["hosts"]}
            if final_host not in allowed:
                row.update({"status": "scope_excluded", "reason": f"redirected outside registered hosts to {final_host}", "finalUrl": final_url})
                return row
            if status < 200 or status >= 300 or "html" not in content_type.lower():
                row.update({"status": "unavailable", "reason": f"HTTP {status} with {content_type or 'unknown type'}", "finalUrl": final_url})
                return row
            row.update({
                "status": "enabled", "enabled": True, "finalUrl": final_url,
                "httpStatus": status, "contentType": content_type,
                "responseBytes": len(body), "responseSha256": hashlib.sha256(body).hexdigest(),
            })
            return row
        except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            row.update({"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"})
            return row


def _phase_settings(experiment: Mapping[str, Any], phase: str) -> dict[str, int]:
    parameters = dict(experiment.get("parameters") or {})
    selected = dict((parameters.get("phases") or {}).get(phase) or {})
    if not selected and phase == str(parameters.get("phase", "engineering")):
        selected = parameters
    if not selected:
        raise ValueError(f"unknown live study phase: {phase}")
    interval = int(selected.get("intervalMinutes", 10))
    if interval < 0:
        raise ValueError("live interval must not be negative")
    if "executions" in selected:
        executions = int(selected["executions"])
    else:
        duration = int(selected.get("durationMinutes", 30))
        executions = max(1, (duration + max(interval, 1) - 1) // max(interval, 1))
    if executions < 1:
        raise ValueError("live study needs at least one execution")
    return {"executions": executions, "intervalMinutes": interval}


def run_live_study(
    experiment: Mapping[str, Any], artifact_root: Path, *, phase: str | None = None,
    reviewer: Any | None = None, fetcher: Any | None = None,
    wait: Callable[[float], None] = time.sleep, progress_path: Path | None = None,
) -> dict[str, Any]:
    """Run one bounded repeated live study and retain its local workspace."""
    from pulsecrawl import Workspace, __version__ as pulsecrawl_version

    parameters = dict(experiment.get("parameters") or {})
    study = str(parameters["study"])
    selected_phase = phase or str(parameters.get("phase", "engineering"))
    settings = _phase_settings(experiment, selected_phase)
    manifest_path = Path(parameters["manifest"])
    if not manifest_path.is_absolute():
        manifest_path = Path(__file__).parents[2] / manifest_path
    manifest = load_live_manifest(manifest_path, expected_study=study)
    schema_profile = str(manifest.get("schemaProfile") or manifest.get("study") or study)
    if schema_profile == "news":
        schema_profile = "article"
    elif schema_profile == "commerce":
        schema_profile = "product"
    definition = profile(schema_profile)
    artifact_root.mkdir(parents=True, exist_ok=True)
    atomic_json(artifact_root / "resolved-site-manifest.json", manifest)
    reviewer = reviewer or LiveAccessReviewer()
    phase_sites: list[dict[str, Any]] = []
    for original in manifest["sites"]:
        site = dict(original)
        phase_seed_key = f"{selected_phase}SeedUrls"
        if site.get(phase_seed_key):
            site["seedUrls"] = list(site[phase_seed_key])
        phase_sites.append(site)
    access: list[dict[str, Any]] = []
    for site in phase_sites:
        if (
            selected_phase in {"qualification", "retained"}
            and site.get("retainedEnabled") is False
        ):
            access.append({
                "siteId": site["id"],
                "siteName": site["name"],
                "seedUrl": site["seedUrls"][0],
                "checkedAt": datetime.now(UTC).isoformat(),
                "enabled": False,
                "status": "study_excluded",
                "reason": str(
                    site.get("retainedExclusion")
                    or "excluded after the initial qualification review"
                ),
            })
        else:
            access.append(reviewer.review(site))
    atomic_json(artifact_root / "access-review.json", {
        "schemaVersion": 1, "reviewedAt": datetime.now(UTC).isoformat(),
        "userAgent": USER_AGENT, "failClosed": True, "retainsHtml": False, "sites": access,
    })
    enabled_ids = {str(row["siteId"]) for row in access if row.get("enabled")}
    enabled = [site for site in phase_sites if str(site["id"]) in enabled_ids]
    result: dict[str, Any] = {
        "status": "running" if enabled else "unavailable", "study": study,
        "schemaProfile": schema_profile,
        "phase": selected_phase, "publicPackageVersion": pulsecrawl_version,
        "requestedSites": len(manifest["sites"]), "enabledSites": len(enabled),
        "excludedSites": len(manifest["sites"]) - len(enabled), "settings": settings,
        "executions": [],
    }
    progress_path = progress_path or artifact_root / "progress.json"
    atomic_json(progress_path, result)
    if not enabled:
        return result

    workspace = Workspace.init(artifact_root / "workspace", name=f"live-{study}-{selected_phase}")
    fields = list(definition["fields"])
    dataset = workspace.datasets.create(
        f"Live {study} observations", fields=fields,
        mode=str(definition["publicationMode"]),
    )
    maximum = int(parameters.get("maxUrlsPerSitePerExecution", definition["defaultMaxUrls"]))
    maximum_depth = int(parameters.get("maxDepth", definition["defaultMaxDepth"]))
    jobs: dict[str, dict[str, Any]] = {}
    for site in enabled:
        site_maximum = int(site.get(
            f"{selected_phase}MaxUrlsPerExecution", site.get("maxUrlsPerExecution", maximum)
        ))
        site_depth = int(site.get(
            f"{selected_phase}MaxDepth", site.get("maxDepth", maximum_depth)
        ))
        delay = float(site.get("minimumOriginDelaySeconds", parameters.get("minimumOriginDelaySeconds", 5)))
        rate = 1.0 / delay
        jobs[str(site["id"])] = workspace.jobs.create(
            f"{study}: {site['name']}", seeds=list(site["seedUrls"]), dataset_id=dataset["datasetId"],
            templates=templates_for(schema_profile, site),
            scope={
                "sameDomainOnly": True, "maxDepth": site_depth,
                "maxUrlsPerExecution": site_maximum,
                "maxUrlsTotal": site_maximum * settings["executions"],
                "includePatterns": list(site.get("discoveryPatterns") or []),
            },
            politeness={
                "respectRobotsTxt": True, "requestsPerSecond": rate,
                "organizationRequestsPerSecond": rate, "userAgent": USER_AGENT,
            },
            store_raw_pages=False,
        )
    try:
        start = time.monotonic()
        started_at = datetime.now(UTC)
        for sequence in range(settings["executions"]):
            if sequence:
                due = start + sequence * settings["intervalMinutes"] * 60
                wait(max(0.0, due - time.monotonic()))
            scheduled_at = started_at + timedelta(minutes=sequence * settings["intervalMinutes"])
            cycle_started = datetime.now(UTC)
            cycle: dict[str, Any] = {
                "sequence": sequence + 1,
                "scheduledAt": scheduled_at.isoformat(),
                "startedAt": cycle_started.isoformat(),
                "startLagSeconds": max(0.0, (cycle_started - scheduled_at).total_seconds()),
                "sites": [],
            }
            for site in enabled:
                site_id = str(site["id"])
                execution_id = f"exec_{selected_phase}_{site_id}_{sequence + 1:03d}"
                observed: dict[str, Any] = {"siteId": site_id, "executionId": execution_id}
                try:
                    execution = workspace.jobs.run(jobs[site_id]["jobId"], execution_id=execution_id, fetcher=fetcher)
                    observed.update({
                        "status": execution["status"], "stats": execution.get("stats", {}),
                        "startedAt": execution.get("startedAt"), "finishedAt": execution.get("finishedAt"),
                    })
                except Exception as exc:  # changing live sites must remain visible evidence
                    observed.update({"status": "failed", "reason": f"{type(exc).__name__}: {exc}"})
                cycle["sites"].append(observed)
            cycle_finished = datetime.now(UTC)
            cycle["finishedAt"] = cycle_finished.isoformat()
            cycle["durationSeconds"] = (cycle_finished - cycle_started).total_seconds()
            result["executions"].append(cycle)
            atomic_json(progress_path, result)

        files = workspace.datasets.files(dataset["datasetId"])
        query = workspace.datasets.query(
            dataset["datasetId"],
            "SELECT count(*) AS rows, count(DISTINCT _execution_id) AS executions, "
            "count(DISTINCT _source_url) AS source_urls FROM dataset",
        )
        quality = workspace.datasets.query(dataset["datasetId"], quality_query(schema_profile))
        result.update({
            "status": "completed", "datasetId": dataset["datasetId"],
            "jobIds": {key: value["jobId"] for key, value in jobs.items()},
            "datasetFiles": files, "querySummary": query, "qualitySummary": quality,
            "workspaceValidation": workspace.validate(), "completedAt": datetime.now(UTC).isoformat(),
        })
        atomic_json(progress_path, result)
        return result
    finally:
        workspace.close()
