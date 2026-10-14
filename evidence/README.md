# Execution evidence

This directory stores reviewed evidence for completed experiment executions.
It does not store application source or downloaded third-party HTML.

Each published execution uses this layout:

```text
evidence/executions/<execution-id>/
├── execution-manifest.json
├── resolved-experiment.json
├── measurements.csv or measurements.jsonl
├── summary.json
└── checksums.sha256
```

`execution-manifest.json` must validate against
[`execution-manifest.schema.json`](execution-manifest.schema.json). It records
the public package version, experiment identifier, dataset revision, sanitized
environment, timestamps, command, status, and output paths.

The following material is not publishable here:

- credentials, tokens, cookies, or sensitive headers;
- usernames, hostnames, absolute workstation paths, or personal email;
- unreviewed notes or raw workspace databases;
- downloaded third-party HTML without redistribution permission;
- raw high-cardinality logs that are unnecessary for the stated measurement.

An empty `executions/` directory means that no run has yet passed the public
evidence review. Definitions in `experiments/catalog.json` remain useful and
reproducible, but they are not presented as completed results.

