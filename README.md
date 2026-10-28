# PulseCrawl research experiments and evidence

This is the public reproducibility companion for
[PulseCrawl](https://github.com/pulsecrawl/PulseCrawl). It contains the
controlled inputs, experiment definitions, runnable research code, comparison
runners, reviewed evidence, and analysis used to evaluate the local
open-source package.

The thesis PDF is intentionally not stored here. This repository contains the
research material needed to inspect how results were produced.

## Start here

The research flow is:

```text
Input data -> Experiment definition -> One or more runs -> Reviewed evidence -> Analysis
Public URL -> Access review         -> Bounded live run -> Versioned dataset -> Summary
```

These terms are deliberately separate:

| Term | Meaning | Location |
|---|---|---|
| Input data | Generated pages or records with known answers | [`datasets/`](datasets/) |
| Experiment | The question, settings, measurements, and acceptance rule | [`experiments/`](experiments/) |
| Run | One execution with resolved settings, measurements, and checksums | `experiments/controlled/<experiment>/runs/` or `experiments/live/<category>/runs/` |
| Evidence release | A reviewed collection of runs and derived results | [`experiments/releases/`](experiments/releases/) |
| Research code | Runners, metrics, storage helpers, and verification tools | [`src/pulsecrawl_research/`](src/pulsecrawl_research/) |

An input file or experiment definition is not proof that a run occurred.
Completed runs contain their own manifests and checksums.

## Repository map

```text
research-datasets/
├── README.md                       this guide and the reviewer reading order
├── CITATION.cff                    citation metadata
├── LICENSE, NOTICE, PRIVACY.md     licensing and publication boundaries
├── pyproject.toml                  reproducible research package
├── registry.yaml                  runnable public experiment registry
│
├── docs/
│   ├── protocols/                  evaluation procedures and decision rules
│   ├── environment/                package pins and compatibility information
│   └── images/                     previews of generated, non-live fixtures
│
├── datasets/
│   ├── fixed-html/                 60 generated pages with expected answers
│   ├── site-pattern-html/          100 scoped-template pages
│   ├── commerce-html/              fictional recurring price observations
│   ├── storage/                    generated versioned-dataset inputs
│   └── webbench/                   local controlled HTTP website generator
│
├── experiments/
│   ├── catalog.json                descriptive controlled experiment catalog
│   ├── controlled/
│   │   └── <experiment-name>/
│   │       └── runs/run-001/       guide, JSON evidence, readable CSV, checksums
│   ├── live/
│   │   ├── catalog.json            nine live categories and source counts
│   │   └── <category>/
│   │       ├── README.md           category purpose and schedule
│   │       ├── experiment.yaml     qualification and retained settings
│   │       ├── input/sites.json    exact reviewed URLs and limits
│   │       └── runs/               published bounded-run evidence
│   └── releases/
│       └── <release>/              analysis, evidence index, and checksums
│
├── runners/
│   ├── pulsecrawl/                 PulseCrawl controlled runner
│   ├── scrapy/                     Scrapy controlled runner
│   ├── crawlee/                    Crawlee controlled runner
│   └── firecrawl/                  pinned optional self-hosted profile
│
├── src/pulsecrawl_research/
│   ├── adapters.py                 comparison-system adapters
│   ├── runner.py                   one-experiment orchestration
│   ├── live_websites.py            bounded raw-HTTP live workflow
│   ├── live_profiles.py            six shared output schemas
│   ├── live_qualification.py       parallel two-cycle qualification
│   ├── metrics.py                  measurement calculations
│   ├── models.py                   shared research data structures
│   ├── store.py                    immutable run directories and checksums
│   ├── webbench.py                 controlled local website generator
│   └── tools/                      generators, importers, and verifier
│
└── tests/                          repository and research-code checks
```

Folder names use full experiment names. Historical opaque identifiers remain
only inside immutable source manifests where changing them would break
traceability.

## Install and verify

Python 3.11 or newer:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[all]'
python src/pulsecrawl_research/tools/verify.py
python -m unittest discover -s tests -v
```

The research package pins the separately published local package:

```sh
python -m pip install 'pulsecrawl[workspace]==0.1.0'
```

The PulseCrawl implementation is not copied into this repository.

## Controlled inputs and evidence

| Collection | Scope | Purpose |
|---|---:|---|
| Fixed HTML | 60 generated pages | Basic extraction against known values |
| Scoped site patterns | 100 pages across 20 fictional configurations | Template selection, fallback, and markup changes |
| Fictional commerce | 20 documents from ten fictional stores | Repeated product and price observations |
| Storage reference | Deterministic 1,000-row sample plus larger generator settings | Dataset versions, compaction, and temporal queries |
| WebBench | Generated local HTTP websites | Budgets, robots rules, pacing, failures, and recovery |

Generated inputs use fictional names and reserved `.example` URLs. They are
not presented as real website observations. Reviewed controlled evidence is
organized by descriptive experiment name under
[`experiments/controlled/`](experiments/controlled/).

## Multi-category live qualification

The live catalog contains 107 selected websites across nine categories:

| Category | Sources | Output schema | Planned retained interval |
|---|---:|---|---:|
| Mexican newspapers | 19 | Article | 30 minutes |
| United States newspapers | 20 | Article | 30 minutes |
| Financial and stock news | 20 | Article | 30 minutes |
| General commerce | 9 | Product | 60 minutes |
| Mexican supermarkets | 5 | Product | 60 minutes |
| S&P 500 company careers | 10 | Job posting | 60 minutes |
| Government and regulatory notices | 9 | Public notice | 60 minutes |
| Security advisories | 8 | Security advisory | 60 minutes |
| Weather and environmental alerts | 7 | Weather alert | 30 minutes |

The bounded qualification runs each category twice, five minutes apart. It
uses actual raw HTTP requests, performs a fresh fail-closed robots review, and
does not retain third-party response bodies:

```sh
pulsecrawl-research qualify-live \
  --output-root ./qualification-output
```

The qualification command cannot start the 24-hour retained phase. The
reviewed qualification release contains the 107 selected websites, all of
which passed the runtime and required-field checks. The release is indexed at
[`experiments/releases/multi-category-qualification-v0.4.1/`](experiments/releases/multi-category-qualification-v0.4.1/).

## Dataset and publication boundary

- Third-party HTML bodies are processed in memory and are not published.
- Published live evidence may contain source URLs, HTTP status, response
  checksums, extracted records, local workspace validation, Parquet parts, and
  dataset-version manifests.
- Every controlled run includes `measurements.csv`, a reviewer-readable view of
  its authoritative JSON measurements. Dataset-producing controlled runs also
  include checksum-linked Parquet evidence and a matching complete or bounded
  CSV view.
- Every live qualification run includes a complete CSV view of the current
  manifest-selected Parquet version. Sensitive text is redacted in that CSV;
  the source Parquet files remain authoritative and unchanged.
- No credentials, browser profiles, workstation paths, or personal names are
  permitted in a release.
- Every published run has a checksum file. Every release has a separate
  release manifest; releases are never overwritten.

See [`PRIVACY.md`](PRIVACY.md) for the complete boundary.

## Reviewer reading order

1. This README.
2. [`experiments/catalog.json`](experiments/catalog.json) for controlled tests.
3. [`experiments/live/catalog.json`](experiments/live/catalog.json) for live categories.
4. [`docs/protocols/`](docs/protocols/) for evaluation procedures.
5. [`experiments/releases/`](experiments/releases/) for reviewed findings.
6. A named experiment's `runs/` directory for direct measurements and checksums.
