"""Run an idiomatic Crawlee for Python HTTP/HTML crawler."""
from __future__ import annotations

import asyncio
import json
import sys


async def execute(raw: dict) -> dict:
    import crawlee
    from crawlee import ConcurrencySettings
    from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

    processed = 0
    profile = __import__("os").environ.get("PULSECRAWL_RESEARCH_PROFILE", "default")
    concurrency = int(raw["concurrency"])
    settings = ConcurrencySettings(
        min_concurrency=1,
        desired_concurrency=concurrency,
        max_concurrency=concurrency,
        max_tasks_per_minute=(
            float(raw["requests_per_second"]) * 60 if profile == "tuned" else float("inf")
        ),
    )
    crawler = BeautifulSoupCrawler(
        max_requests_per_crawl=int(raw["max_urls"]),
        max_crawl_depth=int(raw["max_depth"]),
        respect_robots_txt_file=bool(raw["respect_robots"]),
        concurrency_settings=settings,
        configure_logging=False,
    )

    @crawler.router.default_handler
    async def handler(context: BeautifulSoupCrawlingContext) -> None:
        nonlocal processed
        processed += 1
        await context.enqueue_links()

    await crawler.run(list(raw["seed_urls"]))
    return {
        "systemVersion": getattr(crawlee, "__version__", None),
        "metrics": {"pagesFetched": processed},
        "errors": [],
    }


def main() -> int:
    print(json.dumps(asyncio.run(execute(json.load(sys.stdin)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
