# CSD semantic-review duplicate schema validation report 001

## Finding

Semantic-review duplicate delivery verifies the prior event's payload reference and envelope through `get_event()`, then compares the review ID and payload. The generic event reader checks canonical JSON and envelope integrity, but it does not validate the semantic-review event-local schema.

A tampered prior review could therefore retain a valid canonical payload reference and recomputed envelope digest while carrying an invalid review outcome. Re-delivering the same malformed review could be acknowledged as `duplicate_review` without invoking Recovery.

## Change

- Extracted event-local semantic-review schema checks into `_validate_semantic_review_shape()`.
- Normal review submission/replay continues to use the same shape validator before checking proposal/claim provenance and event chronology.
- Duplicate review delivery now validates the prior event's semantic-review shape after `get_event()` verifies its content and envelope, before it can return `duplicate_review`.
- The shape validator is deliberately independent of mutable proposal lifecycle state, so a legitimate retry of an old review remains idempotent even if the proposal was subsequently decided.

## Regression

- `tests/test_csd_semantic_review.py::test_duplicate_review_rejects_prior_event_with_invalid_review_schema` stores a review with an invalid outcome, recomputes its canonical payload reference and envelope digest, then attempts duplicate delivery. The duplicate is rejected with `CognitiveIntegrityError`.

## Verification

- [x] Implementation commit: `bb4a5ce825ed460b1fdcd7b5af6aff1e17b51a43`.
- [x] Regression commit: `dcfbc12cef7273065b07230073c83501bd68666e`.
- [x] GitHub Actions run #336 passed on Ubuntu (Python 3.12.16 / SQLite 3.46.1) and Windows (Python 3.12.10 / SQLite 3.49.1): 344 tests passed on each platform; compileall passed.
- [ ] User-local Windows 11 / Python 3.12.14 verification remains pending.

## Boundary

This closes the event-local schema gap for semantic-review duplicate acknowledgement. It does not authenticate reviewer identity, establish reviewer truthfulness, or replace full event-history Recovery and projection reconciliation.
