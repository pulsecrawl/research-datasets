# Research code

This package turns a registered experiment into a run directory with resolved
settings, direct measurements, a summary, and checksums.

| File | Purpose |
|---|---|
| `runner.py` | Runs one registered experiment and creates immutable evidence |
| `adapters.py` | Presents comparison systems through one measurement interface |
| `metrics.py` | Calculates shared measurements |
| `webbench.py` | Serves controlled local websites |
| `live_websites.py` | Runs bounded real-website studies without retaining HTML |
| `live_profiles.py` | Defines the six output schemas and template mappings |
| `live_qualification.py` | Runs the two-cycle readiness check for all categories |
| `store.py` | Creates run directories and checksum manifests |
| `tools/` | Generates fixtures, imports reviewed runs, and verifies a release |

The PulseCrawl application is installed from its public Python distribution;
its implementation is not copied into this repository.
