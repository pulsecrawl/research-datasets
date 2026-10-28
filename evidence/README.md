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

Release `v0.3.0` contains 116 reviewed controlled executions. The release index
at [`reviewed-release.json`](reviewed-release.json) records the frozen source
release, source commit, per-run source checksum, public checksum, controlled
analysis, and aggregate live-study summaries.

The live-study directories contain aggregate counts only. Record-level review
files, downloaded third-party HTML, article or product text, raw request logs,
and workspace databases remain outside the public artifact.

