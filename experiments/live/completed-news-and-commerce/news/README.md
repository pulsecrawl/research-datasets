# News study: 48 recurring cycles

This study ran PulseCrawl every 30 minutes for 48 cycles against five public
news websites. All five site configurations completed every scheduled cycle.

## Study identity

| Identifier | Value |
| --- | --- |
| Study ID | `news` |
| Retained run ID | `20261026T062242Z-l01-59f95fc5` |
| Schedule | Every 30 minutes |
| Planned and completed cycles | 48 of 48 |
| Website configurations | 5 |

## Websites evaluated

| Website | Site ID | Domain | Executions | Pages fetched | Records extracted | Published rows |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Norte Digital | `norte-digital` | `nortedigital.mx` | 48 | 384 | 336 | 32 |
| La Verdad Juárez | `la-verdad-juarez` | `laverdadjuarez.com` | 48 | 384 | 336 | 7 |
| Raíchali | `raichali` | `raichali.com` | 48 | 384 | 336 | 9 |
| La Opción de Chihuahua | `la-opcion` | `laopcion.com.mx` | 48 | 384 | 336 | 67 |
| Tiempo | `tiempo` | `tiempo.com.mx` | 48 | 384 | 336 | 88 |
| **Total** |  |  | **240** | **1,920** | **1,680** | **203** |

**Records extracted** counts records produced during all executions.
**Published rows** counts rows retained by the study's new-URL publication
policy, so a URL seen again in a later cycle does not create another published
row. The 83 published executions are the site executions that added at least
one new row to the dataset.

The exact seed URLs and the mapping from website names to site IDs are in
[`sources.json`](sources.json).

## Aggregate outcome

| Measurement | Result |
| --- | ---: |
| Planned cycles | 48 |
| Completed cycles | 48 |
| Pages fetched | 1,920 |
| Pages failed | 0 |
| Records extracted | 1,680 |
| Published rows | 203 |
| Published executions | 83 |
| Transient retries | 0 |
| Robots fetch failures | 0 |

## How to read the files

- [`sources.json`](sources.json) answers **which websites and identifiers were
  used?**
- [`summary.json`](summary.json) answers **what aggregate activity was
  recorded?**
- [`manifest.json`](manifest.json) answers **what was published or omitted?**
- [`checksums.sha256`](checksums.sha256) answers **have the published JSON files
  changed?**

Website screenshots and downloaded pages are not included because these were
external sites. Only the aggregate operational evidence and public source
identifiers are published.
