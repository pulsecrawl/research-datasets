"""Run a minimal, idiomatic Scrapy spider for the common benchmark."""
from __future__ import annotations

import json
import sys


def main() -> int:
    import scrapy
    from scrapy.crawler import CrawlerProcess
    from scrapy.linkextractors import LinkExtractor

    raw = json.load(sys.stdin)
    profile = __import__("os").environ.get("PULSECRAWL_RESEARCH_PROFILE", "default")

    class ResearchSpider(scrapy.Spider):
        name = "pulsecrawl-research"
        start_urls = list(raw["seed_urls"])
        extractor = LinkExtractor()

        def parse(self, response):
            yield {"url": response.url, "title": response.css("title::text").get()}
            for link in self.extractor.extract_links(response):
                yield response.follow(link.url, callback=self.parse)

    settings = {
        "LOG_ENABLED": False,
        "ROBOTSTXT_OBEY": bool(raw["respect_robots"]),
        "DEPTH_LIMIT": int(raw["max_depth"]),
        "CONCURRENT_REQUESTS": int(raw["concurrency"]),
        "CONCURRENT_REQUESTS_PER_DOMAIN": int(raw["concurrency"]),
        "DOWNLOAD_DELAY": 1 / float(raw["requests_per_second"]),
        "CLOSESPIDER_PAGECOUNT": int(raw["max_urls"]),
        "TELNETCONSOLE_ENABLED": False,
        "USER_AGENT": "ScrapyPulseCrawlResearch/0.1",
    }
    if profile == "default":
        settings.pop("CONCURRENT_REQUESTS_PER_DOMAIN")
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(ResearchSpider)
    process.crawl(crawler)
    process.start()
    stats = crawler.stats.get_stats()
    print(
        json.dumps(
            {
                "systemVersion": scrapy.__version__,
                "metrics": {
                    "pagesFetched": stats.get("downloader/response_count", 0),
                    "itemsScraped": stats.get("item_scraped_count", 0),
                    "duplicatesFiltered": stats.get("dupefilter/filtered", 0),
                    "finishReason": stats.get("finish_reason"),
                },
                "errors": [],
            },
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
