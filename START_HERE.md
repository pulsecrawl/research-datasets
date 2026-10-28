# Start here

This repository separates the research into a few different kinds of files.
They are related, but they do not mean the same thing.

## The research flow

```text
Controlled input -> Experiment definition -> Execution evidence -> Analysis
 real website  ->   Live-study plan   -> Aggregate live evidence
```

| Term | Plain-language meaning | Example | Location |
| --- | --- | --- | --- |
| Dataset or input collection | Pages or records supplied to a controlled test | 60 generated HTML pages with known answers | [`datasets/`](datasets/) |
| Experiment | The question, workload, measurements, and success rule defined before execution | `url-scoped-template-selection` | [`experiments/`](experiments/) |
| Execution | One completed run of one registered experiment | `20261026T060712Z-s04-aa30023e` | [`evidence/executions/`](evidence/executions/) |
| Evidence | Direct measurements and metadata retained from an execution | Request counts, extracted fields, or published versions | [`evidence/`](evidence/) |
| Analysis | Results calculated from reviewed evidence | Tables, statistics, and hypothesis decisions | [`analysis/`](analysis/) |
| Live study | Repeated execution against current public pages | The 48-cycle news study | [`evidence/live-studies/`](evidence/live-studies/) |

An input file is not proof that a test ran. An experiment definition is also
not proof that it ran. Completed runs are under `evidence/`, and conclusions
calculated from those runs are under `analysis/`.

## What is currently published

| Material | Published scope |
| --- | ---: |
| Controlled input collections | 5 |
| Registered experiments | 30 |
| Reviewed controlled executions | 116 |
| Frozen controlled analyses | 1 |
| Retained live studies | 2 |
| Websites used by the retained live studies | 6 |

The six live website configurations are five news websites and one commerce
website. Their names, URLs, study IDs, run IDs, site IDs, and aggregate results
are listed in the [live-study guide](evidence/live-studies/README.md).

## How identifiers work

| Identifier | What it identifies | Example |
| --- | --- | --- |
| Experiment ID | A repeatable test definition | `execution-budget-under-concurrency` |
| Execution ID | One run of an experiment | `20261026T053308Z-s01-652aa247` |
| Study ID | One retained real-website study | `news` |
| Run ID | The retained scheduled run for that study | `20261026T062242Z-l01-59f95fc5` |
| Site ID | One website configuration inside a live study | `norte-digital` |

Timestamped directory names are execution IDs. To learn what was tested, open
the directory's `execution-manifest.json` and read its `experimentId`, or use
the [controlled execution index](evidence/executions/INDEX.md).

## Choose what you want to inspect

| Question | Best starting point |
| --- | --- |
| What did the controlled evaluation conclude? | [Controlled findings](analysis/releases/public-local-0.1.0-2026-10-27/README.md) |
| Which real websites were used? | [Live-study overview](evidence/live-studies/README.md) |
| What are the generated input pages? | [Dataset guide](datasets/README.md) |
| What does each experiment test? | [Experiment guide](experiments/README.md) |
| What files belong to one completed run? | [Execution evidence guide](evidence/executions/README.md) |
| How can the checks be reproduced? | [Protocol guide](protocols/README.md) |
| What is intentionally not public? | [Privacy and publication boundary](PRIVACY.md) |

The repository does not contain the thesis PDF, downloaded third-party HTML,
raw browser sessions, credentials, or personal workstation metadata.
