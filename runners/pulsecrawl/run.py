"""Run the real PulseCrawl local API and emit normalized JSON."""
from __future__ import annotations

import json
import sys
from pulsecrawl import __version__, crawl


def main() -> int:
    raw = json.load(sys.stdin)
    result = crawl(
        raw["seed_urls"],
        templates=[
            {
                "template_id": "research-meta",
                "engine": "meta",
                "mappings": {
                    "title": ["og:title", "<title>"],
                    "description": ["og:description", "description"],
                },
            }
        ],
        fields=[
            {"fieldId": "title", "name": "title", "type": "string"},
            {"fieldId": "description", "name": "description", "type": "string"},
        ],
        scope={
            "maxDepth": raw["max_depth"],
            "maxUrlsPerExecution": raw["max_urls"],
            "sameDomainOnly": True,
        },
        politeness={
            "respectRobotsTxt": raw["respect_robots"],
            "requestsPerSecond": raw["requests_per_second"],
            "organizationRequestsPerSecond": raw["requests_per_second"],
            "userAgent": "PulseCrawlResearch/0.1",
        },
        # WebBench is an explicitly controlled loopback fixture. Production
        # and user-supplied targets keep the default non-public-IP block.
        allow_private_networks=True,
    )
    print(
        json.dumps(
            {
                "systemVersion": __version__,
                "metrics": {**result.stats, "records": len(result.records)},
                "errors": [],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
