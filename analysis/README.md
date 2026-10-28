# Analysis artifacts

This directory contains transformations derived from reviewed execution
evidence. Analysis files must identify their input execution IDs and retain the
direct measurements unchanged under `evidence/executions/`.

For every published analysis, include:

1. the included and excluded execution IDs;
2. the exclusion rule and reason for each exclusion;
3. the measurement columns used;
4. the statistic or transformation applied;
5. the software version that produced the output; and
6. links to generated tables or figures.

Recommended layout:

```text
analysis/<analysis-id>/
├── analysis-manifest.json
├── findings.md
├── statistics.csv
├── tables/
└── figures/
```

Negative and null results remain part of the analysis. Failed runs are not
silently deleted, post-repair measurements do not overwrite pre-repair
measurements, and missing values are not treated as zero.

Release `v0.3.0` publishes the frozen controlled analysis under
[`releases/public-local-0.1.0-2026-10-27/`](releases/public-local-0.1.0-2026-10-27/).
Its manifest lists all 116 included controlled executions, and its checksum
manifest covers the retained findings, measurements, statistics, and verdict
files.

