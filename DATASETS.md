# Evaluation inputs and evidence boundary

The datasets are one part of the public research artifact. Experiment
registrations live under `experiments/`, direct execution evidence under
`evidence/`, and derived results under `analysis/`. Dataset presence alone does
not establish that an experiment was executed.

## Controlled synthetic inputs

All HTML bodies and expected record values in `datasets/` are generated, not scraped.

- **Fixed HTML:** 60 pages, 20 each for news, employment, and products. The unchanged answer manifest includes mappings and checksums. Symbolic `webbench://` identifiers are not downloaded URLs.
- **Scoped synthetic HTML:** 100 baseline pages across 20 fictional configurations. Five layouts per configuration: JSON-LD, graph, metadata, CSS, and malformed JSON-LD with CSS fallback. Hosts end in `.example`. Extra mutation experiments are not included.
- **Fictional commerce:** 20 documents representing two observations of ten fictional stores. Prices USD 120 and USD 99 are deliberate test values, not observed market prices. There are ten repeated scopes, not twenty independent products.
- **Storage:** a newly generated 1,000-row JSONL sample (two executions of 500 rows) plus the generator and million-row reference configuration. Source URLs use `source.example`. Full historical outputs are not included.
- **WebBench:** a local HTTP server generating fictional websites on demand. Its example configuration is illustrative; no historical request logs are included.

DuckDB is pinned and storage timestamps explicitly use UTC. Under the declared identity rule, the sample has 505 distinct URLs and the million-record configuration has 19,900.

Version 0.2.0 changed the identities of scoped and commerce synthetic inputs. It does not claim byte identity with earlier real-brand-shaped fixtures or establish that historical accuracy results were rerun against this version.

## Live end-to-end case study

`live-case-study/sources.json` contains real candidate product URLs, provisional template stacks, shared fields, request limits, and explicit access-review status. It contains no fake records or expected prices. All candidates are initially disabled. The study status is `not-run`.

The exercise uses real HTTP through the local OSS workspace. It retains extracted records, execution summaries, version manifests, request status/checksum metadata, and setup/repair notes. HTML is processed in memory, not archived by the example.

Repeated executions may show changed or unchanged prices. Missing fields, redirects outside scope, access denials, and required template edits remain observations. Provisional templates are not validated live integrations.

## Evidence and verification

HTML answer manifests hash the synthetic inputs; `checksums.sha256` covers
release files. `release-manifest.json` records current coverage and exclusions.
Published executions additionally carry a per-execution checksum manifest and
identify the exact public PulseCrawl package version.

The live source manifest defines an exercise but does not prove it ran. No
independently labeled external corpus, manuscript, personal metadata, or
completed live-commerce observations are included in the current tagged
release. Publishing collected output requires a separate review for permissions
and sensitive data.
