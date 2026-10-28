# Registered experiments

`catalog.json` is the public index of the controlled experiments. Entries use
descriptive identifiers rather than internal codes so a reader can understand
the evaluated behavior without consulting a separate crosswalk.

An experiment is a test definition, not a dataset and not a completed run.
The repository map in [`../START_HERE.md`](../START_HERE.md) explains how an
experiment connects to inputs, execution evidence, and analysis.

Each registration records:

- the experiment family and research question;
- deterministic seed and workload parameters;
- direct measurements;
- an acceptance rule that can be evaluated from retained evidence; and
- the current public evidence status.

`registered` means that the definition is available. It does not mean that a
reviewed execution has been published. An entry becomes `evidence-published`
only when its sanitized execution manifest and measurements are present under
`evidence/executions/` and covered by the repository checksum manifest.

The catalog evaluates the local open-source application. References to a
workspace mean one local PulseCrawl workspace, not a remote account or service.

For example, `url-scoped-template-selection` is an experiment ID. A timestamped
name such as `20261026T060712Z-s04-aa30023e` is an execution ID for one run.
Use [`../evidence/executions/INDEX.md`](../evidence/executions/INDEX.md) to move
from a readable experiment name to its retained executions.

