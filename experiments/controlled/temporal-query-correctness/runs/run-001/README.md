# Temporal query correctness and latency

**Execution:** `20261026T062122Z-d07-e85beb7f`  
**Status:** completed  
**Acceptance rule:** Hourly, daily, all-history, and new-URL queries return the registered rows and checksums.

## What to inspect

| File | Purpose |
|---|---|
| `measurements.csv` | Human-readable, flattened view of every retained measurement |
| `measurements.json` | Authoritative structured measurements |
| `summary.json` | Run-level result consumed by the reviewed analysis |
| `resolved-experiment.json` | Registered workload, measures, and acceptance rule |
| `execution-manifest.json` | Software, timing, command, and source-evidence identity |
| `checksums.sha256` | Integrity hashes for all published run files |
| `readable-output/` | Parquet evidence plus its matching CSV view and export manifest |

`measurements.csv` is derived from `measurements.json`; it does not add observations
that were not retained by the execution. Parquet files, when present, remain the
authoritative dataset representation and the CSV is a reviewer-readable companion.
