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
- Preserve internal decision-event retry idempotency while checking authority source, allowed outcome, proposal-scoped event ID, and correlation ID for each decision family. Memory/motivation decision sequence numbering is checked by `get_event()` and repeated at the duplicate boundary; goal decision IDs are checked against their family-specific proposal identity.
- Enforce exact decision payload field sets for all five decision families. `_apply_decision()` now rejects unknown/missing fields during Recovery as well as duplicate retry validation; motivation and goal decision reducers already enforce their corresponding exact field sets.
- Extend `get_event()` decision integrity checks to goal-batch, goal-activation, and goal-pause/resume decisions. Reads now verify exact field sets, authority source, proposal-scoped event ID, and correlation ID for all five decision families; state-version reads inherit these checks through `get_event()`.
- Covered observation, memory proposal, grounded-memory proposal, semantic review, interaction, motivation proposal, goal batch proposal, goal activation proposal, and goal pause/resume proposal event families.
- Keep the existing generic envelope verification and idempotency-conflict comparison.
- Convert malformed prior event schema errors to `CognitiveIntegrityError`.

The helper intentionally validates event-local and historically available evidence. It does not re-run a proposal's later lifecycle decision or reject a valid old review merely because its proposal has since reached a terminal state.

## Regression test

Added:

- `tests/test_csd_semantic_review.py::test_same_event_id_duplicate_rejects_prior_event_with_invalid_review_schema`
- `tests/test_csd_semantic_review.py::test_same_event_id_internal_decision_retry_remains_idempotent`
- `tests/test_csd_semantic_review.py::test_same_event_id_duplicate_rejects_decision_with_extra_payload_field`
- `tests/test_csd_goals.py::test_get_event_rejects_goal_decision_with_rebound_event_id_and_valid_digest`

The test:
1. Persists a valid semantic-review event.
2. Changes its outcome to an unsupported value.
3. Recomputes the canonical payload reference and event envelope digest, so generic integrity checks still pass.
4. Retries using the original `event_id`.
5. Requires `CognitiveIntegrityError` rather than a duplicate acknowledgement.

## Verification

- Schema-validation implementation commit: `32915b190d888aee36d584dd2987b0a4d51e953d`.
- Decision-retry compatibility implementation commit: `6492fa8e94c8e8cb487ee163b8e8d1380537aa52`.
- Same-event-ID schema regression commit: `6ca4e4a479d560569e8855dc646767fa0b7d6cba`.
- Internal-decision retry test was first added with an incomplete fixture; run #341 exposed that the fixture had not supplied the required semantic review. The fixture was corrected in commit `1b37d53061b0dd397792f7b06d353338e88f46d9`.
- Exact decision-schema implementation commit: `2c48338ac9ed46e868f059f8fcf8d265fe3c1fcf`; extra-field regression and assertion correction commit: `2c967b49ee766a52e27423ffbba02728c9f20292`.
- Decision-read validation implementation commit: `83b1927d2a08991f4c31e05146f0b21fad6a7a14`; error-contract and regression assertion updates: `1dfb7d28d7eed4775a2253f019010d07b5a2fd91`, `31c77293acd2d33cd71312bad252e57cf67ef638`, and `53c479cc6ec8b1f70fc0b1b2290f825d2e1001e7`.
- Runs #346–#349 exposed test assertions that expected the older/later validation message after decision validation moved into `get_event()`. Assertions were aligned with the earlier integrity rejection; no production behavior failure remained.
- GitHub Actions run #350: **passed** on Ubuntu and Windows.
- Full test discovery: **348 tests passed** on each platform.
- `compileall` and all workflow test steps passed.
- Hosted Windows CI is not a substitute for the user's own Windows 11 / Python 3.12.14 verification.

## Remaining audit boundary

This closes the event-local schema gap for the listed public event families on the same-event-ID duplicate path and enforces exact field sets for all decision event families. Continue auditing deeper decision semantic/context validation, cross-family event ordering, and coordinated corruption of projections versus event history. No real model provider or external action execution is introduced by this change.
