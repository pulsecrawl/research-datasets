# Reviewed executions

This release contains 116 controlled execution directories that passed
public-artifact review. Each directory includes the resolved experiment,
direct measurements, summary, sanitized execution manifest, and checksums.

Use [`INDEX.md`](INDEX.md) to see the experiment names and number of retained
executions. Each experiment then contains readable `run-001`, `run-002`, and
similar folders. The original timestamped execution ID remains inside
`execution-manifest.json` for traceability.

## How to read one execution

| File | Meaning |
| --- | --- |
| `execution-manifest.json` | Execution ID, descriptive experiment ID, timestamps, software versions, source checksum, public checksum paths, and reconstructed registered command |
| `resolved-experiment.json` | The workload, measurements, and acceptance rule applied to that execution |
| `measurements.json` | Direct measurements retained by the experiment harness |
| `measurements.csv` | The same retained measurements flattened into a GitHub-readable table |
| `summary.json` | Run-level summary used by the frozen analysis |
| `readable-output/` | Parquet evidence and matching CSV for runs that produced dataset rows |
| `checksums.sha256` | Integrity hashes for every published evidence file in the run |

The descriptive parent folder answers “what was tested.” The `run-###` folder
answers “which repetition is this.” The execution manifest preserves the
original immutable execution identity.

The directories were generated from the frozen release with
`src/pulsecrawl_research/tools/import_reviewed_release.py`, then enriched with
`src/pulsecrawl_research/tools/build_readable_evidence.py`. The controlled
release contains bounded evidence, not entire workspaces. Parquet is added only
for experiments whose retained source run contained dataset output.

