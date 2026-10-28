# Reference-to-Parquet semantic round trip

**Execution:** `20261026T061327Z-d04-dde0ba0a`  
**Status:** completed  
**Acceptance rule:** Row counts and canonical semantic checksums agree after publication and readback.

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
