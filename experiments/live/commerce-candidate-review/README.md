# Live end-to-end case study

This directory defines a real-website usability and workflow exercise for the
local PulseCrawl application. It is not an offline HTML corpus. Aggregate
results from the retained executions are published separately under
[`../completed-news-and-commerce/`](../completed-news-and-commerce/).

`sources.json` contains ten candidate product sources, provisional scoped
templates, nullable typed fields, and conservative request bounds. It contains
no manufactured product records or expected prices. Candidates remain disabled
in this public reproducibility copy; the completed study used a separately
reviewed local configuration and does not rewrite this source manifest.

## Installation

Use the same public package version as the controlled experiments:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r docs/environment/requirements.txt
```

Run these commands from the repository root so the source manifest and evidence
paths are unambiguous.

## Procedure

1. Inspect `sources.json` without making network requests.
2. Review each candidate's access conditions. Enable only reviewed sources in
   a local copy and record the review date and basis. This is an operator record,
   not a legal guarantee.
3. Create a new local PulseCrawl workspace and initialize the bounded job and
   dataset from the reviewed manifest.
4. Execute the job once using real HTTP. Synthetic fallback is prohibited.
5. Retain the sanitized execution manifest, request status/checksum metadata,
   structured records, dataset-version identifiers, and setup or repair notes.
6. Run again manually after the configured minimum interval and compare actual
   structured observations, including unchanged prices.
7. Publish only the reviewed evidence files allowed by `PRIVACY.md`.

Candidates remain disabled in the published manifest. Requests pass through the
package's robots and request-policy checks. Denial or an unreadable policy stops
product retrieval for that source. The study does not provide challenge
solving, proxy rotation, authentication bypass, private API access, or an
unattended schedule.

## Retained evidence

A publishable live execution may include:

- the reviewed source-manifest checksum;
- generic software and environment versions;
- bounded request URLs, statuses, timestamps, and body checksums;
- extracted structured fields after review;
- committed dataset-version identifiers and manifest hashes;
- template corrections and practical workflow notes; and
- a record of blocked, empty, unchanged, or unsuccessful sources.

Downloaded HTML bodies, cookies, sensitive headers, credentials, personal
notes, and an unreviewed workspace are not published.

An execution that produces zero useful product records is not evidence of
successful extraction. It is still a reportable usability or access outcome.
A source manifest alone is never described as a completed run.

The retained commerce study completed eight cycles on one eligible product
page. Its aggregate counts and publication boundary are explained in
[`../completed-news-and-commerce/commerce/README.md`](../completed-news-and-commerce/commerce/README.md).
