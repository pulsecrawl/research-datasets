# Versioned-dataset storage inputs

This directory provides deterministic records for evaluating dataset
publication and reading behavior.

- `sample/` retains 1,000 JSONL rows across two executions.
- `sample/manifest.json` records expected row and URL-identity counts.
- `reference-config.json` defines the larger deterministic workload without
  committing its full generated output.

The storage experiments use these records to evaluate append-all versus
new-URL-only publication, version selection, copy-on-write compaction,
interruption boundaries, and temporal queries. URLs use the reserved
`source.example` domain.
