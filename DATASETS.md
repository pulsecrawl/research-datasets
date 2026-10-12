# Dataset guide

## Fixed HTML: basic extraction

The 60 generated HTML files in `datasets/fixed-html/expanded/` and their answer manifest are unchanged from the controlled input collection. The manifest stores expected title, body/description, date, mappings, layout, and SHA-256. It contains 20 documents in each of three categories. The symbolic `webbench://` source identifiers do not mean these files were downloaded from a running WebBench server.

## Site-pattern HTML: scoped extraction

`datasets/site-pattern-html/catalog.json` contains 20 configurations. Each has five baseline layouts: JSON-LD, JSON-LD graph, metadata, CSS, and malformed JSON-LD with CSS fallback. The 100 generated pages and their expected values are in the same directory.

Host/path and selector patterns are documented example scopes; the HTML bodies are synthetic, not captured third-party pages. Multiple configurations can share a host. The baseline does not include selector-renaming, negative-page, or other mutation experiments.

## Commerce HTML: repeated observations

`datasets/commerce-html/` contains two observations for each of ten retailer-shaped URLs: lululemon, Alo Yoga, Nordstrom, REVOLVE, Nike, Adidas, New Balance, On, HOKA, and UGG. The price values are fictional USD 120.00 followed by USD 99.00. Identifiers, sizes, colors, and brands are synthetic.

There are 20 input documents but only 10 repeated product scopes. This release contains fixtures and expected fields, not the local Workspace execution state or proof of live extraction. Live access is not enabled.

## Storage: independently generated records

`datasets/storage/reference-config.json` records the million-record workload parameters: 100 executions, 10,000 records each, 1% new identities per execution, body lengths from 128 to 2,048 characters, and synthetic source.example URLs. The SQL row-generation expressions are adapted from the research storage generator.

`datasets/storage/sample/` contains 1,000 rows in two JSONL files: two executions of 500 rows. It is a newly generated illustrative sample, not a subset asserted to reproduce historical results. `tools/generate_storage.py` can generate the million-record input in Parquet. It does not run the publication, compaction, or performance experiments.

DuckDB is pinned because hash and serialization behavior may depend on its version. The million-record configuration has 19,900 distinct URL identities under the declared rule; the 1,000-row sample has 505.

## WebBench: an executable input source

`tools/webbench.py` is a standalone copy of the local HTTP testbed implementation. It generates websites on demand and records requests when tracing is enabled. No request traces are included here. `datasets/webbench/example-config.json` is an illustrative configuration, not a claim that all historical experiments used those settings.

## Reproducibility limits

Each HTML manifest hashes its files. `checksums.sha256` covers all committed release content except itself. `release-manifest.json` records the included counts and exclusions.

The source application, complete experiment harness, raw benchmark runs, live audits, thesis, machine metadata, and independently labeled external corpus are not included. Public access to these inputs does not establish a complete reproducibility archive or independent real-web accuracy.
