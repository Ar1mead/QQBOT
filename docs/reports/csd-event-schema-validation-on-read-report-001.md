# CSD Event Schema Validation on Direct Read Report 001

Date: 2026-11-16 (UTC+08:00)

## Scope

This slice closes the gap between three event-validation paths: Recovery replay, same-event-ID duplicate delivery, and ordinary direct event reads through `get_event()`.

## Finding

Before this change, `get_event()` verified payload storage type, payload digest, canonical JSON, timestamps, and envelope digest. It also checked the exact field set and proposal-scoped identity of decision events. It did not consistently rerun event-family schema validation for observations, memory proposals, grounded proposals, semantic reviews, interactions, motivation proposals, or goal proposals.

As a result, a direct SQL rewrite that also recomputed the payload reference and envelope digest could leave a malformed non-decision event readable until Recovery or a duplicate-delivery path encountered it.

## Change

- `get_event()` now invokes the same event-local schema validator used by the same-event-ID duplicate path.
- The validator checks the event family shape and applicable earlier-event references.
- Contextual checks remain bounded by the event's original sequence; later lifecycle changes do not invalidate an otherwise valid historical event.
- Earlier evidence references are followed recursively through `get_event()`, with event ordering rules requiring references to point backward.
- Decision event read checks remain in place and are also covered by the shared validator.

## Regression

Added `tests/test_csd_semantic_review.py::test_get_event_rejects_schema_invalid_observation_with_valid_digests`.

The test:
1. Persists a valid observation event.
2. Changes its `observation_kind` to an invalid empty value.
3. Recomputes the canonical payload reference and envelope digest.
4. Calls `get_event()` directly.
5. Requires `CognitiveIntegrityError` instead of returning the malformed event.

## Verification

- Implementation commits: `68956b4092742fb8aa9c2c31e37204c01134b63c` (shared validation on reads), `aa5c13fca447bf7cd64669c8df98890fe9932122` (helper naming and avoid duplicate decision checks), and `c61677c04980cdafb0d51b34efd60588f3fa825d` (generalized error wording).
- Regression test commits: `12c059db63443bb9a848fcd0df4f1c70555cf187` and `f7698e1e0726375211a1dcd73fe99f96007a6edf` (assertion wording aligned with the generalized integrity error).
- Hosted CI: pending.
- User-local Windows 11 / Python 3.12.14 verification: pending.

## Security boundary

The event digest is an integrity checksum, not an authenticated signature. This change detects schema-invalid rewrites even when their hashes are recomputed. It cannot prove authenticity against an actor able to rewrite the complete event history into a different, internally valid history and recompute all dependent values. Stronger tamper evidence requires an independently protected checkpoint or signing key outside the writable SQLite database; that is a separate design decision.

This change does not connect a model provider, infer subjective motivation, or execute external actions.
