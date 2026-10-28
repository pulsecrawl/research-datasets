# Reviewed executions

This release contains 116 controlled execution directories that passed
public-artifact review. Each directory includes the resolved experiment,
direct measurements, summary, sanitized execution manifest, and checksums.

Use [`INDEX.md`](INDEX.md) to see the experiment names and number of retained
executions before opening an individual timestamped directory.

## How to read one execution

| File | Meaning |
| --- | --- |
| `execution-manifest.json` | Execution ID, descriptive experiment ID, timestamps, software versions, source checksum, public checksum paths, and reconstructed registered command |
| `resolved-experiment.json` | The workload, measurements, and acceptance rule applied to that execution |
| `measurements.json` | Direct measurements retained by the experiment harness |
| `summary.json` | Run-level summary used by the frozen analysis |
| `checksums.sha256` | Integrity hashes for the four files above |

The timestamped directory name is an execution identity, not an experiment
name. Use the `experimentId` field or the index to determine what was tested.

The directories were generated from the frozen release with
`tools/import_reviewed_release.py`. Do not commit an entire PulseCrawl
workspace. Copy only the bounded evidence listed in `evidence/README.md`, run
the repository verification, and inspect the diff before publication.

