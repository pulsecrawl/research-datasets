# PulseCrawl research experiments and evidence

This repository is the public reproducibility companion for
[PulseCrawl](https://github.com/pulsecrawl/PulseCrawl). It contains the inputs,
registered experiment definitions, analysis methods, and reviewed execution
evidence used to evaluate the local open-source application.

**New readers should begin with [`START_HERE.md`](START_HERE.md).** It explains
the difference between inputs, experiments, executions, evidence, analysis,
and live studies, and shows where each item can be found.

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
| [`live-case-study/`](live-case-study/) | Candidate commerce sources and the bounded live-study procedure | Defines the exercise; completed results are under `evidence/live-studies/` |
| [`tools/`](tools/) | Generators, verification, WebBench, and evidence utilities | Regenerates inputs and validates the publication boundary |

No manuscript or thesis PDF is stored here. The repository provides research
artifacts that can be cited or inspected independently.

## Where to start

Choose the path that matches what you want to inspect:

| Goal | Start here |
| --- | --- |
| Understand how the repository fits together | [`START_HERE.md`](START_HERE.md) |
| Read the principal controlled findings | [`analysis/releases/public-local-0.1.0-2026-10-27/README.md`](analysis/releases/public-local-0.1.0-2026-10-27/README.md) |
| Understand the real-website studies | [`evidence/live-studies/README.md`](evidence/live-studies/README.md) |
| Inspect individual controlled executions | [`evidence/executions/README.md`](evidence/executions/README.md) |
| Understand the synthetic inputs | [`datasets/README.md`](datasets/README.md) |
| See what each experiment tests | [`experiments/README.md`](experiments/README.md) |
| Reproduce the procedures | [`protocols/README.md`](protocols/README.md) |

The human-readable guides explain the artifact first. JSON, JSONL, CSV, and
checksum files remain available for programmatic verification.

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

The retained evidence includes two live studies. The news study ran 48 cycles
across Norte Digital, La Verdad Juárez, Raíchali, La Opción de Chihuahua, and
Tiempo. The commerce study ran eight cycles against one Alo Yoga product page.
The [live-study overview](evidence/live-studies/README.md) lists the study ID,
retained run ID, site IDs, URLs, and aggregate results.

These summaries contain counts and operational outcomes, not downloaded pages,
article or product text, raw request logs, or workspace databases. A source
manifest alone is not treated as evidence of execution.

## Release boundary

Release `v0.3.2` adds a plain-language repository map and self-contained source
indexes for the retained live studies. It does not change the controlled input
collections, the 116 controlled executions, or the frozen controlled analysis.
Each controlled execution links its public checksum manifest to the checksum of
the corresponding frozen source run. Existing tags remain immutable.

See [`DATASETS.md`](DATASETS.md), [`PRIVACY.md`](PRIVACY.md), and
[`NOTICE`](NOTICE) for dataset, publication, and licensing boundaries.
