# Frozen multi-industry corpus quality

**Execution:** `20261026T061324Z-t04-cd6d587e`  
**Status:** completed  
**Acceptance rule:** Metrics are computed against the frozen expected-value manifests without live-network substitution.

## What to inspect

| File | Purpose |
|---|---|
| `measurements.csv` | Human-readable, flattened view of every retained measurement |
| `measurements.json` | Authoritative structured measurements |
| `summary.json` | Run-level result consumed by the reviewed analysis |
| `resolved-experiment.json` | Registered workload, measures, and acceptance rule |
| `execution-manifest.json` | Software, timing, command, and source-evidence identity |
| `checksums.sha256` | Integrity hashes for all published run files |

`measurements.csv` is derived from `measurements.json`; it does not add observations
that were not retained by the execution. Parquet files, when present, remain the
authoritative dataset representation and the CSV is a reviewer-readable companion.
