"""Deterministic, observable HTTP websites for crawler research.

This is a real HTTP server, not a mocked fetcher. It generates virtual news,
job, and product sites with known URL graphs and extraction ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import random
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


PROFILES = {
    "smoke": 50,
    "small": 1_000,
    "standard": 10_000,
    "large": 100_000,
    "extreme": 1_000_000,
}
VERTICALS = ("news", "jobs", "products")
LAYOUTS = ("jsonld", "metadata", "css", "nested", "malformed")


@dataclass(frozen=True)
class WebBenchConfig:
    items_per_site: int = 50
    sites_per_vertical: int = 20
    seed: int = 4703
    epoch: int = 1
    page_size: int = 20
    crawl_delay_seconds: float = 0.0
    include_fault_links: bool = False
    trace_path: str | None = None

    def __post_init__(self) -> None:
        if self.items_per_site < 1:
            raise ValueError("items_per_site must be positive")
        if not 1 <= self.sites_per_vertical <= 100:
            raise ValueError("sites_per_vertical must be between 1 and 100")
        if self.page_size < 1:
            raise ValueError("page_size must be positive")
        if self.epoch < 1:
            raise ValueError("epoch must be positive")


class BenchmarkState:
    def __init__(self, config: WebBenchConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._trace: list[dict[str, Any]] = []

    def observe(
        self,
        *,
        method: str,
        path: str,
        host: str,
        user_agent: str,
        kind: str,
        status: int,
        received_at_ns: int | None = None,
    ) -> None:
        row = {
            "kind": kind,
            "method": method,
            "path": path,
            "host": host,
            "userAgent": user_agent,
            "status": status,
            "receivedAtNs": received_at_ns if received_at_ns is not None else time.time_ns(),
        }
        with self._lock:
            self._trace.append(row)
            trace_path = self.config.trace_path
            if trace_path:
                target = Path(trace_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")

    def trace(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._trace]

    def reset(self) -> None:
        with self._lock:
            self._trace.clear()
            if self.config.trace_path:
                Path(self.config.trace_path).unlink(missing_ok=True)

    def site(self, vertical: str, site_number: int) -> "VirtualSite":
        if vertical not in VERTICALS:
            raise KeyError(vertical)
        if not 1 <= site_number <= self.config.sites_per_vertical:
            raise KeyError(site_number)
        return VirtualSite(self.config, vertical, site_number)

    def ground_truth(self) -> dict[str, Any]:
        site_count = len(VERTICALS) * self.config.sites_per_vertical
        return {
            "schemaVersion": 1,
            "seed": self.config.seed,
            "epoch": self.config.epoch,
            "verticals": list(VERTICALS),
            "sitesPerVertical": self.config.sites_per_vertical,
            "itemsPerSite": self.config.items_per_site,
            "siteCount": site_count,
            "itemCount": site_count * self.config.items_per_site,
            "layouts": list(LAYOUTS),
            "faultLinks": self.config.include_fault_links,
        }


class VirtualSite:
    categories = 10
    subcategories = 10

    def __init__(self, config: WebBenchConfig, vertical: str, number: int) -> None:
        self.config = config
        self.vertical = vertical
        self.number = number
        self.site_id = f"{vertical}-{number:02d}"
        self.layout = LAYOUTS[(number - 1) % len(LAYOUTS)]

    @property
    def prefix(self) -> str:
        return f"/site/{self.vertical}/{self.number:02d}"

    def _random(self, *parts: object) -> random.Random:
        material = ":".join(str(value) for value in (self.config.seed, *parts))
        digest = hashlib.sha256(material.encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def item(self, item_id: int) -> dict[str, Any]:
        if not 1 <= item_id <= self.config.items_per_site:
            raise KeyError(item_id)
        category = (item_id - 1) % self.categories
        subcategory = ((item_id - 1) // self.categories) % self.subcategories
        published = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(
            minutes=item_id + self.config.epoch * 10_000
        )
        rng = self._random(self.site_id, item_id, self.config.epoch)
        base = {
            "id": item_id,
            "url": f"{self.prefix}/item/{item_id:07d}",
            "category": f"category-{category:02d}",
            "subcategory": f"subcategory-{subcategory:02d}",
            "publishedAt": published.isoformat(),
            "modifiedAt": (
                published + timedelta(hours=self.config.epoch - 1)
            ).isoformat(),
            "site": self.site_id,
            "layout": self.layout,
        }
        if self.vertical == "news":
            base.update(
                title=f"{self.site_id} report {item_id}",
                body=f"Verified article body {item_id} token {rng.randrange(1_000_000):06d}.",
                author=f"Reporter {(item_id % 17) + 1}",
                kind="NewsArticle",
            )
        elif self.vertical == "jobs":
            base.update(
                title=f"Software role {item_id}",
                body=f"Job description {item_id} token {rng.randrange(1_000_000):06d}.",
                author=f"Company {(item_id % 13) + 1}",
                kind="JobPosting",
                location=f"Region {(item_id % 8) + 1}",
            )
        else:
            base.update(
                title=f"Product {item_id}",
                body=f"Product description {item_id} token {rng.randrange(1_000_000):06d}.",
                author=f"Brand {(item_id % 11) + 1}",
                kind="Product",
                price=round(10 + (item_id % 500) * 1.17, 2),
                currency="USD",
            )
        return base

    def featured(self, count: int = 12) -> list[int]:
        population = range(1, self.config.items_per_site + 1)
        count = min(count, self.config.items_per_site)
        return self._random(self.site_id, "featured", self.config.epoch).sample(
            population, count
        )

    def items_for(self, category: int, subcategory: int) -> list[int]:
        if not (0 <= category < self.categories and 0 <= subcategory < self.subcategories):
            return []
        first = 1 + category + self.categories * subcategory
        stride = self.categories * self.subcategories
        return list(range(first, self.config.items_per_site + 1, stride))

    def render_item(self, item_id: int) -> str:
        item = self.item(item_id)
        canonical = item["url"]
        escaped_title = html.escape(str(item["title"]))
        escaped_body = html.escape(str(item["body"]))
        schema = {
            "@context": "https://schema.org",
            "@type": item["kind"],
            "name": item["title"],
            "headline": item["title"],
            "description": item["body"],
            "articleBody": item["body"],
            "datePublished": item["publishedAt"],
            "dateModified": item["modifiedAt"],
            "author": {"@type": "Person", "name": item["author"]},
            "url": canonical,
        }
        if self.vertical == "jobs":
            schema["jobLocation"] = {
                "@type": "Place",
                "address": item["location"],
            }
        if self.vertical == "products":
            schema["offers"] = {
                "@type": "Offer",
                "price": item["price"],
                "priceCurrency": item["currency"],
            }
        jsonld = json.dumps(schema, separators=(",", ":"))
        head = [
            "<meta charset='utf-8'>",
            f"<title>{escaped_title}</title>",
            f"<link rel='canonical' href='{html.escape(canonical)}'>",
            f"<meta property='article:published_time' content='{item['publishedAt']}'>",
        ]
        body_class = f"content-{self.number:02d}"
        body_markup = (
            f"<article data-site='{self.site_id}'><h1>{escaped_title}</h1>"
            f"<div class='{body_class}'>{escaped_body}</div>"
            f"<a href='{self.prefix}/item/{max(1, item_id - 1):07d}'>Previous</a>"
            f"<a href='{self.prefix}/item/{min(self.config.items_per_site, item_id + 1):07d}'>Next</a>"
            "</article>"
        )
        if self.layout == "jsonld":
            head.append(f"<script type='application/ld+json'>{jsonld}</script>")
        elif self.layout == "metadata":
            head.extend(
                [
                    f"<meta property='og:title' content='{escaped_title}'>",
                    f"<meta property='og:description' content='{escaped_body}'>",
                ]
            )
            body_markup = f"<main><h1>{escaped_title}</h1><p>{escaped_body}</p></main>"
        elif self.layout == "nested":
            head.append(
                "<script type='application/ld+json'>"
                + json.dumps({"payload": {"entity": schema}}, separators=(",", ":"))
                + "</script>"
            )
        elif self.layout == "malformed":
            head.append(f"<script type='application/ld+json'>{jsonld[:-1]},</script>")
        return (
            "<!doctype html><html><head>"
            + "".join(head)
            + "</head><body>"
            + body_markup
            + "</body></html>"
        )


def _site_from_path(state: BenchmarkState, path: str) -> tuple[VirtualSite, list[str]]:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0] != "site":
        raise KeyError(path)
    site = state.site(parts[1], int(parts[2]))
    return site, parts[3:]


def _links(values: list[tuple[str, str]]) -> str:
    return "".join(
        f"<li><a href='{html.escape(url)}'>{html.escape(label)}</a></li>"
        for label, url in values
    )


def _handler(state: BenchmarkState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PulseCrawlWebBench/1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send(
            self,
            status: int,
            body: str,
            content_type: str = "text/html; charset=utf-8",
            *,
            kind: str = "request",
            headers: dict[str, str] | None = None,
        ) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(encoded)
            if not self.path.startswith("/__"):
                state.observe(
                    method=self.command,
                    path=urlparse(self.path).path,
                    host=self.headers.get("Host", ""),
                    user_agent=self.headers.get("User-Agent", ""),
                    kind=kind,
                    status=status,
                    received_at_ns=getattr(self, "_request_started_ns", None),
                )

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_POST(self) -> None:  # noqa: N802
            self._request_started_ns = time.time_ns()
            parsed = urlparse(self.path)
            if parsed.path == "/__reset__" and self.client_address[0] in {
                "127.0.0.1",
                "::1",
            }:
                state.reset()
                self._send(HTTPStatus.NO_CONTENT, "", "text/plain")
                return
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            self._request_started_ns = time.time_ns()
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/__health__":
                self._send(HTTPStatus.OK, json.dumps({"status": "ok"}), "application/json")
                return
            if path == "/__trace__" and self.client_address[0] in {"127.0.0.1", "::1"}:
                self._send(HTTPStatus.OK, json.dumps(state.trace()), "application/json")
                return
            if path == "/__ground_truth__":
                self._send(
                    HTTPStatus.OK,
                    json.dumps(state.ground_truth(), sort_keys=True),
                    "application/json",
                )
                return
            if path == "/robots.txt":
                delay = state.config.crawl_delay_seconds
                text = "User-agent: *\nDisallow: /blocked/\n"
                if delay > 0:
                    text += f"Crawl-delay: {delay:g}\n"
                text += "Sitemap: /sitemap.xml\n"
                self._send(HTTPStatus.OK, text, "text/plain; charset=utf-8", kind="robots")
                return
            if path == "/sitemap.xml":
                urls = [
                    f"/site/{vertical}/{number:02d}/sitemap.xml"
                    for vertical in VERTICALS
                    for number in range(1, state.config.sites_per_vertical + 1)
                ]
                body = "<?xml version='1.0'?><sitemapindex>" + "".join(
                    f"<sitemap><loc>{html.escape(url)}</loc></sitemap>" for url in urls
                ) + "</sitemapindex>"
                self._send(HTTPStatus.OK, body, "application/xml")
                return
            if path == "/fault/":
                links = [
                    ("HTTP 404", "/fault/status/404"),
                    ("HTTP 429", "/fault/status/429"),
                    ("HTTP 500", "/fault/status/500"),
                    ("Delayed response", "/fault/delay/50"),
                ]
                self._send(
                    HTTPStatus.OK,
                    "<!doctype html><title>Fault cases</title><ul>"
                    + _links(links)
                    + "</ul>",
                )
                return
            if path.startswith("/fault/status/"):
                status = int(path.rsplit("/", 1)[-1])
                self._send(status, f"status {status}", "text/plain")
                return
            if path.startswith("/fault/delay/"):
                milliseconds = min(5_000, max(0, int(path.rsplit("/", 1)[-1])))
                time.sleep(milliseconds / 1_000)
                self._send(HTTPStatus.OK, f"delayed {milliseconds}", "text/plain")
                return
            if path.startswith("/redirect/"):
                target = "/" + path.split("/", 2)[-1]
                self._send(
                    HTTPStatus.FOUND,
                    "redirect",
                    "text/plain",
                    headers={"Location": target},
                )
                return
            if path.startswith("/blocked/"):
                self._send(HTTPStatus.OK, "robots should prevent this request", "text/plain")
                return
            if path == "/":
                values = [
                    (
                        f"{vertical}-{number:02d}",
                        f"/site/{vertical}/{number:02d}/",
                    )
                    for vertical in VERTICALS
                    for number in range(1, state.config.sites_per_vertical + 1)
                ]
                body = (
                    "<!doctype html><title>PulseCrawl WebBench</title>"
                    "<h1>Deterministic benchmark websites</h1><ul>"
                    + _links(values)
                    + "</ul>"
                )
                self._send(HTTPStatus.OK, body)
                return
            try:
                site, remainder = _site_from_path(state, path)
                self._serve_site(site, remainder, parse_qs(parsed.query))
            except (KeyError, ValueError):
                self._send(HTTPStatus.NOT_FOUND, "not found", "text/plain")

        def _site_home(self, site: VirtualSite) -> str:
            links: list[tuple[str, str]] = []
            if state.config.include_fault_links:
                links.extend(
                    [
                        ("Redirect", f"/redirect{site.prefix}/item/0000001"),
                        ("HTTP 404", "/fault/status/404"),
                        ("HTTP 429", "/fault/status/429"),
                        ("HTTP 500", "/fault/status/500"),
                        ("Delayed response", "/fault/delay/50"),
                    ]
                )
            links.extend(
                [
                    (f"Category {category}", f"{site.prefix}/category/{category:02d}/")
                    for category in range(site.categories)
                ]
            )
            links.extend(
                (f"Featured {item_id}", f"{site.prefix}/item/{item_id:07d}")
                for item_id in site.featured()
            )
            links.extend(
                [
                    ("Sitemap", f"{site.prefix}/sitemap.xml"),
                    ("Robots-blocked canary", "/blocked/canary"),
                ]
            )
            if state.config.include_fault_links:
                # A terminal hub makes the case reachable for both FIFO and
                # LIFO schedulers; the direct links above do the same for FIFO.
                links.append(("Fault-case hub", "/fault/"))
            return (
                f"<!doctype html><title>{site.site_id}</title>"
                f"<h1>{site.site_id}</h1><p>layout={site.layout}</p><ul>"
                + _links(links)
                + "</ul>"
            )

        def _serve_category(self, site: VirtualSite, remainder: list[str]) -> None:
            if len(remainder) == 2:
                category = int(remainder[1])
                if not 0 <= category < site.categories:
                    raise KeyError(category)
                links = [
                    (
                        f"Subcategory {subcategory}",
                        f"{site.prefix}/category/{category:02d}/{subcategory:02d}/page/1",
                    )
                    for subcategory in range(site.subcategories)
                ]
                self._send(
                    HTTPStatus.OK,
                    f"<!doctype html><h1>Category {category}</h1><ul>{_links(links)}</ul>",
                )
                return
            if len(remainder) == 5 and remainder[3] == "page":
                category = int(remainder[1])
                subcategory = int(remainder[2])
                page = int(remainder[4])
                if not (0 <= category < site.categories and 0 <= subcategory < site.subcategories):
                    raise KeyError((category, subcategory))
                all_items = site.items_for(category, subcategory)
                pages = max(1, math.ceil(len(all_items) / site.config.page_size))
                if not 1 <= page <= pages:
                    raise KeyError(page)
                start = (page - 1) * site.config.page_size
                selected = all_items[start : start + site.config.page_size]
                links = [
                    (f"Item {item_id}", f"{site.prefix}/item/{item_id:07d}")
                    for item_id in selected
                ]
                if page < pages:
                    links.append(
                        (
                            "Next page",
                            f"{site.prefix}/category/{category:02d}/{subcategory:02d}/page/{page + 1}",
                        )
                    )
                self._send(
                    HTTPStatus.OK,
                    f"<!doctype html><h1>Listing {category}/{subcategory}</h1><ul>{_links(links)}</ul>",
                )
                return
            raise KeyError(remainder)

        def _sitemap_chunk(self, site: VirtualSite, chunk: int) -> str:
            start = chunk * 50_000 + 1
            stop = min(site.config.items_per_site, (chunk + 1) * 50_000)
            return "<?xml version='1.0'?><urlset>" + "".join(
                f"<url><loc>{site.prefix}/item/{item_id:07d}</loc></url>"
                for item_id in range(start, stop + 1)
            ) + "</urlset>"

        # Special-case site roots before generic path parsing loses the trailing slash.
        def _serve_site(
            self, site: VirtualSite, remainder: list[str], query: dict[str, list[str]]
        ) -> None:
            if not remainder and self.path.endswith("/"):
                self._send(HTTPStatus.OK, self._site_home(site))
                return
            return self._serve_site_nonroot(site, remainder, query)

        def _serve_site_nonroot(
            self, site: VirtualSite, remainder: list[str], query: dict[str, list[str]]
        ) -> None:
            del query
            if not remainder:
                self._send(
                    HTTPStatus.PERMANENT_REDIRECT,
                    "redirect",
                    "text/plain",
                    headers={"Location": f"{site.prefix}/"},
                )
                return
            if remainder == ["sitemap.xml"]:
                chunks = math.ceil(site.config.items_per_site / 50_000)
                body = (
                    "<?xml version='1.0'?><sitemapindex>"
                    + "".join(
                        f"<sitemap><loc>{site.prefix}/sitemap-{chunk}.xml</loc></sitemap>"
                        for chunk in range(chunks)
                    )
                    + "</sitemapindex>"
                    if chunks > 1
                    else self._sitemap_chunk(site, 0)
                )
                self._send(HTTPStatus.OK, body, "application/xml")
                return
            if len(remainder) == 1 and remainder[0].startswith("sitemap-"):
                chunk = int(remainder[0].removeprefix("sitemap-").removesuffix(".xml"))
                if chunk < 0 or chunk >= math.ceil(site.config.items_per_site / 50_000):
                    raise KeyError(chunk)
                self._send(HTTPStatus.OK, self._sitemap_chunk(site, chunk), "application/xml")
                return
            if remainder == ["ground-truth.json"]:
                self._send(
                    HTTPStatus.OK,
                    json.dumps(
                        {
                            "siteId": site.site_id,
                            "vertical": site.vertical,
                            "layout": site.layout,
                            "items": site.config.items_per_site,
                            "epoch": site.config.epoch,
                        },
                        sort_keys=True,
                    ),
                    "application/json",
                )
                return
            if remainder[0] == "item" and len(remainder) == 2:
                self._send(HTTPStatus.OK, site.render_item(int(remainder[1])))
                return
            if remainder[0] == "category":
                self._serve_category(site, remainder)
                return
            raise KeyError(remainder)

    return Handler


class WebBenchServer:
    """Context-managed web benchmark used by experiments and tests."""

    def __init__(
        self,
        config: WebBenchConfig | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.state = BenchmarkState(config or WebBenchConfig())
        self.httpd = ThreadingHTTPServer((host, port), _handler(self.state))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "WebBenchServer":
        self.thread.start()
        return self

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def __enter__(self) -> "WebBenchServer":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="small")
    parser.add_argument("--items-per-site", type=int)
    parser.add_argument("--sites-per-vertical", type=int, default=20)
    parser.add_argument("--seed", type=int, default=4703)
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--crawl-delay", type=float, default=0.0)
    parser.add_argument(
        "--fault-links",
        action="store_true",
        help="link deterministic redirects, HTTP failures, and delay endpoints from site homes",
    )
    parser.add_argument("--trace")
    args = parser.parse_args(argv)
    config = WebBenchConfig(
        items_per_site=args.items_per_site or PROFILES[args.profile],
        sites_per_vertical=args.sites_per_vertical,
        seed=args.seed,
        epoch=args.epoch,
        crawl_delay_seconds=args.crawl_delay,
        include_fault_links=args.fault_links,
        trace_path=args.trace,
    )
    server = WebBenchServer(config, args.host, args.port).start()
    print(json.dumps({"baseUrl": server.base_url, **server.state.ground_truth()}))
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
