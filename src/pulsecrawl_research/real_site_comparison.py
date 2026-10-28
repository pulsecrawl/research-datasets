"""Executable scoped-template comparison over generated controlled inputs.

Current inputs use fictional names and .example domains. Historical catalogs
remain supported to interpret earlier runs; page content is always generated.
The module evaluates user integration surfaces, not framework internals.
"""
from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit



SYSTEMS = (
    "pulsecrawl",
    "scrapy",
    "crawlee-python",
    "beautifulsoup-reference",
    "firecrawl-client",
)


def load_real_site_catalog(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    sites = raw.get("sites") or []
    required = {
        "id", "vertical", "sourceName", "host", "pathPrefix", "family",
        "entityType", "titleProperty", "bodyProperty", "titleSelector",
        "bodySelector",
    }
    if len(sites) != 20 or len({row["id"] for row in sites}) != len(sites):
        raise ValueError("T09 catalog must contain 20 unique sites")
    for row in sites:
        missing = required.difference(row)
        if missing:
            raise ValueError(f"{row.get('id', 'site')} missing {sorted(missing)}")
        if not str(row["pathPrefix"]).startswith("/"):
            raise ValueError(f"{row['id']} pathPrefix must start with /")
    return raw


def _tag_for_atom(atom: str, content: str) -> str:
    atom = atom.strip()
    tag = "div"
    identifier = None
    attributes: dict[str, str] = {}
    classes: list[str] = []
    attribute = re.fullmatch(r"\[([^=\]]+)='([^']+)'\]", atom)
    presence = re.fullmatch(r"\[([^=\]]+)\]", atom)
    if attribute:
        attributes[attribute.group(1)] = attribute.group(2)
    elif presence:
        attributes[presence.group(1)] = presence.group(1)
    else:
        match = re.match(r"^([a-zA-Z][\w-]*)", atom)
        if match:
            tag = match.group(1)
        id_match = re.search(r"#([\w-]+)", atom)
        if id_match:
            identifier = id_match.group(1)
        classes = re.findall(r"\.([\w-]+)", atom)
    attrs = []
    if identifier:
        attrs.append(f'id="{identifier}"')
    if classes:
        attrs.append(f'class="{" ".join(classes)}"')
    attrs.extend(f'{key}="{html.escape(value, quote=True)}"' for key, value in attributes.items())
    suffix = " " + " ".join(attrs) if attrs else ""
    return f"<{tag}{suffix}>{content}</{tag}>"


def _selector_markup(selector: str, content: str) -> str:
    nested = html.escape(content)
    for atom in reversed(selector.split()):
        nested = _tag_for_atom(atom, nested)
    return nested


def _truth(site: dict[str, Any], item: int) -> dict[str, str]:
    url = f"https://{site['host']}{site['pathPrefix']}fixture-{item}"
    return {
        "title": f"{site['sourceName']} synthetic item {item}",
        "body": f"Synthetic {site['vertical']} body {site['id']} item {item}",
        "url": url,
        "source_name": str(site["sourceName"]),
    }


def render_fixture(
    site: dict[str, Any],
    item: int,
    *,
    mutation: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Render one generated page using five extraction/fallback variants."""

    truth = _truth(site, item)
    title_markup = _selector_markup(str(site["titleSelector"]), truth["title"])
    body_selector = str(site["bodySelector"])
    if mutation == "shared_selector_rename" and site["family"] == "shopify-product":
        body_selector = ".product-details"
    if mutation == "site_selector_rename" and site["id"] in {"news-laopcion", "news-case-05"}:
        body_selector = "div.newsfull__content"
    body_markup = _selector_markup(body_selector, truth["body"])
    if mutation == "wrapper_insertion":
        body_markup = f'<section class="layout-wrapper">{body_markup}</section>'

    entity = {
        "@context": "https://schema.org",
        "@type": site["entityType"],
        site["titleProperty"]: truth["title"],
        site["bodyProperty"]: truth["body"],
        "url": truth["url"],
    }
    if site["vertical"] == "jobs":
        entity["hiringOrganization"] = {"name": truth["source_name"]}
    elif site["vertical"] == "products":
        entity["brand"] = {"name": truth["source_name"]}
    else:
        entity["publisher"] = {"name": truth["source_name"]}

    jsonld = ""
    meta = ""
    css = f"{title_markup}{body_markup}"
    variant = ((item - 1) % 5) + 1
    if variant in {1, 2}:
        payload: Any = entity if variant == 1 else {"@context": "https://schema.org", "@graph": [entity]}
        if mutation == "multiple_entities":
            decoy = dict(entity)
            decoy[site["titleProperty"]] = "Unrelated entity"
            decoy[site["bodyProperty"]] = "Unrelated body"
            decoy["url"] = f"https://{site['host']}/related"
            payload = [decoy, entity]
        if mutation == "canonical_change":
            entity["url"] = f"https://{site['host']}/old-canonical"
        if mutation == "jsonld_to_meta":
            variant = 3
        else:
            jsonld = (
                '<script type="application/ld+json">'
                + json.dumps(payload, ensure_ascii=False)
                + "</script>"
            )
    if variant == 3:
        meta = "".join(
            (
                f'<meta property="og:title" content="{html.escape(truth["title"], quote=True)}">',
                f'<meta property="og:description" content="{html.escape(truth["body"], quote=True)}">',
                f'<meta property="og:url" content="{html.escape(truth["url"], quote=True)}">',
            )
        )
    elif variant == 4:
        meta = ""
    elif variant == 5:
        jsonld = '<script type="application/ld+json">{"@type":,}</script>'
        meta = ""
    if mutation == "negative_page":
        return "<html><head><title>Index</title></head><body><nav>Navigation</nav></body></html>", truth
    return (
        "<!doctype html><html><head>"
        f'<link rel="canonical" href="{html.escape(truth["url"], quote=True)}">'
        f"<title>{html.escape(truth['title'])}</title>{meta}{jsonld}"
        f"</head><body>{css}</body></html>",
        truth,
    )


def _scope_match(site: dict[str, Any], url: str) -> bool:
    split = urlsplit(url)
    return (split.hostname or "").lower() == str(site["host"]).lower() and split.path.startswith(str(site["pathPrefix"]))


def _core_engines() -> Callable[[str], Any]:
    from pulsecrawl.core.extraction import get_engine

    return get_engine


def _mappings(site: dict[str, Any]) -> list[tuple[str, dict[str, tuple[str, ...]]]]:
    source_path = {
        "news": "publisher.name",
        "jobs": "hiringOrganization.name",
        "products": "brand.name",
    }[site["vertical"]]
    entity = str(site["entityType"])
    return [
        (
            "jsonld",
            {
                "title": (f"{entity}.{site['titleProperty']}",),
                "body": (f"{entity}.{site['bodyProperty']}",),
                "url": (f"{entity}.url",),
                "source_name": (f"{entity}.{source_path}",),
            },
        ),
        (
            "meta",
            {
                "title": ("og:title", "<title>"),
                "body": ("og:description",),
                "url": ("og:url",),
                "source_name": (f"literal:{site['sourceName']}",),
            },
        ),
        (
            "css",
            {
                "title": (str(site["titleSelector"]),),
                "body": (str(site["bodySelector"]),),
                "url": ("link[rel='canonical']@href",),
                "source_name": (f"literal:{site['sourceName']}",),
            },
        ),
    ]


def _pulse_extract(site: dict[str, Any], url: str, body: str) -> tuple[dict[str, str], str | None]:
    if not _scope_match(site, url):
        return {}, None
    winner: dict[str, str] = {}
    provenance: list[str] = []
    get_engine = _core_engines()
    for engine, mappings in _mappings(site):
        rows = get_engine(engine)(body, mappings)
        if not rows:
            continue
        for field, value in rows[0].items():
            if field not in winner:
                winner[field] = value
                provenance.append(engine)
    return winner, "+".join(dict.fromkeys(provenance)) or None


def _jsonld_entities(body: str) -> list[dict[str, Any]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(body, "html.parser")
    entities: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.get_text())
        except json.JSONDecodeError:
            continue
        stack: list[Any] = [value]
        while stack:
            node = stack.pop(0)
            if isinstance(node, list):
                stack[0:0] = node
            elif isinstance(node, dict):
                graph = node.get("@graph")
                if isinstance(graph, list):
                    stack[0:0] = graph
                if node.get("@type"):
                    entities.append(node)
    return entities


def _walk(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            current = current[0] if current else None
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _imperative_extract(
    site: dict[str, Any],
    url: str,
    body: str,
    *,
    parser: str,
) -> tuple[dict[str, str], str | None]:
    if not _scope_match(site, url):
        return {}, None
    for entity in _jsonld_entities(body):
        declared = entity.get("@type")
        types = {str(value).lower() for value in (declared if isinstance(declared, list) else [declared])}
        if str(site["entityType"]).lower() not in types:
            continue
        source_path = {"news": "publisher.name", "jobs": "hiringOrganization.name", "products": "brand.name"}[site["vertical"]]
        row = {
            "title": _walk(entity, str(site["titleProperty"])),
            "body": _walk(entity, str(site["bodyProperty"])),
            "url": entity.get("url"),
            "source_name": _walk(entity, source_path),
        }
        cleaned = {key: str(value).strip() for key, value in row.items() if value is not None and str(value).strip()}
        if cleaned:
            return cleaned, "jsonld"

    if parser == "parsel":
        from parsel import Selector

        document = Selector(text=body)
        meta = {
            key: document.css(f'meta[property="{key}"]::attr(content),meta[name="{key}"]::attr(content)').get()
            for key in ("og:title", "og:description", "og:url")
        }
        if any(meta.values()):
            return {
                key: str(value).strip()
                for key, value in {
                    "title": meta["og:title"], "body": meta["og:description"],
                    "url": meta["og:url"], "source_name": site["sourceName"],
                }.items()
                if value
            }, "meta"
        title = " ".join(document.css(str(site["titleSelector"]) + " ::text").getall()).strip()
        body_text = " ".join(document.css(str(site["bodySelector"]) + " ::text").getall()).strip()
        canonical = document.css('link[rel="canonical"]::attr(href)').get()
    else:
        from bs4 import BeautifulSoup

        document = BeautifulSoup(body, "html.parser")
        meta_values = {
            key: (document.select_one(f'meta[property="{key}"]') or document.select_one(f'meta[name="{key}"]'))
            for key in ("og:title", "og:description", "og:url")
        }
        if any(meta_values.values()):
            return {
                key: str(value).strip()
                for key, value in {
                    "title": meta_values["og:title"].get("content") if meta_values["og:title"] else None,
                    "body": meta_values["og:description"].get("content") if meta_values["og:description"] else None,
                    "url": meta_values["og:url"].get("content") if meta_values["og:url"] else None,
                    "source_name": site["sourceName"],
                }.items()
                if value
            }, "meta"
        title_node = document.select_one(str(site["titleSelector"]))
        body_node = document.select_one(str(site["bodySelector"]))
        title = title_node.get_text(" ", strip=True) if title_node else ""
        body_text = body_node.get_text(" ", strip=True) if body_node else ""
        canonical_node = document.select_one('link[rel="canonical"]')
        canonical = canonical_node.get("href") if canonical_node else None
    row = {
        "title": title,
        "body": body_text,
        "url": str(canonical) if canonical else "",
        "source_name": str(site["sourceName"]),
    }
    return ({key: value for key, value in row.items() if value}, "css") if title or body_text else ({}, None)


def _source_catalog(catalog: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            {
                key: site[key]
                for key in (
                    "id", "host", "pathPrefix", "sourceName", "entityType",
                    "titleProperty", "bodyProperty", "titleSelector", "bodySelector",
                )
            }
            for site in catalog
        ],
        sort_keys=True,
    )


def integration_sources(catalog: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    compact = _source_catalog(catalog)
    template_resources: list[dict[str, Any]] = []
    shared_jsonld: dict[str, str] = {}
    for vertical in ("news", "jobs", "products"):
        site = next(row for row in catalog if row["vertical"] == vertical)
        template_id = f"tmpl_t09_{vertical}_jsonld"
        shared_jsonld[vertical] = template_id
        template_resources.append({
            "templateId": template_id,
            "engine": "jsonld",
            "mappings": _mappings(site)[0][1],
        })
    stack: list[dict[str, Any]] = []
    for site in catalog:
        slug = str(site["id"]).replace("-", "_")
        scope = {
            "hosts": [site["host"]],
            "urlPatterns": [f"https://{site['host']}{site['pathPrefix']}**"],
        }
        meta_id = f"tmpl_t09_{slug}_meta"
        css_id = f"tmpl_t09_{slug}_css"
        template_resources.extend((
            {"templateId": meta_id, "engine": "meta", "mappings": _mappings(site)[1][1]},
            {"templateId": css_id, "engine": "css", "mappings": _mappings(site)[2][1]},
        ))
        stack.extend((
            {"templateId": shared_jsonld[str(site["vertical"])], "scope": scope},
            {"templateId": meta_id, "scope": scope},
            {"templateId": css_id, "scope": scope},
        ))
    pulse = json.dumps(
        {
            "templates": template_resources,
            "job": {"templateStack": stack},
            "systemFallback": True,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    python_header = (
        "# Generated T09 user integration; framework runtime is pinned separately.\n"
        "import json\n"
        f"ROUTES = json.loads({compact!r})\n"
    )
    scrapy = python_header + (
        "def parse(response, route):\n"
        "    return {'title': response.css(route['titleSelector'] + ' ::text').get(), "
        "'body': response.css(route['bodySelector'] + ' ::text').get(), "
        "'source_name': route['sourceName']}\n"
    )
    crawlee = python_header + (
        "async def handle(context, route):\n"
        "    soup = context.soup\n"
        "    return {'title': soup.select_one(route['titleSelector']).get_text(strip=True), "
        "'body': soup.select_one(route['bodySelector']).get_text(strip=True), "
        "'source_name': route['sourceName']}\n"
    )
    beautiful = python_header + (
        "def extract(soup, route):\n"
        "    return {'title': soup.select_one(route['titleSelector']).get_text(strip=True), "
        "'body': soup.select_one(route['bodySelector']).get_text(strip=True), "
        "'source_name': route['sourceName']}\n"
    )
    firecrawl = json.dumps(
        {
            "extract": {"schema": {"title": "string", "body": "string", "source_name": "string"}},
            "capabilityBoundary": "deterministic host/CSS routing is client orchestration",
            "clientRoutes": json.loads(compact),
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    return {
        "pulsecrawl": ("integration.json", pulse),
        "scrapy": ("integration.py", scrapy),
        "crawlee-python": ("integration.py", crawlee),
        "beautifulsoup-reference": ("integration.py", beautiful),
        "firecrawl-client": ("integration.json", firecrawl),
    }


def _loc(source: str) -> int:
    return sum(bool(line.strip()) and not line.lstrip().startswith(("#", "//")) for line in source.splitlines())


def write_integration_sources(catalog: list[dict[str, Any]], root: Path) -> dict[str, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, dict[str, Any]] = {}
    for system, (filename, source) in integration_sources(catalog).items():
        target = root / system / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        if filename.endswith(".json"):
            json.loads(source)
            syntax = "json.loads"
        else:
            ast.parse(source)
            syntax = "ast.parse"
        metrics[system] = {
            "artifact": str(target.relative_to(root)),
            "sha256": hashlib.sha256(source.encode()).hexdigest(),
            "authoredLoc": _loc(source),
            "authoredBytes": len(source.encode()),
            "maintainedFiles": 1,
            "maintainedComponents": 1 if system == "pulsecrawl" else 2,
            "syntaxCheck": syntax,
        }
    return metrics


def validate_real_site_baselines(catalog_path: Path, baseline_root: Path) -> list[str]:
    errors: list[str] = []
    catalog = load_real_site_catalog(catalog_path)["sites"]
    manifest = json.loads((baseline_root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("catalogSites") != len(catalog):
        errors.append("T09 baseline catalog size mismatch")
    expected = integration_sources(catalog)
    for system, (filename, source) in expected.items():
        row = (manifest.get("systems") or {}).get(system) or {}
        target = baseline_root / system / filename
        digest = hashlib.sha256(source.encode()).hexdigest()
        if not target.is_file() or target.read_text(encoding="utf-8") != source:
            errors.append(f"T09 baseline source mismatch: {system}")
        if row.get("sha256") != digest or row.get("authoredLoc") != _loc(source):
            errors.append(f"T09 baseline manifest mismatch: {system}")
    return errors


def _score(system: str, catalog: list[dict[str, Any]], documents_per_site: int) -> dict[str, Any]:
    expected_fields = correct_fields = predicted_fields = records = 0
    provenance = 0
    for site in catalog:
        for item in range(1, documents_per_site + 1):
            body, truth = render_fixture(site, item)
            if system == "pulsecrawl":
                row, used = _pulse_extract(site, truth["url"], body)
            else:
                row, used = _imperative_extract(
                    site,
                    truth["url"],
                    body,
                    parser="parsel" if system == "scrapy" else "beautifulsoup",
                )
            records += int(bool(row))
            provenance += int(bool(used))
            expected_fields += len(truth)
            predicted_fields += len(row)
            correct_fields += sum(row.get(field) == value for field, value in truth.items())
    precision = correct_fields / predicted_fields if predicted_fields else 0.0
    recall = correct_fields / expected_fields if expected_fields else 0.0
    return {
        "documents": len(catalog) * documents_per_site,
        "records": records,
        "correctFields": correct_fields,
        "expectedFields": expected_fields,
        "predictedFields": predicted_fields,
        "fieldPrecision": precision,
        "fieldRecall": recall,
        "fieldF1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "provenanceCoverage": provenance / (len(catalog) * documents_per_site),
    }


def _drift_score(system: str, catalog: list[dict[str, Any]], mutation: str) -> dict[str, Any]:
    sites = [site for site in catalog if (
        mutation not in {"shared_selector_rename", "site_selector_rename"}
        or (mutation == "shared_selector_rename" and site["family"] == "shopify-product")
        or (mutation == "site_selector_rename" and site["id"] in {"news-laopcion", "news-case-05"})
    )]
    if not sites:
        sites = catalog
    expected = correct = records = 0
    for site in sites:
        item = 4 if "selector_rename" in mutation or mutation == "wrapper_insertion" else 1
        body, truth = render_fixture(site, item, mutation=mutation)
        if system == "pulsecrawl":
            row, _ = _pulse_extract(site, truth["url"], body)
        else:
            row, _ = _imperative_extract(
                site, truth["url"], body,
                parser="parsel" if system == "scrapy" else "beautifulsoup",
            )
        records += int(bool(row))
        expected += len(truth)
        correct += sum(row.get(field) == value for field, value in truth.items())
    return {
        "documents": len(sites),
        "records": records,
        "recordCoverage": records / len(sites) if sites else 0.0,
        "falsePositiveRate": records / len(sites) if mutation == "negative_page" and sites else None,
        "fieldAccuracy": correct / expected if expected else 0.0,
    }


def _repaired_catalog(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repaired = copy.deepcopy(catalog)
    for site in repaired:
        if site["family"] == "shopify-product":
            site["bodySelector"] = ".product-details"
        if site["id"] in {"news-laopcion", "news-case-05"}:
            site["bodySelector"] = "div.newsfull__content"
    return repaired


def _change_metrics(before: str, after: str) -> dict[str, int]:
    matcher = difflib.SequenceMatcher(
        None, before.splitlines(), after.splitlines(), autojunk=False
    )
    changed = 0
    hunks = 0
    for opcode, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if opcode == "equal":
            continue
        changed += before_end - before_start + after_end - after_start
        hunks += 1
    return {
        "changedFiles": int(before != after),
        "changedLines": changed,
        "diffHunks": hunks,
    }


def run_real_site_comparison(
    catalog_path: Path,
    output_root: Path,
    *,
    documents_per_site: int = 5,
    drift_cases: list[str] | None = None,
) -> dict[str, Any]:
    if documents_per_site < 5:
        raise ValueError("T09 needs at least five documents per site")
    catalog_document = load_real_site_catalog(catalog_path)
    catalog = list(catalog_document["sites"])
    drift_cases = drift_cases or []
    fixtures = output_root / "fixtures"
    fixture_manifest: list[dict[str, Any]] = []
    for site in catalog:
        for item in range(1, documents_per_site + 1):
            body, truth = render_fixture(site, item)
            target = fixtures / site["id"] / f"item-{item}.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            fixture_manifest.append({
                "site": site["id"], "item": item, "url": truth["url"],
                "path": str(target.relative_to(output_root)),
                "sha256": hashlib.sha256(body.encode()).hexdigest(), "truth": truth,
            })
    (output_root / "fixture-manifest.json").write_text(
        json.dumps(fixture_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    source_metrics = write_integration_sources(catalog, output_root / "integrations" / "before")
    repaired = _repaired_catalog(catalog)
    after_metrics = write_integration_sources(repaired, output_root / "integrations" / "after")
    before_sources = integration_sources(catalog)
    after_sources = integration_sources(repaired)

    systems: dict[str, Any] = {}
    for system in SYSTEMS:
        system_result = {**source_metrics[system], **_score(system, catalog, documents_per_site)}
        system_result["drift"] = {
            mutation: _drift_score(system, catalog, mutation) for mutation in drift_cases
        }
        filename, before = before_sources[system]
        _, after = after_sources[system]
        system_result.update(_change_metrics(before, after))
        system_result["postRepair"] = {
            "sharedSelector": _drift_score(system, repaired, "shared_selector_rename"),
            "siteSelector": _drift_score(system, repaired, "site_selector_rename"),
        }
        system_result["afterSha256"] = after_metrics[system]["sha256"]
        system_result["capabilityBoundary"] = (
            "deterministic selector routing is evaluated in the client layer; live LLM extraction is not scored"
            if system == "firecrawl-client"
            else "registered deterministic user integration"
        )
        systems[system] = system_result

    # A literal from the first site is deliberately applied outside its scope.
    leak_pages = scoped_leaks = unscoped_leaks = 0
    first = catalog[0]
    for site in catalog[1:]:
        body, truth = render_fixture(site, 4)
        scoped, _ = _pulse_extract(first, truth["url"], body)
        get_engine = _core_engines()
        unscoped_rows = get_engine("css")(body, _mappings(first)[2][1])
        unscoped = unscoped_rows[0] if unscoped_rows else {}
        leak_pages += 1
        scoped_leaks += int(scoped.get("source_name") == first["sourceName"])
        unscoped_leaks += int(unscoped.get("source_name") == first["sourceName"])

    return {
        "status": "completed",
        "method": "generated-scoped-fixtures-with-equivalent-user-integrations",
        "corpusClassification": catalog_document["classification"],
        "sites": len(catalog),
        "documents": len(fixture_manifest),
        "fixtureManifestSha256": hashlib.sha256((output_root / "fixture-manifest.json").read_bytes()).hexdigest(),
        "systems": systems,
        "literalLeakAblation": {
            "pages": leak_pages,
            "scopedContaminationRate": scoped_leaks / leak_pages,
            "unscopedContaminationRate": unscoped_leaks / leak_pages,
        },
        "allSyntaxValid": all(row["syntaxCheck"] in {"json.loads", "ast.parse"} for row in systems.values()),
        "allBaselineF1Perfect": all(row["fieldF1"] == 1.0 for row in systems.values()),
        "allPostRepairAccurate": all(
            row["postRepair"][case]["fieldAccuracy"] == 1.0
            for row in systems.values()
            for case in ("sharedSelector", "siteSelector")
        ),
        "externalAccuracyBoundary": "controlled conformance only; T08 remains permission-gated",
    }
