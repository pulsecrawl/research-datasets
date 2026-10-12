# PulseCrawl evaluation inputs and live case-study plan

Two separate kinds of evaluation:

| Area | Contents | What it establishes |
| --- | --- | --- |
| Controlled synthetic tests | 60 fixed HTML pages, 100 scoped HTML pages, 20 fictional commerce inputs, WebBench, storage generator and 1,000-row sample | Repeatable behavior against known inputs |
| [Live end-to-end case study](live-case-study/README.md) | Real candidate URLs, provisional templates, field definitions, and execution limits | A plan for using the local OSS application against real websites; not completed results |

**Synthetic data uses fictional names and reserved .example URLs. Real website names and URLs belong only to the live case-study plan.** Synthetic pages are never substituted for a failed live fetch.

## Verify and regenerate synthetic inputs

Python 3.11 or newer:

```sh
python tools/verify.py
python -m pip install -r requirements-storage.txt
python -m unittest discover -s tests -v
python tools/generate_fixed_html.py
python tools/generate_site_pattern.py
python tools/generate_commerce.py
python tools/webbench.py --items-per-site 10 --sites-per-vertical 1
```

WebBench binds to loopback by default. Its HTTP websites are not the saved extraction sets. To generate storage input in a fresh directory:

```sh
python tools/generate_storage.py --output ./storage-output --rows 1000000 --executions 100
```

The million-row generator is included; retained historical million-row outputs and performance measurements are not.

## Run the real-world exercise

[The manifest](live-case-study/sources.json) defines ten real candidate product sources, provisional template stacks, and bounded policy settings. Every candidate starts disabled pending an operator's access review.

The local OSS example provides separate `live.py` commands to inspect the plan, initialize an explicitly reviewed job, run it once over real HTTP, and record exercise notes. Re-run manually later to compare actual observations. No HTML archive is required: retain structured outputs, dataset versions, request metadata, and practical workflow notes.

A manifest alone is not evidence of a run. This release contains **no completed live commerce executions or observed retailer price changes**. Access blocks, empty results, unchanged prices, and template repairs are reportable outcomes.

## Version and evidence boundaries

Version 0.2.0 replaces real-brand-shaped synthetic fixtures with fictional identities. Earlier versions remain historical snapshots; their fixtures were also synthetic. Existing research scores must not be silently assigned to the revised inputs. This is not a complete archive of the application, historical runs, or a participant usability study.

See [DATASETS.md](DATASETS.md), [PRIVACY.md](PRIVACY.md), and [NOTICE](NOTICE). Fixed/scoped synthetic collections retain CC0-1.0; software, commerce fixtures, and other new files are AGPL-3.0-only. Third-party names and URLs do not convey affiliation or crawling permission.
