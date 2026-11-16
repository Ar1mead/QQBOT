# CSD authoritative decision event identity validation report 001

## Finding

Recovery replay already recomputed deterministic decision outcomes and checked decision source authority, but memory and motivation decision replay did not bind the immutable event identity fields to the proposal identity. Unlike goal lifecycle decisions, those two decision families did not verify their generated event ID sequence or correlation ID. A durable event with a recomputed valid envelope digest but a different correlation ID could therefore pass replay.

## Change

- Memory decisions now require event IDs of the form `csd-decision:{proposal_id}:{decision_number}` and correlation IDs of the form `proposal:{proposal_id}`.
- Motivation decisions now require event IDs of the form `csd-motivation-decision:{proposal_id}:{decision_number}` and correlation IDs of the form `motivation-proposal:{proposal_id}`.
- The decision number is derived from the count of prior events in the same decision family at the current replay sequence, matching the append path.
- Added recovery regressions that independently alter each decision's correlation ID and event ID, recompute the event-envelope digest, and verify Recovery rejects all four mutations with `CognitiveIntegrityError`.

## Verification status

- [x] Implementation and regression tests committed to the feature branch.
- [ ] GitHub-hosted Ubuntu and Windows CI pending.
- [ ] User-local Windows 11 verification remains pending.

## Boundary

This binds event identity and correlation metadata to the proposal ID and replay order. It does not authenticate the writer or provide a cryptographic signature. Goal decision families already enforced their corresponding proposal-scoped event ID and correlation contracts.
