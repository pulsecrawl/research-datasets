# Template extraction protocol

## Question

Can URL-scoped, policy-aware template stacks produce useful structured records
across heterogeneous page layouts while making fallback, ambiguity, scope, and
repair behavior observable?

## Controlled inputs

The fixed and scoped collections provide generated HTML plus expected field
values. Synthetic documents never stand in for a real-website observation.
Live exercises are analyzed separately and do not receive expected values
unless an independent labeling procedure is recorded.

## Measurements

- field precision, recall, and F1;
- record coverage;
- cross-scope contamination;
- fallback tier and missing-template diagnostics;
- ambiguity detection and canonical-entity accuracy;
- accuracy before and after a registered repair;
- changed files, lines, and selector definitions for maintenance studies.

## Interpretation

Baseline and drift results are reported separately. Post-repair accuracy does
not replace the pre-repair result. A selected template identifier or template
label is document-level provenance; it is not described as field-level
attribution unless the retained record identifies the source of each field.

