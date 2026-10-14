# PulseCrawl research experiments and evidence

This repository is the public reproducibility companion for
[PulseCrawl](https://github.com/pulsecrawl/PulseCrawl). It contains the inputs,
registered experiment definitions, analysis methods, and reviewed execution
evidence used to evaluate the local open-source application.

The repository does **not** contain a second copy of PulseCrawl. Experiments run
against the versioned package published on PyPI:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements.txt
```

The pinned research dependency is `pulsecrawl[workspace]==0.1.0`. The package
implements the crawler and local workspace; this repository supplies the
evaluation inputs and records what was executed.

## Repository contents

| Area | Contents | Purpose |
| --- | --- | --- |
| [`datasets/`](datasets/) | Fixed synthetic HTML, scoped-template cases, fictional commerce observations, WebBench configuration, and storage inputs | Repeatable inputs with known expected values |
| [`experiments/`](experiments/) | Descriptively named experiment catalog and registered parameters | Defines the question, workload, measurements, and acceptance rule before a run |
| [`protocols/`](protocols/) | Policy, template, and versioned-dataset evaluation procedures | Explains how the experiment families are executed and interpreted |
| [`evidence/`](evidence/) | Schemas, execution manifests, measurements, checksums, and reviewed summaries | Connects an execution to its inputs, software version, configuration, and outcome |
| [`analysis/`](analysis/) | Analysis rules and derived tables or figures | Keeps transformations from measurements to reported results inspectable |
| [`live-case-study/`](live-case-study/) | Reviewed source manifest, templates, bounded configuration, and publishable run records | Supports a real-website workflow without redistributing downloaded HTML |
| [`tools/`](tools/) | Generators, verification, WebBench, and evidence utilities | Regenerates inputs and validates the publication boundary |

No manuscript or thesis PDF is stored here. The repository provides research
artifacts that can be cited or inspected independently.

## Controlled evaluation inputs

| Collection | Current coverage | Interpretation |
| --- | --- | --- |
| Fixed HTML | 60 documents | Deterministic extraction behavior across news, employment, and product layouts |
| Scoped synthetic HTML | 100 documents across 20 fictional site configurations | Template selection, fallback, ambiguity, and controlled drift |
| Fictional commerce | Two observations for ten fictional stores | Repeated extraction and structured price-history behavior |
| Storage | 1,000-row retained sample and a deterministic million-row generator configuration | Version publication, compaction, and temporal-query experiments |
| WebBench | Loopback HTTP generator | Request budgets, robots rules, pacing, redirects, failures, and recovery |

Synthetic data uses fictional names and reserved `.example` URLs. Real website
names and URLs appear only in the live case-study manifest. A failed live fetch
is never replaced by a synthetic page and reported as a live result.

## Verify the repository

Python 3.11 or newer:

```sh
python tools/verify.py
python -m unittest discover -s tests -v
```

Regenerate the deterministic input collections when their generators change:

```sh
python tools/generate_fixed_html.py
python tools/generate_site_pattern.py
python tools/generate_commerce.py
python tools/webbench.py --items-per-site 10 --sites-per-vertical 1
```

Generate the larger storage workload outside the repository:

```sh
python tools/generate_storage.py \
  --output ./storage-output \
  --rows 1000000 \
  --executions 100
```

## Experiment and evidence workflow

1. Select an entry from [`experiments/catalog.json`](experiments/catalog.json).
2. Confirm that its dataset revision and package version match
   [`environment/compatibility.json`](environment/compatibility.json).
3. Execute the registered workload against the installed public package.
4. Store the sanitized run manifest, measurements, and checksums under
   `evidence/executions/<execution-id>/`.
5. Generate derived summaries under `analysis/` without modifying the retained
   measurements.
6. Run `python tools/verify.py` before publishing the artifact.

After a run has produced reviewed measurements and a summary, create the
bounded evidence directory with:

```sh
python tools/create_execution_manifest.py \
  --experiment execution-budget-under-concurrency \
  --execution-id budget-run-001 \
  --measurements ./reviewed/measurements.csv \
  --summary ./reviewed/summary.json \
  --output ./evidence/executions/budget-run-001 \
  -- pulsecrawl run registered-job.json
```

The utility copies only the selected files, records generic software and
platform versions, and writes a per-execution checksum manifest. Review the
created directory before committing it.

The evidence directory distinguishes three layers:

- **Registered definition:** what was planned and how success is evaluated.
- **Execution evidence:** what version and configuration ran, plus the direct
  measurements and checksums.
- **Analysis:** derived statistics, tables, and figures with a documented input
  set and transformation.

An experiment definition is not evidence that the experiment ran. A run is not
included in a release until its evidence passes schema, checksum, and privacy
validation.

## Live end-to-end exercise

[`live-case-study/sources.json`](live-case-study/sources.json) defines ten real
candidate product sources and conservative request limits. Candidates start
disabled until an operator reviews access conditions.

The exercise uses real HTTP and records structured results, dataset-version
identifiers, request status/checksum metadata, and practical setup or repair
notes. Downloaded HTML bodies are not published. Access blocks, zero extracted
records, unchanged prices, and required template repairs remain valid observed
outcomes.

The current tagged release contains a plan, not completed live-commerce
results. A source manifest by itself is not evidence of execution.

## Release boundary

The existing [`v0.2.0`](https://github.com/pulsecrawl/research-datasets/releases/tag/v0.2.0)
tag remains the immutable synthetic-input release. The main branch prepares the
next artifact release, which adds experiment registration and a reviewed
evidence format. Existing tags are not rewritten.

See [`DATASETS.md`](DATASETS.md), [`PRIVACY.md`](PRIVACY.md), and
[`NOTICE`](NOTICE) for dataset, publication, and licensing boundaries.
