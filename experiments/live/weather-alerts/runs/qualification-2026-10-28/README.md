# Two-cycle qualification: Weather and environmental alerts

This folder contains the published output for the 7 websites selected for
the short two-cycle qualification completed on 28 October 2026. It contains
access review, execution state, SQLite metadata, Parquet dataset parts,
dataset-version manifests, direct metrics, and checksums. Third-party response
bodies are not included.

- Selected websites: 7
- Completed cycles: 2
- Websites with a complete required-field record: 7
- Ready for the separately configured retained study: true

Start with `live-progress.json`, then inspect
`workspace-evidence/access-review.json`. The SQLite database and Parquet
files are retained so reviewers can reproduce the summary queries.

## Read the extracted records

Open [`readable-output/records.csv`](readable-output/records.csv) to inspect the complete current dataset version directly on GitHub. The source Parquet parts remain under `workspace-evidence/`.
