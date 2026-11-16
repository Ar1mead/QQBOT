# CSD malformed durable event read error normalization report 001

## Scope

Ensure persisted event corruption is consistently surfaced as `CognitiveIntegrityError` when reading an event, including reads used by duplicate-delivery acknowledgement.

## Change

- Wrapped persisted event field, timestamp, payload decoding, canonical serialization, and envelope validation in a single integrity-error boundary in `CognitiveMemoryStore.get_event()`.
- Existing explicit `CognitiveIntegrityError` failures retain their original messages.
- Unexpected validation failures caused by malformed durable data (`TypeError`, `ValueError`, `RecursionError`, or `OverflowError`) are now raised as `CognitiveIntegrityError`.
- Added `test_duplicate_event_rejects_prior_event_with_invalid_timestamp_as_integrity_error`: the test corrupts an already stored event timestamp using a test-only trigger removal, retries the same event ID, and verifies the duplicate is rejected with `CognitiveIntegrityError` without adding another event.

## Verification status

- [x] Implementation and regression test committed to the feature branch.
- [ ] GitHub-hosted Ubuntu and Windows CI pending.
- [ ] User-local Windows 11 verification remains pending.

## Boundary

This normalizes error classification; it does not change the event schema, durable format, digest algorithm, or authority model. A SHA-256 digest remains an integrity checksum, not a keyed signature or proof of writer identity.
