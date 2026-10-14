# Versioned dataset protocol

## Question

Can repeated local crawl outputs be published as consistent dataset versions,
queried by time and URL identity, and compacted without exposing partial
replacement files?

## Controlled inputs

The storage generator creates deterministic execution batches with repeated
and newly observed URL identities. The retained 1,000-row sample supports fast
verification; larger workloads are generated outside Git from the registered
configuration.

## Measurements

- expected and observed row counts;
- canonical semantic checksums;
- version-manifest validity;
- file count and encoded bytes;
- write, compaction, and query duration;
- reader-visible state at injected interruption boundaries;
- new-URL and temporal-query correctness.

## Interpretation

Logical equality is checked before performance is interpreted. Timing results
describe the recorded local machine and cache conditions; they are not
universal performance guarantees. Compaction can reduce file-open and metadata
overhead while making a selective query slower, so each query class is
reported independently.

