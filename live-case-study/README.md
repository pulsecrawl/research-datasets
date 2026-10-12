# Live end-to-end case study

This is a **real-website exercise plan**, not an offline HTML corpus or completed result set.

`sources.json` defines ten candidate product sources with actual URLs, nullable typed fields, provisional templates, and conservative bounds. No product records, price expectations, or success claims are manufactured.

## Workflow with the local OSS example

From a PulseCrawl source checkout with the SDK workspace dependencies installed, use the `marketplace.premium_commerce.live` module in the SDK examples directory:

1. `plan --manifest sources.json`: inspect candidates; no requests or workspace writes.
2. Review access conditions. In your local manifest copy, enable only reviewed sources and record an access basis and review date. This is an operator record, not a legal guarantee.
3. `init --manifest reviewed-sources.json --workspace ./live-workspace`: create the bounded local dataset/job; no HTTP.
4. `run --manifest reviewed-sources.json --workspace ./live-workspace --network`: execute once using real HTTP. HTML is not archived; synthetic fallback is prohibited.
5. Add practical notes with `note --workspace ./live-workspace --stage setup --text "..."`.
6. Run again manually after the configured minimum interval. Query the versioned records and compare actual prices, including unchanged values.

Candidates remain disabled in the published manifest. Requests still pass robots checks; denial or unreadable policy responses stop product fetching. No challenge solving, proxy rotation, authentication bypass, private APIs, or unattended schedules are supplied.

## Retained evidence

Local output includes resolved configuration, execution summaries, per-request URLs/statuses/checksums (not bodies or sensitive headers), extracted fields, committed version identities, and exercise notes. An execution that finishes with zero useful product records is not evidence of successful extraction.

Do not upload a whole workspace or unreviewed notes. Review product records, URLs, logs, and metadata before any publication. The current repository contains only the plan, not real-world results.

## Analysis

Record whether setup, execution, inspection, repeat execution, and version/history queries work. Record configuration corrections and template repairs rather than hiding them. Price change is not required for success: retaining the actual observations is.

A developer-conducted exercise supports a practical workflow analysis. It does not establish usability for other users without a separate participant study.
