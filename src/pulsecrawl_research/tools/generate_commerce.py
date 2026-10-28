"""Generate fictional commerce HTML observations without network access.

Adapted from PulseCrawl's controlled example; AGPL-3.0-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import hashlib
import json
from pathlib import Path

@dataclass(frozen=True)
class Source:
    slug: str
    store: str
    host: str
    paths: tuple[str, ...]
    sample_url: str
    terms_url: str


SOURCES = tuple(
    Source(f"shop-{i:02d}", f"Fictional Store {i:02d}", f"shop-{i:02d}.example",
           ("/products/*",), f"https://shop-{i:02d}.example/products/item-{i:02d}?color=black&size=m",
           f"https://shop-{i:02d}.example/policies")
    for i in range(1, 11)
)

def product_html(source: Source, execution: int, *, layout: str = "jsonld") -> str:
    """Prices/identifiers are fictional and do not describe the linked product."""
    if execution not in (0, 1):
        raise ValueError("controlled fixture has exactly two observations")
    price = "120.00" if execution == 0 else "99.00"
    name = f"SYNTHETIC {source.store} product - not a live price"
    url = escape(source.sample_url, quote=True)
    title = f'<meta property="og:title" content="{escape(name, quote=True)}">'
    if layout == "meta":
        return title + f'''<meta property="og:url" content="{url}">
        <meta property="product:price:amount" content="{price}">
        <meta property="product:price:currency" content="USD">'''
    if layout == "css":
        return title + f'''<main itemscope itemtype="https://schema.org/Product">
        <h1 itemprop="name">{escape(name)}</h1>
        <meta itemprop="price" content="{price}">
        <meta itemprop="priceCurrency" content="USD">
        <meta itemprop="sku" content="SYNTHETIC-{source.slug}-M-BLACK"></main>'''
    entity = {
        "@context": "https://schema.org", "@type": "Product", "name": name,
        "url": source.sample_url, "brand": {"name": "SYNTHETIC brand"},
        "productID": f"SYNTHETIC-{source.slug}", "sku": f"SYNTHETIC-{source.slug}-M-BLACK",
        "color": "SYNTHETIC Black", "size": "SYNTHETIC M",
        "offers": {"@type": "Offer", "price": price, "priceCurrency": "USD",
                   "url": source.sample_url, "availability": "https://schema.org/InStock"},
    }
    if layout == "range":
        entity["offers"] = {"@type": "AggregateOffer", "lowPrice": "80.00",
                            "highPrice": "150.00", "priceCurrency": "USD"}
    if layout not in ("jsonld", "graph", "range", "malformed"):
        raise ValueError("unknown controlled layout")
    data = {"@graph": [entity]} if layout == "graph" else entity
    script = "{ malformed" if layout == "malformed" else json.dumps(data)
    suffix = product_html(source, execution, layout="css") if layout == "malformed" else title
    return f'<script type="application/ld+json">{script}</script>' + suffix

def main() -> int:
    root = Path(__file__).resolve().parents[3] / "datasets" / "commerce-html"
    labels = []
    for execution in range(2):
        for source in SOURCES:
            body = product_html(source, execution)
            relative = Path("pages") / f"observation-{execution + 1}" / f"{source.slug}.html"
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body.encode("utf-8"))
            labels.append({
                "id": f"{source.slug}-{execution + 1}",
                "path": relative.as_posix(), "scopeUrl": source.sample_url,
                "storeContext": source.store, "observation": execution + 1,
                "observedAt": f"2026-10-11T{12 + execution:02d}:00:00+00:00",
                "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "truth": {
                    "name": f"SYNTHETIC {source.store} product - not a live price",
                    "brand": "SYNTHETIC brand",
                    "sku": f"SYNTHETIC-{source.slug}-M-BLACK",
                    "product_id": f"SYNTHETIC-{source.slug}",
                    "current_price": 120.0 if execution == 0 else 99.0,
                    "currency": "USD", "color": "SYNTHETIC Black",
                    "size": "SYNTHETIC M",
                    "availability": "https://schema.org/InStock",
                    "product_url": source.sample_url,
                },
                "license": "AGPL-3.0-only", "liveEnabled": False,
                "provenance": "original-synthetic-fictional-price-observation",
            })
    (root / "manifest.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in labels),
        encoding="utf-8",
    )
    print(f"Generated {len(labels)} fictional commerce observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
