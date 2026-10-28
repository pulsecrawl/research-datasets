# Human-readable dataset view

`records.csv` is a complete, deterministic row-level CSV view of the current dataset version. The manifest-selected Parquet files under `workspace-evidence/` remain authoritative. Email addresses, absolute home paths, and credential-shaped text are redacted only in the CSV view. `csv-export.json` records the selected version, row count, source files, checksums, and sanitization boundary.
