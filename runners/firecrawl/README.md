# Firecrawl comparator

This adapter runs the upstream Firecrawl `v2.9.0` checkout at commit
`11490b52b46b35423548df809c966d51463ec49d`. Firecrawl is an external AGPL
service and is not vendored into PulseCrawl.

```bash
sh research/baselines/firecrawl/run.sh
sh research/baselines/firecrawl/stop.sh
```

`run.sh` refuses to start unless every service in the resolved Docker Compose
configuration uses the `none` logging driver. This is a cost and privacy guard:
benchmark output is recorded by the research harness, while container stdout
is deliberately not persisted. The override also allows only the local
WebBench destination needed by this controlled experiment; do not copy those
settings to a public deployment.

The release report must retain Firecrawl failures and unavailable results. A
failed comparator is never silently replaced by zero, and no result implies
that a differently configured or extended Firecrawl deployment cannot provide
the behavior under test.
