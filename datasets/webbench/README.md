# WebBench loopback websites

WebBench is a local HTTP generator used by the policy and recovery experiments.
It produces fictional websites on `127.0.0.1` with configurable link graphs,
robots rules, redirects, transient failures, delays, and response sizes.

`example-config.json` is an example configuration. Historical requests and
downloaded pages are not retained here; the generator creates the bounded
workload when an experiment runs.

Because the generated server is an experimental control surface rather than a
single static website, screenshots would not explain its main purpose. Its
observable behavior is documented through the experiment definitions,
execution measurements, and request-policy summaries.
