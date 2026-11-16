# CSD canonical event payload read validation report 001

## Scope

Harden event reads used by idempotency and duplicate-review acknowledgement. A stored event could previously have a valid payload SHA-256 reference and a valid event-envelope digest while its JSON bytes were not in the canonical representation emitted by the append path.

## Change

- `CognitiveMemoryStore.get_event()` now compares the stored payload JSON bytes with the canonical serialization of the decoded object.
- Non-canonical but parseable JSON raises `CognitiveIntegrityError`.
- Because event-ID duplicate delivery and semantic-review duplicate handling both verify the prior event through `get_event()`, these acknowledgement paths now reject this tampering even when an attacker/test fixture recomputes both the payload reference and event-envelope digest.
- Added `test_duplicate_review_rejects_noncanonical_prior_payload_even_with_matching_digests`. The test removes immutability triggers in its isolated database, rewrites the payload using indented JSON, recomputes the content hash and event digest, then verifies that a retry cannot receive a duplicate acknowledgement.

## Verification status

- [~] Regression test and implementation committed to the feature branch.
- [ ] GitHub-hosted Ubuntu and Windows CI pending.
- [ ] User-local Windows 11 verification remains pending.

## Boundary

This change validates canonical serialization in `get_event()`; it does not turn SHA-256 digests into authenticated signatures and does not prove writer identity or source truth. Full event-family schema validation and projection replay remain part of Recovery and projection reconciliation. The change does not alter event schema version or persisted data format.
