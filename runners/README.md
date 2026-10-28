# Comparison runners

These small entry points run the same controlled WebBench profiles through the
systems named by each folder.

| Folder | Role |
|---|---|
| [`pulsecrawl/`](pulsecrawl/) | PulseCrawl implementation evaluated by the thesis |
| [`scrapy/`](scrapy/) | Scrapy comparison runner |
| [`crawlee/`](crawlee/) | Crawlee comparison runner |
| [`firecrawl/`](firecrawl/) | Pinned optional Firecrawl environment and wrapper |

The shared experiment settings, metrics, and output format live in
[`../src/pulsecrawl_research/`](../src/pulsecrawl_research/). These folders do
not contain copies of the upstream projects.
