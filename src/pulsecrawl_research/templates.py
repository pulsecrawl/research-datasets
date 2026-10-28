"""Controlled extraction-strategy ablations."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from .metrics import summarize
from .webbench import VirtualSite, WebBenchConfig


def _load_core():
    from pulsecrawl.core.extraction import get_engine

    return get_engine


def _extract(engine: str, body: str, mappings: dict[str, tuple[str, ...]]) -> dict[str, str]:
    rows = _load_core()(engine)(body, mappings)
    return dict(rows[0]) if rows else {}


def _site_templates(site: VirtualSite) -> list[dict[str, Any]]:
    common_css = {
        "title": ("h1",),
        "body": (f"div.content-{site.number:02d}",),
        "site": (f"literal:{site.site_id}",),
    }
    jsonld = {
        "title": (f"{site.item(1)['kind']}.name",),
        "body": (
            f"{site.item(1)['kind']}.articleBody",
            f"{site.item(1)['kind']}.description",
        ),
        "site": (f"literal:{site.site_id}",),
    }
    meta = {
        "title": ("og:title", "<title>"),
        "body": ("og:description",),
        "site": (f"literal:{site.site_id}",),
    }
    return [
        {"engine": "jsonld", "mappings": jsonld, "site": site.site_id},
        {"engine": "meta", "mappings": meta, "site": site.site_id},
        {"engine": "css", "mappings": common_css, "site": site.site_id},
    ]


def _apply(templates: list[dict[str, Any]], body: str) -> dict[str, str]:
    winner: dict[str, str] = {}
    for template in templates:
        row = _extract(template["engine"], body, template["mappings"])
        if not row:
            continue
        if not winner:
            winner.update(row)
        else:
            for field, value in row.items():
                winner.setdefault(field, value)
    return winner


def run_template_benchmark(
    *,
    sites_per_vertical: int = 5,
    items_per_site: int = 20,
    seed: int = 4703,
    mode: str = "scoping",
    mutations: list[str] | None = None,
    corpus_path: Path | None = None,
) -> dict[str, Any]:
    if mode == "corpus":
        if corpus_path is None:
            raise ValueError("corpus mode requires corpus_path")
        return _run_corpus(corpus_path)
    config = WebBenchConfig(
        items_per_site=items_per_site,
        sites_per_vertical=sites_per_vertical,
        seed=seed,
    )
    sites = [
        VirtualSite(config, vertical, number)
        for vertical in ("news", "jobs", "products")
        for number in range(1, sites_per_vertical + 1)
    ]
    if mode == "fallback":
        return _run_fallback(sites, items_per_site)
    if mode == "drift":
        return _run_drift(sites, items_per_site, mutations or [])
    if mode != "scoping":
        raise ValueError(f"unknown template benchmark mode: {mode}")
    all_templates = [template for site in sites for template in _site_templates(site)]
    strategies = {"generic": [], "unscoped": all_templates, "routed": [], "scoped": []}
    counters = {
        name: {"records": 0, "correctFields": 0, "expectedFields": 0, "contaminated": 0}
        for name in strategies
    }
    for site in sites:
        routed = _site_templates(site)
        system = [
            {
                "engine": "meta",
                "mappings": {"title": ("og:title", "<title>"), "body": ("og:description",)},
                "site": None,
            }
        ]
        for item_id in range(1, items_per_site + 1):
            truth = site.item(item_id)
            body = site.render_item(item_id)
            rows = {
                "generic": _apply(system, body),
                "unscoped": _apply(all_templates + system, body),
                "routed": _apply(routed, body),
                "scoped": _apply(routed + system, body),
            }
            for strategy, row in rows.items():
                expected = {"title": truth["title"], "body": truth["body"]}
                counters[strategy]["records"] += int(bool(row))
                counters[strategy]["expectedFields"] += len(expected)
                counters[strategy]["correctFields"] += sum(
                    row.get(field) == value for field, value in expected.items()
                )
                if row.get("site") is not None and row.get("site") != site.site_id:
                    counters[strategy]["contaminated"] += 1
    result: dict[str, Any] = {"status": "completed", "strategies": {}}
    total_pages = len(sites) * items_per_site
    for strategy, values in counters.items():
        expected_fields = values["expectedFields"]
        result["strategies"][strategy] = {
            **values,
            "pages": total_pages,
            "recordCoverage": values["records"] / total_pages,
            "fieldAccuracy": values["correctFields"] / expected_fields,
            "contaminationRate": values["contaminated"] / total_pages,
        }
    return result


def _run_fallback(sites: list[VirtualSite], items_per_site: int) -> dict[str, Any]:
    """Measure explicit system fallback and needs-template diagnostics."""

    system = [
        {
            "engine": "meta",
            "mappings": {"title": ("og:title", "<title>"), "body": ("og:description",)},
            "site": None,
        },
        {
            "engine": "css",
            "mappings": {"title": ("article h1", "main h1", "h1"), "body": ("article div", "main p")},
            "site": None,
        },
    ]
    counters = {
        "authoredMatches": 0,
        "systemFallbackMatches": 0,
        "needsTemplate": 0,
        "completeRecords": 0,
        "pages": 0,
    }
    diagnostics: dict[str, dict[str, int]] = {}
    for site in sites:
        # Every fourth site deliberately represents a newly discovered host.
        authored = [] if site.number % 4 == 0 else _site_templates(site)
        site_counts = {"authored": 0, "fallback": 0, "miss": 0}
        for item_id in range(1, items_per_site + 1):
            body = site.render_item(item_id)
            authored_row = _apply(authored, body)
            fallback_row = {} if authored_row else _apply(system, body)
            row = authored_row or fallback_row
            counters["pages"] += 1
            if authored_row:
                counters["authoredMatches"] += 1
                site_counts["authored"] += 1
            elif fallback_row:
                counters["systemFallbackMatches"] += 1
                site_counts["fallback"] += 1
            else:
                site_counts["miss"] += 1
            if row.get("title") and row.get("body"):
                counters["completeRecords"] += 1
            # A fallback-only or complete miss is actionable even when a
            # generic title was recovered.
            if not authored_row:
                counters["needsTemplate"] += 1
        diagnostics[site.site_id] = site_counts
    return {
        "status": "completed",
        **counters,
        "fallbackRate": counters["systemFallbackMatches"] / counters["pages"],
        "needsTemplateRate": counters["needsTemplate"] / counters["pages"],
        "diagnosticsBySite": diagnostics,
    }


def _mutate(body: str, mutation: str, site: VirtualSite) -> str:
    if mutation == "class_renamed":
        return body.replace(f"content-{site.number:02d}", "content-renamed")
    if mutation == "body_moved":
        return body.replace("<div class=", "<section class=").replace("</div>", "</section>")
    if mutation == "jsonld_removed":
        return re.sub(
            r"<script type='application/ld\+json'>.*?</script>", "", body, flags=re.DOTALL
        )
    if mutation == "jsonld_malformed":
        return body.replace("</script>", ",</script>", 1)
    if mutation == "metadata_removed":
        return re.sub(r"<meta property='og:[^>]+>", "", body)
    if mutation == "multiple_entities":
        marker = "<script type='application/ld+json'>"
        if marker not in body:
            return body
        decoy = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": site.item(1)["kind"],
                "name": "unrelated entity",
                "description": "unrelated body",
            }
        )
        return body.replace(marker, f"{marker}{decoy}</script>{marker}", 1)
    raise ValueError(f"unknown mutation: {mutation}")


def _run_drift(
    sites: list[VirtualSite], items_per_site: int, mutations: list[str]
) -> dict[str, Any]:
    if not mutations:
        raise ValueError("drift mode needs at least one mutation")
    results: dict[str, Any] = {}
    for mutation in mutations:
        pages = correct = records = 0
        by_layout: dict[str, dict[str, int]] = {}
        for site in sites:
            layout = by_layout.setdefault(site.layout, {"pages": 0, "records": 0, "correct": 0})
            for item_id in range(1, items_per_site + 1):
                truth = site.item(item_id)
                row = _apply(_site_templates(site), _mutate(site.render_item(item_id), mutation, site))
                pages += 1
                records += int(bool(row))
                matched = int(
                    row.get("title") == truth["title"] and row.get("body") == truth["body"]
                )
                correct += matched
                layout["pages"] += 1
                layout["records"] += int(bool(row))
                layout["correct"] += matched
        results[mutation] = {
            "pages": pages,
            "records": records,
            "correctRecords": correct,
            "recordCoverage": records / pages,
            "recordAccuracy": correct / pages,
            "byLayout": by_layout,
        }
    return {"status": "completed", "mutations": results}


def _run_corpus(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    root = manifest_path.parent.resolve()
    rows: list[dict[str, Any]] = []
    true_positive = false_positive = false_negative = 0
    latencies: list[float] = []
    for number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        entry = json.loads(line)
        sample = (root / str(entry["path"])).resolve()
        if root not in sample.parents:
            raise ValueError(f"corpus row {number} escapes its root")
        body = sample.read_text(encoding="utf-8")
        digest = hashlib.sha256(body.encode()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"corpus row {number} checksum mismatch")
        started = time.perf_counter()
        extracted = _extract(str(entry["engine"]), body, {
            key: tuple(values) for key, values in entry["mappings"].items()
        })
        latencies.append(time.perf_counter() - started)
        truth = dict(entry["truth"])
        correct = sum(extracted.get(field) == value for field, value in truth.items())
        for field, expected_value in truth.items():
            if extracted.get(field) == expected_value:
                true_positive += 1
            elif field in extracted:
                false_positive += 1
                false_negative += 1
            else:
                false_negative += 1
        false_positive += sum(field not in truth for field in extracted)
        rows.append(
            {
                "id": entry["id"],
                "vertical": entry["vertical"],
                "expectedFields": len(truth),
                "correctFields": correct,
                "recordMatched": bool(extracted),
                "completeRecord": correct == len(truth),
                "layout": entry.get("layout", "legacy"),
            }
        )
    expected = sum(row["expectedFields"] for row in rows)
    correct = sum(row["correctFields"] for row in rows)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
    return {
        "status": "completed",
        "documents": len(rows),
        "recordsMatched": sum(row["recordMatched"] for row in rows),
        "fieldAccuracy": correct / expected if expected else 0,
        "fieldPrecision": precision,
        "fieldRecall": recall,
        "fieldF1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
        "completeRecords": sum(row["completeRecord"] for row in rows),
        "extractionLatencySeconds": summarize(latencies),
        "authoringSelectors": sum(
            len(values)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for values in json.loads(line)["mappings"].values()
        ),
        "rows": rows,
    }
