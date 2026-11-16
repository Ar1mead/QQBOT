# CSD Same-Event-ID Duplicate Schema Validation Report 001

Date: 2026-11-16 (UTC+08:00)

## Scope

This follow-up audits the shared event-ID idempotency path after the semantic-review duplicate-schema fix. It specifically covers a retry that reuses the exact same `event_id`, rather than a second event ID carrying the same semantic `review_id`.

## Finding

The existing same-event-ID branch called `get_event()` and compared immutable envelope fields before returning `status="duplicate"`. `get_event()` verified payload storage type, payload hash, canonical JSON, timestamps, and envelope digest, but did not re-run the event family's schema validator.

Consequently, a previously accepted event whose payload and envelope were both maliciously modified and re-hashed could pass the generic integrity checks and receive a duplicate acknowledgement despite violating its event-specific schema. The semantic-review duplicate path with a *different* event ID was already protected; this report addresses the earlier same-event-ID branch.

## Change

- Added `_validate_duplicate_event_shape()` and invoke it on the stored event before acknowledging a same-event-ID retry.
- Revalidate the immutable event-local contract at the event's original sequence.
- Covered observation, memory proposal, grounded-memory proposal, semantic review, interaction, motivation proposal, goal batch proposal, goal activation proposal, and goal pause/resume proposal event families.
- Keep the existing generic envelope verification and idempotency-conflict comparison.
- Convert malformed prior event schema errors to `CognitiveIntegrityError`.

The helper intentionally validates event-local and historically available evidence. It does not re-run a proposal's later lifecycle decision or reject a valid old review merely because its proposal has since reached a terminal state.

## Regression test

Added:

`tests/test_csd_semantic_review.py::test_same_event_id_duplicate_rejects_prior_event_with_invalid_review_schema`

The test:
1. Persists a valid semantic-review event.
2. Changes its outcome to an unsupported value.
3. Recomputes the canonical payload reference and event envelope digest, so generic integrity checks still pass.
4. Retries using the original `event_id`.
5. Requires `CognitiveIntegrityError` rather than a duplicate acknowledgement.

## Verification

- Implementation commit: `32915b190d888aee36d584dd2987b0a4d51e953d`
- Regression-test commit: `6ca4e4a479d560569e8855dc646767fa0b7d6cba`
- GitHub Actions run #339: **passed** on Ubuntu and Windows.
- Full test discovery: **345 tests passed** on each platform.
- `compileall` and all workflow test steps passed.
- Hosted Windows CI is not a substitute for the user's own Windows 11 / Python 3.12.14 verification.

## Remaining audit boundary

This closes the event-local schema gap for the listed public event families on the same-event-ID duplicate path. Continue auditing internal decision-event retries, cross-family event ordering, and coordinated corruption of projections versus event history. No real model provider or external action execution is introduced by this change.
