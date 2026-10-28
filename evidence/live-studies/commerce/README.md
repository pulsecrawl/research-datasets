# Commerce study: eight recurring cycles

This retained study exercised PulseCrawl hourly for eight cycles on one
eligible product page. Ten sources were considered and nine remained excluded
after access review. An excluded source was not replaced with synthetic data
and reported as a live result.

## Aggregate result

| Measurement | Result |
| --- | ---: |
| Planned cycles | 8 |
| Completed cycles | 8 |
| Eligible product pages | 1 |
| Pages fetched | 8 |
| Pages failed | 0 |
| Records extracted | 8 |
| Materialized rows | 8 |
| Published executions | 8 |
| Transient retries | 0 |
| Robots fetch failures | 0 |

## How to read the files

- [`summary.json`](summary.json) contains aggregate run and site counters.
- [`manifest.json`](manifest.json) identifies the retained summary by checksum
  and lists material intentionally excluded from publication.
- [`checksums.sha256`](checksums.sha256) detects changes to the published files.

The public artifact does not contain the downloaded product page, product
description, image, or record-level review file. It therefore demonstrates the
bounded execution outcome without republishing third-party page content.
