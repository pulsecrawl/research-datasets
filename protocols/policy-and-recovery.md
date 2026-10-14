# Policy and recovery protocol

## Question

Can the local PulseCrawl workspace apply request budgets, robots rules, origin
pacing, terminal-state guards, and recovery procedures consistently under
concurrency and process interruption?

## Controlled environment

WebBench runs on loopback and records an independent request trace. Each run
uses a newly created workspace, a registered seed, and the package version in
`environment/compatibility.json`. The final request-boundary authorization time
is the authoritative pacing measurement. Server arrival time is retained as a
diagnostic observation because transport and event-loop scheduling occur after
authorization.

## Measurements

- authorized and completed requests;
- budget, robots, and origin-interval violations;
- duplicate deliveries and duplicate request authorizations;
- requests observed after a terminal state;
- frontier and reservation state after recovery;
- queue, state-store, and visibility operations where applicable.

## Interpretation

A budget is an upper bound, not a promise to fetch exactly that many URLs.
Recovery means that local state converges to a valid terminal condition. It
does not imply exactly-once effects at an arbitrary remote HTTP server. Every
repetition and adverse observation remains in the evidence; missing values are
not converted to zero.

