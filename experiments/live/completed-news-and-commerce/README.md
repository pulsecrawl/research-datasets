# Retained live-study evidence

This directory contains public, aggregate evidence from PulseCrawl runs against
real websites. Start with the two study guides rather than the JSON files.

## Studies at a glance

| Study | Study ID | Retained run ID | Websites evaluated | Guide |
| --- | --- | --- | ---: | --- |
| Recurring news collection | `news` | `20261026T062242Z-l01-59f95fc5` | 5 | [`news/README.md`](news/README.md) |
| Recurring product observation | `commerce` | `20261026T062448Z-l02-5b82bc4b` | 1 | [`commerce/README.md`](commerce/README.md) |

The news study used Norte Digital, La Verdad Juárez, Raíchali, La Opción de
Chihuahua, and Tiempo. The commerce study used one Alo Yoga product page.

## Identifier meanings

- The **study ID** identifies the type of retained live study.
- The **run ID** identifies the scheduled run that produced the retained
  summary.
- A **site ID** identifies one website configuration inside that run.

For example, `news` is a study ID, `20261026T062242Z-l01-59f95fc5` is its run
ID, and `norte-digital` is one of its site IDs.

## Files in each study folder

| File | Meaning |
| --- | --- |
| `README.md` | Website table, scope, results, and limitations in plain language |
| `sources.json` | Study ID, run ID, website names, domains, evaluated URLs, and site IDs |
| `summary.json` | Machine-readable aggregate counters for runs and sites |
| `manifest.json` | Publication status, source/public hashes, and excluded material |
| `checksums.sha256` | Integrity hashes for the published files in that directory |

## Publication boundary

This is not a downloadable website corpus. The repository does not publish
downloaded HTML, article or product text, record-level review files, raw
request logs, local databases, credentials, or machine-specific metadata.

The live studies show that the local recurring workflow ran against changing
public pages and produced structured dataset versions. They do not replace the
controlled experiments and do not establish universal behavior across all
websites.
