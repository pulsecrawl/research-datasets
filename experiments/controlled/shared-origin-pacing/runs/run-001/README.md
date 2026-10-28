# Shared origin pacing across local jobs

**Execution:** `20261026T054858Z-s03-03213b64`  
**Status:** completed  
**Acceptance rule:** All same-origin authorization gaps satisfy the configured minimum interval.

## What to inspect

| File | Purpose |
|---|---|
| `measurements.csv` | Human-readable, flattened view of every retained measurement |
| `measurements.json` | Authoritative structured measurements |
| `summary.json` | Run-level result consumed by the reviewed analysis |
| `resolved-experiment.json` | Registered workload, measures, and acceptance rule |
| `execution-manifest.json` | Software, timing, command, and source-evidence identity |
| `checksums.sha256` | Integrity hashes for all published run files |

## Recorded pacing checks

| Scope | Required gap (s) | Minimum observed gap (s) | Violations | Result |
|---|---:|---:|---:|---|
| `results.configuredAllowancePhase.arrivalDiagnostics.group-a` | 0.2 | 0.219075 | 0 | pass |
| `results.configuredAllowancePhase.arrivalDiagnostics.group-b` | 0.2 | 0.219041 | 0 | pass |
| `results.configuredAllowancePhase.perGroup.group-a` | 0.2 | 0.220404992 | 0 | pass |
| `results.configuredAllowancePhase.perGroup.group-b` | 0.2 | 0.22048896 | 0 | pass |
| `results.originCeilingPhase.arrivalDiagnostics` | 0.5 | 0.549062 | 0 | pass |
| `results.originCeilingPhase.global` | 0.5 | 0.550611968 | 0 | pass |

`measurements.csv` is derived from `measurements.json`; it does not add observations
that were not retained by the execution. Parquet files, when present, remain the
authoritative dataset representation and the CSV is a reviewer-readable companion.
