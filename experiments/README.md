# Registered experiments

`catalog.json` is the public index of the controlled experiments. Entries use
descriptive identifiers rather than internal codes so a reader can understand
the evaluated behavior without consulting a separate crosswalk.

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

