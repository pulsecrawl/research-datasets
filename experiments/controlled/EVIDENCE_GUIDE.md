# Execution evidence

This directory stores reviewed evidence for completed experiment executions.
It does not store application source or downloaded third-party HTML.

For a plain-language explanation of datasets, experiments, executions,
evidence, and analysis, begin with the [repository guide](../../README.md).

## Two kinds of evidence

| Evidence | Location | Meaning |
| --- | --- | --- |
| Controlled executions | [This folder](./) | Direct measurements from repeatable tests with fixed inputs |
| Live studies | [`../live/`](../live/) | Bounded observations from current public pages |

Each published execution uses this layout:

```text
experiments/controlled/<experiment-name>/runs/run-###/
├── execution-manifest.json
├── resolved-experiment.json
├── measurements.json
├── summary.json
└── checksums.sha256
```

`execution-manifest.json` must validate against
[`execution-manifest.schema.json`](../releases/execution-manifest.schema.json). It records
the public package version, experiment identifier, dataset revision, sanitized
environment, timestamps, command, status, and output paths.

The following material is not publishable here:

- credentials, tokens, cookies, or sensitive headers;
- usernames, hostnames, absolute workstation paths, or personal email;
- unreviewed notes or raw workspace databases;
- downloaded third-party HTML without redistribution permission;
- raw high-cardinality logs that are unnecessary for the stated measurement.

Release `v0.3.2` contains 116 reviewed controlled executions. The release index
at [`reviewed-release.json`](../releases/controlled-evidence-v0.3.2/reviewed-release.json) records the frozen source
release, source commit, per-run source checksum, public checksum, controlled
analysis, and aggregate live-study summaries.

For a readable entry point, use the [controlled index](INDEX.md) and the
[live-study guide](../live/README.md).

The earlier completed news and commerce study contains aggregate summaries.
The multi-category qualification release also retains its bounded local
workspace, including SQLite state and Parquet output, after a privacy scan.
Neither release contains downloaded third-party HTML.

