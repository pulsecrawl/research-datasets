# Execution evidence

This directory stores reviewed evidence for completed experiment executions.
It does not store application source or downloaded third-party HTML.

For a plain-language explanation of datasets, experiments, executions,
evidence, and analysis, begin with [`../START_HERE.md`](../START_HERE.md).

## Two kinds of evidence

| Evidence | Location | Meaning |
| --- | --- | --- |
| Controlled executions | [`executions/`](executions/) | Direct measurements from repeatable tests with fixed inputs |
| Live studies | [`live-studies/`](live-studies/) | Aggregate observations from repeated requests to current public pages |

Each published execution uses this layout:

```text
evidence/executions/<execution-id>/
├── execution-manifest.json
├── resolved-experiment.json
├── measurements.json
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

For a readable entry point, use the
[`executions` guide and index](executions/README.md) for controlled runs and the
[`live-studies` guide](live-studies/README.md) for real-website observations.

The live-study directories contain aggregate counts only. Record-level review
files, downloaded third-party HTML, article or product text, raw request logs,
and workspace databases remain outside the public artifact.

