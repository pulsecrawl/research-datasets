"""Generate the author-owned, checksummed 60-document controlled corpus."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "datasets" / "fixed-html"
OUTPUT = ROOT / "expanded"
VERTICALS = {
    "news": ("NewsArticle", "headline", "articleBody", "datePublished"),
    "jobs": ("JobPosting", "title", "description", "datePosted"),
    "products": ("Product", "name", "description", "releaseDate"),
}
LAYOUTS = ("jsonld", "meta", "css", "graph", "malformed-with-css")


def document(vertical: str, number: int, layout: str) -> tuple[str, str, dict, dict]:
    kind, title_field, body_field, date_field = VERTICALS[vertical]
    title = f"Controlled {vertical} title {number:02d}"
    body = f"Author-owned {vertical} body {number:02d}."
    published = f"2026-01-{number:02d}T12:00:00+00:00"
    truth = {"title": title, "body": body, "published_at": published}
    entity = {"@context": "https://schema.org", "@type": kind, title_field: title, body_field: body, date_field: published}
    if layout in {"jsonld", "graph"}:
        payload = entity if layout == "jsonld" else {"@context": "https://schema.org", "@graph": [entity]}
        body_html = f"<script type='application/ld+json'>{json.dumps(payload, sort_keys=True)}</script>"
        engine = "jsonld"
        mappings = {"title": [f"{kind}.{title_field}"], "body": [f"{kind}.{body_field}"], "published_at": [f"{kind}.{date_field}"]}
    elif layout == "meta":
        body_html = "".join([
            f"<meta property='og:title' content='{html.escape(title)}'>",
            f"<meta property='og:description' content='{html.escape(body)}'>",
            f"<meta property='article:published_time' content='{published}'>",
        ])
        engine = "meta"
        mappings = {"title": ["og:title"], "body": ["og:description"], "published_at": ["article:published_time"]}
    else:
        malformed = "<script type='application/ld+json'>{broken,}</script>" if layout == "malformed-with-css" else ""
        body_html = malformed + f"<h1 class='headline-{number:02d}'>{html.escape(title)}</h1><div class='body-{number:02d}'>{html.escape(body)}</div><time datetime='{published}'></time>"
        engine = "css"
        mappings = {"title": [f"h1.headline-{number:02d}"], "body": [f"div.body-{number:02d}"], "published_at": ["time@datetime"]}
    complete = f"<!doctype html><html><head><title>{html.escape(title)}</title></head><body>{body_html}</body></html>\n"
    return complete, engine, mappings, truth


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for vertical in VERTICALS:
        for number in range(1, 21):
            layout = LAYOUTS[(number - 1) % len(LAYOUTS)]
            content, engine, mappings, truth = document(vertical, number, layout)
            relative = Path("expanded") / f"{vertical}-{number:02d}-{layout}.html"
            target = ROOT / relative
            target.write_text(content, encoding="utf-8")
            rows.append({
                "id": f"{vertical}-{number:02d}-{layout}", "vertical": vertical,
                "layout": layout, "path": relative.as_posix(),
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "engine": engine, "mappings": mappings, "truth": truth,
                "license": "CC0-1.0", "provenance": "original-synthetic-author-owned",
                "capturedAt": "2026-08-26T00:00:00Z",
                "sourceUrl": f"webbench://{vertical}/{number:02d}/{layout}",
                "robotsAccess": "owned-controlled-benchmark",
                "redistributionPermission": "author-owned-CC0-1.0",
            })
    manifest = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    (ROOT / "manifest.jsonl").write_text(manifest, encoding="utf-8")
    print(f"generated {len(rows)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
