# Evaluation datasets

This directory contains the controlled inputs used by the registered
experiments. These files are inputs, not results. Controlled run evidence is
under [`../experiments/controlled/`](../experiments/controlled/), and reviewed
releases are under [`../experiments/releases/`](../experiments/releases/).

If those terms are unfamiliar, read the repository's
[`README.md`](../README.md) first.

| Collection | What it contains | Primary purpose |
| --- | --- | --- |
| [`fixed-html/`](fixed-html/) | 60 generated news, employment, and product pages | Compare extraction methods against known values |
| [`site-pattern-html/`](site-pattern-html/) | 100 pages across 20 fictional website configurations | Test URL-scoped templates, fallback, ambiguity, and markup changes |
| [`commerce-html/`](commerce-html/) | Two fictional observations for ten fictional stores | Test repeated product extraction and price-history records |
| [`storage/`](storage/) | A 1,000-row retained sample and a larger deterministic configuration | Test publication, version selection, compaction, and temporal queries |
| [`webbench/`](webbench/) | Configuration for a loopback HTTP website generator | Test budgets, robots rules, pacing, failures, and recovery |

All website identities in the controlled HTML collections are fictional.
Reserved `.example` hosts and generated content prevent controlled inputs from
being mistaken for captured website data. The screenshots in this repository
show these generated fixtures only; they are not screenshots of external sites.

See [`../README.md`](../README.md) for licensing, provenance, and the full
publication boundary.

## Do not confuse these folders

- `datasets/` contains repeatable controlled inputs.
- `experiments/controlled/` contains measurements from completed controlled runs.
- `experiments/releases/` contains reviewed results calculated from those measurements.
- `experiments/live/completed-news-and-commerce/` contains aggregate observations from real websites.
