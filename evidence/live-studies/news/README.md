# News study: 48 recurring cycles

This retained study exercised PulseCrawl every 30 minutes for 48 cycles. Five
of seven requested news sites were eligible for execution; two remained
excluded by the study's access review.

## Aggregate result

| Measurement | Result |
| --- | ---: |
| Planned cycles | 48 |
| Completed cycles | 48 |
| Eligible sites | 5 |
| Pages fetched | 1,920 |
| Pages failed | 0 |
| Records extracted | 1,680 |
| Materialized rows | 203 |
| Published executions | 83 |
| Transient retries | 0 |
| Robots fetch failures | 0 |

The five site summaries each report 48 successful executions. The aggregate
summary also retains discovery, request-control, robots-cache, and byte-count
measurements so that the practical workload can be inspected without
publishing page bodies or article records.

## How to read the files

- [`summary.json`](summary.json) contains the aggregate run and per-site
  counters.
- [`manifest.json`](manifest.json) identifies the retained summary by checksum
  and lists material intentionally excluded from publication.
- [`checksums.sha256`](checksums.sha256) detects changes to the published files.

Website screenshots are not included because these were external sites. Only
the aggregate operational evidence is public.
