"""Generate original baseline HTML using PulseCrawl site-pattern fixtures.

Adapted from PulseCrawl research tooling; AGPL-3.0-only.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

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
    if mutation == "site_selector_rename" and site["id"] == "news-laopcion":
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


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "datasets" / "site-pattern-html"
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    labels = []
    layouts = ("jsonld", "graph", "meta", "css", "malformed-with-css")
    for site in catalog["sites"]:
        for item in range(1, 6):
            body, truth = render_fixture(site, item)
            relative = Path("pages") / site["id"] / f"item-{item}.html"
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body.encode("utf-8"))
            labels.append({
                "id": f"{site['id']}-{item}", "siteId": site["id"],
                "path": relative.as_posix(), "layout": layouts[item - 1],
                "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "truth": truth, "license": "CC0-1.0",
                "provenance": "original-synthetic-site-pattern-baseline",
                "notLiveCapture": True,
            })
    (root / "manifest.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in labels),
        encoding="utf-8",
    )
    print(f"Generated {len(labels)} site-pattern HTML pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
