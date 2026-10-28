# Shared origin pacing across local jobs

**Execution:** `20261026T055118Z-s03-fd7f5983`  
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
| `results.configuredAllowancePhase.arrivalDiagnostics.group-a` | 0.2 | 0.218832 | 0 | pass |
| `results.configuredAllowancePhase.arrivalDiagnostics.group-b` | 0.2 | 0.220046 | 0 | pass |
| `results.configuredAllowancePhase.perGroup.group-a` | 0.2 | 0.220411136 | 0 | pass |
| `results.configuredAllowancePhase.perGroup.group-b` | 0.2 | 0.220669952 | 0 | pass |
| `results.originCeilingPhase.arrivalDiagnostics` | 0.5 | 0.548816 | 0 | pass |
| `results.originCeilingPhase.global` | 0.5 | 0.550349824 | 0 | pass |

`measurements.csv` is derived from `measurements.json`; it does not add observations
that were not retained by the execution. Parquet files, when present, remain the
authoritative dataset representation and the CSV is a reviewer-readable companion.
