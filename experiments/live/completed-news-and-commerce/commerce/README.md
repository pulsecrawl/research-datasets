# Commerce study: eight recurring cycles

This study ran PulseCrawl once per hour for eight cycles against one Alo Yoga
product page. The page was requested directly during each cycle; a generated
page was not substituted for it.

## Study identity

| Identifier | Value |
| --- | --- |
| Study ID | `commerce` |
| Retained run ID | `20261026T062448Z-l02-5b82bc4b` |
| Site ID | `alo-airlift` |
| Website | Alo Yoga |
| Domain | `aloyoga.com` |
| Schedule | Once per hour |
| Planned and completed cycles | 8 of 8 |

The exact evaluated product URL and the identifier mapping are in
[`sources.json`](sources.json).

## Aggregate outcome

| Measurement | Result |
| --- | ---: |
| Planned cycles | 8 |
| Completed cycles | 8 |
| Pages fetched | 8 |
| Pages failed | 0 |
| Records extracted | 8 |
| Published rows | 8 |
| Published executions | 8 |
| Transient retries | 0 |
| Robots fetch failures | 0 |

Each completed cycle produced one structured observation containing the
available product name, price, currency, source URL, and observation time.

## How to read the files

- [`sources.json`](sources.json) answers **which website, URL, and identifiers
  were used?**
- [`summary.json`](summary.json) answers **what aggregate activity was
  recorded?**
- [`manifest.json`](manifest.json) answers **what was published or omitted?**
- [`checksums.sha256`](checksums.sha256) answers **have the published JSON files
  changed?**

The public artifact does not contain the downloaded product page, product
description, image, or record-level review file. It demonstrates the bounded
execution outcome without republishing third-party page content.
