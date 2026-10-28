# Frozen controlled analysis

This directory is the main human-readable entry point for the controlled
evaluation. It analyzes the same 116 executions listed in
[`../../../evidence/reviewed-release.json`](../../../evidence/reviewed-release.json).
No controlled execution is silently excluded from the frozen input set.

## Start with these files

| File | Purpose |
| --- | --- |
| [`hypothesis-verdicts.md`](hypothesis-verdicts.md) | Concise H1–H3 verdicts and the acceptance checks behind them |
| [`findings.md`](findings.md) | Readable tables for policy, extraction, and dataset-publication results |
| [`analysis-manifest.json`](analysis-manifest.json) | Exact execution IDs, method, software, and output map |

## Detailed machine-readable files

| File | Purpose |
| --- | --- |
| `measurements.csv` | Normalized measurements derived from retained run summaries |
| `statistics.csv` | Computed statistics grouped by experiment, system, profile, or case |
| `analysis.json` | Full structured analysis used to generate the readable tables |
| `hypothesis-verdicts.json` | Structured form of the hypothesis checks |
| `checksums.sha256` | Integrity hashes for every published analysis file |

The controlled analysis and the live studies answer different questions. This
directory supplies the repeatable hypothesis evidence. The live studies under
[`../../../evidence/live-studies/`](../../../evidence/live-studies/) provide
bounded observations from real websites without publishing their page content.
