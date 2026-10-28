# Statistical analysis

Phase: **confirmatory**
Measurements: 577
Metric groups: 456

Pilot, confirmatory, and remediation runs must not be pooled. Inspect `experiment.json` and the release manifest before publication.

## Crawl safety

| Experiment | System | Profile | Runs | Zero-violation runs | Mean HTTP requests | Mean duration (s) |
|---|---|---:|---:|---:|---:|---:|
| S01 | crawlee | default | 30 | 0 | 54.833 | 0.602 |
| S01 | crawlee | tuned | 30 | 29 | 50.033 | 0.940 |
| S01 | pulsecrawl | default | 30 | 30 | 49.000 | 11.198 |
| S01 | scrapy | default | 30 | 0 | 56.000 | 1.084 |
| S01 | scrapy | tuned | 30 | 0 | 56.000 | 1.024 |
| S04 | crawlee | default | 30 | 0 | 38.467 | 0.462 |
| S04 | pulsecrawl | default | 30 | 30 | 30.000 | 11.628 |
| S04 | scrapy | default | 30 | 0 | 32.000 | 0.708 |
| S07 | pulsecrawl | redelivery-cache-loss | 30 | 30 | 800.000 |  |

Safety compliance and performance are reported separately; a faster run that violates a configured invariant is not ranked as superior.

Unavailable profiles were excluded from compliance and performance totals: S01:firecrawl-local:default, S04:firecrawl-local:default.

## Safety mechanisms

| Experiment | Case | Runs | Zero-violation/recovery runs | Causal matches | Mean storage calls | Mean deferrals |
|---|---|---:|---:|---:|---:|---:|
| S02 | after_admission | 3 | 3 |  |  |  |
| S02 | after_commit | 3 | 3 |  |  |  |
| S02 | after_http | 3 | 3 |  |  |  |
| S02 | before_http | 3 | 3 |  |  |  |
| S02 | lifetime-budget | 3 | 3 |  |  |  |
| S03 | pulsecrawl | 30 | 30 |  |  |  |
| S05 | crawlby | 1 |  |  | 2000 | 0 |
| S05 | crawlby-final-gate | 1 |  |  | 2000 | 0 |
| S05 | queue-defer | 1 |  |  | 4000 | 984 |
| S05 | worker-sleep | 1 |  |  | 2000 | 984 |
| S06 | complete | 1 | 1 | 1 |  |  |
| S06 | without_durable_admission | 1 | 0 | 1 |  |  |
| S06 | without_final_dispatch_gate | 1 | 0 | 1 |  |  |
| S06 | without_lifetime_reservation | 1 | 0 | 1 |  |  |
| S06 | without_terminal_cleanup | 1 | 0 | 1 |  |  |
| S06 | without_terminal_guard | 1 | 0 | 1 |  |  |
| S07 | pulsecrawl | 30 | 30 |  |  |  |
| S08 | cache-loss-crawlby | 1 |  |  | 160860 |  |
| S08 | durable-only | 1 |  |  | 181500 |  |
| S08 | volatile-cache | 1 |  |  | 151140 |  |
| S08 | volatile-cache-crawlby | 1 |  |  | 140640 |  |

## Extraction

| Experiment | Strategy/case | Field F1/accuracy | Record coverage | Contamination |
|---|---|---:|---:|---:|
| T01 | generic | 0.6 | 1 | 0 |
| T01 | routed | 1 | 1 | 0 |
| T01 | scoped | 1 | 1 | 0 |
| T01 | unscoped | 1 | 1 | 0.933333 |
| T02 | scoped-plus-system-fallback |  | 1 |  |
| T03 | body_moved | 0.4 | 1 |  |
| T03 | class_renamed | 0.4 | 1 |  |
| T03 | jsonld_malformed | 1 | 1 |  |
| T03 | jsonld_removed | 1 | 1 |  |
| T03 | metadata_removed | 0.8 | 1 |  |
| T03 | multiple_entities | 0.4 | 1 |  |
| T04 | pulsecrawl-template-stack | 1 | 1 |  |
| T05 | beautifulsoup-reference | 1 |  |  |
| T05 | crawlee | 1 |  |  |
| T05 | firecrawl | 1 |  |  |
| T05 | pulsecrawl | 1 |  |  |
| T05 | scrapy | 1 |  |  |
| T06 | beautifulsoup-reference | 1 |  |  |
| T06 | crawlee | 1 |  |  |
| T06 | firecrawl | 1 |  |  |
| T06 | pulsecrawl | 1 |  |  |
| T06 | scrapy | 1 |  |  |
| T07 | canonical-completeness | 1 |  |  |
| T07 | first-entity | 0.5 |  |  |
| T09 | beautifulsoup-reference | 1 | 1 | 0 |
| T09 | crawlee-python | 1 | 1 | 0 |
| T09 | firecrawl-client | 1 | 1 | 0 |
| T09 | pulsecrawl | 1 | 1 | 0 |
| T09 | scrapy | 1 | 1 | 0 |
| T10 | beautifulsoup-reference | 1 | 1 | 0 |
| T10 | crawlee-python | 1 | 1 | 0 |
| T10 | firecrawl-client | 1 | 1 | 0 |
| T10 | pulsecrawl | 1 | 1 | 0 |
| T10 | scrapy | 1 | 1 | 0 |

## Data lake

| Experiment | Append-all rows | New-only rows | Snapshot violations | Unsafe-publication violations |
|---|---:|---:|---:|---:|
| D01 | 10000 | 1900 |  |  |
| D02 | 100000 | 5950 |  |  |
| D03 | 100000 | 10900 | 0 |  |
| D04 | 10000 | 1900 |  |  |
| D05 | 10000 | 1900 | 0 | 30 |
| D06 (1000000-rows) | 1e+06 | 19900 | 0 |  |
| D06 (10000000-rows) | 1e+07 | 199000 | 0 |  |
| D07 | 1e+06 | 19900 | 0 |  |
| D08 |  |  | 0 |  |
| D10 (governance-equivalent) |  |  | 0 |  |
| D10 (integration-burden) |  |  |  |  |
| D10 (long-term) | 1e+06 | 19900 | 0 |  |
| D10 (native-output) |  |  |  |  |
| D11 | 1000 | 100 | 0 |  |
