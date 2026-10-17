# Implementation review log

16 October 2026, before packaging: the first diagnostic run correctly restricted simulator and hazard fitting to settled pre-cutoff records, but its May/June policy-selection subset did not separately exclude contracts settling on or after 1 July. This violated the intended information cutoff for policy fitting. Added the settlement cutoff to policy selection and a policy-availability guard to the single-quote command, then reran the fixed experiment. No event labels, neighbours, loading grid, event weights or evaluation definitions were changed in response to scores. Published outputs are from the corrected run; the protocol remains unchanged.

Prospective collection is a prototype. Source endpoints and actual external-model responses require a live integration test in an environment with network access and credentials. Offline API-orchestration tests use an explicitly fake client.
