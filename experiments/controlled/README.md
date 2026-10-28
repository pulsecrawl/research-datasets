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
| `summary.json` | Run-level summary used by the frozen analysis |
| `checksums.sha256` | Integrity hashes for the four files above |

The descriptive parent folder answers “what was tested.” The `run-###` folder
answers “which repetition is this.” The execution manifest preserves the
original immutable execution identity.

The directories were generated from the frozen release with
`src/pulsecrawl_research/tools/import_reviewed_release.py`. The controlled
release contains only the bounded files listed above, not entire workspaces.

