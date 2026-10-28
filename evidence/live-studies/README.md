# Retained live-study evidence

This directory contains public, aggregate evidence from PulseCrawl runs against
real websites. Its purpose is to show that the local workflow was exercised
outside the controlled synthetic environment while keeping the public artifact
bounded and reviewable.

The live-study evidence is not a downloadable website corpus. It intentionally
excludes downloaded HTML, article and product text, record-level review files,
raw request logs, local databases, credentials, and machine-specific metadata.

| Study | Scope | Human-readable guide |
| --- | --- | --- |
| News | 48 scheduled cycles across five eligible sites | [`news/README.md`](news/README.md) |
| Commerce | Eight scheduled cycles on one eligible product page | [`commerce/README.md`](commerce/README.md) |

Each study directory contains:

| File | Meaning |
| --- | --- |
| `README.md` | Plain-language scope, principal results, and limitations |
| `summary.json` | Machine-readable aggregate counters for runs and sites |
| `manifest.json` | Publication status, source/public hashes, and excluded material |
| `checksums.sha256` | Integrity hashes for the published files in that directory |

These studies support practical observations about recurring execution and
structured publication. They do not replace the controlled experiments used to
evaluate the hypotheses, and they do not establish universal behavior across
all websites.
