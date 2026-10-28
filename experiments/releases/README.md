# Reviewed evidence releases

This directory contains reviewed collections of execution evidence and the
analysis derived from them. Every release identifies its input runs and leaves
the direct measurements unchanged under `experiments/controlled/` or
`experiments/live/`.

Analysis is the last layer of the controlled research flow: controlled inputs
are in `datasets/`, test definitions and direct run outputs are in
`experiments/`, and calculated findings are here. See the
[repository guide](../../README.md) for the complete map.

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

The [controlled evidence release](controlled-evidence-v0.3.2/) indexes the 116
reviewed controlled executions and their frozen analysis. The
`multi-category-qualification-v0.4.0-rc.1/` folder indexes the later short live
qualification and explicitly records that the 24-hour phase was not started.

