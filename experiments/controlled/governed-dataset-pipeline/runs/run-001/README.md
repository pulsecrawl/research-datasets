# Governed dataset pipeline comparison

**Execution:** `20261026T062126Z-d10-d011e7db`  
**Status:** completed  
**Acceptance rule:** Equivalent logical inputs and queries are validated before storage, query, or maintenance costs are compared.

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
