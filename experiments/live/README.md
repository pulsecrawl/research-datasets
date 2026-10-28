# Live website studies

Each category folder contains three different things:

1. `input/sites.json` lists candidate websites, exact qualification URLs,
   access limits, extraction mappings, and any recorded exclusion reason.
2. `experiment.yaml` defines the short qualification and the separately
   configured 24-hour study.
3. `runs/` contains published evidence after a bounded run completes.

The qualification command performs two cycles five minutes apart. It cannot
start the 24-hour phase. A site is eligible for that later phase only when the
short run completes normally, the workspace validates, and the site produces
at least one record containing every required field.

Third-party response bodies are processed in memory and are never published.
The evidence may include access decisions, request metadata, SQLite state,
Parquet dataset parts, dataset-version manifests, summaries, and checksums.

Start with [`catalog.json`](catalog.json), then open a category README.
