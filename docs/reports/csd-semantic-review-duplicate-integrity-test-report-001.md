# CSD Semantic Review Duplicate Integrity — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `b276f393dc91873cb0b649dae332d4284767ccd6`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43693759104)  
> Workflow run: **#302** — success on both matrix jobs

## 1. Finding

Semantic-review idempotency is keyed by `review_id`, independently of the event's `event_id`. The duplicate-review path previously queried the prior event and payload tables directly, compared the stored JSON, and returned `duplicate_review` without validating the prior event's payload digest or envelope digest.

A damaged prior semantic-review event could therefore be hidden by a retry carrying the same `review_id` and payload.

## 2. Fix

The duplicate-review path now resolves each prior semantic-review event through the standard `get_event` reader before inspecting its `review_id` or acknowledging a duplicate. This verifies payload availability, content-addressed payload digest, event envelope fields, and event-envelope digest.

The event remains authoritative; the semantic-review projection is not used as a substitute for validating the original event.

## 3. Regression coverage

The new test:
1. submits a valid grounded proposal and semantic-review event;
2. removes the append-only event trigger in the test database;
3. corrupts the stored semantic-review event digest;
4. submits a retry with a new event ID but the same review ID and payload;
5. asserts that submission raises `CognitiveIntegrityError` and the event count remains unchanged.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 333 passed | 2.070s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 333 passed | 35.767s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- `get_event` validates payload and envelope digests; full event-schema and canonical-serialization validation remains enforced during Recovery. Continue reviewing whether append-time duplicate acknowledgements should share a single stronger persisted-event validator.
- Hashes detect accidental or partial corruption; they are not keyed signatures or proof of writer authenticity.
