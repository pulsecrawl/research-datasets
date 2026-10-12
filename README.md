# PulseCrawl research datasets

Versioned, synthetic inputs for separate local crawling, extraction, and storage evaluations.

These are **different tests, not one shared dataset or a single pipeline**.

| Input | Contents | Purpose |
| --- | --- | --- |
| WebBench | Local HTTP server and example configuration | Test crawling behavior, links, robots, redirects, and request timing |
| Fixed HTML | 60 pages: 20 news, 20 jobs, 20 products; expected fields and checksums | Repeatable basic extraction checks |
| Site-pattern HTML | 100 baseline pages across 20 documented site configurations | Scoped-template checks using synthetic markup |
| Commerce HTML | 20 synthetic observations: 10 product scopes, twice | Illustrate fictional price changes across two observations |
| Storage workload | Generator, reference configuration, and a 1,000-row sample | Generate structured records independently of HTML extraction |

## Use

Python 3.11 or newer is required. Small HTML inputs are included directly.

```sh
python tools/verify.py
python -m unittest discover -s tests -v
python tools/webbench.py --items-per-site 10 --sites-per-vertical 1
```

The HTTP server binds to loopback by default. Its generated pages are not the saved extraction collections.

Regenerate each collection separately:

```sh
python tools/generate_fixed_html.py
python tools/generate_site_pattern.py
python tools/generate_commerce.py
```

For the storage workload, install the pinned optional dependency and generate a fresh directory:

```sh
python -m pip install -r requirements-storage.txt
python tools/generate_storage.py --output ./storage-output --rows 1000000 --executions 100
```

This may produce large files. Generated output is excluded from Git. This release includes the generator and a 1,000-row sample, **not the retained million-row experimental outputs**.

## Evidence boundaries

All included HTML bodies and record values are synthetic. Retailer and publisher names identify example URL scopes, not endorsements, permissions, observed live prices, or verified live integrations. No live website requests are made by the HTML generators. Never crawl the example URLs solely because they appear here.

This is an input-data release, not a complete archive of research runs, performance results, or the PulseCrawl application. Generating new files does not reproduce historical timings. The site-pattern release includes baseline pages only, not the additional mutation experiments.

See [DATASETS.md](DATASETS.md) for counts, labels, and limitations, and [PRIVACY.md](PRIVACY.md) for the publication boundary.

## License

The existing fixed and site-pattern datasets are CC0-1.0; their manifests retain that designation. The commerce fixtures, software, documentation, and new storage sample are distributed under AGPL-3.0-only. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Dataset licenses do not cover third-party names or trademarks.
