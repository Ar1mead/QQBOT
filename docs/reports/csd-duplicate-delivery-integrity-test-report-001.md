# CSD Duplicate Delivery Integrity — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `6353b83167c955a08b041cd923bbca9a62cb3b3b`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43692771953)  
> Workflow run: **#290** — success on both matrix jobs

## 1. Finding

The event append path treated a repeated `event_id` with matching immutable envelope fields and payload reference as an idempotent duplicate. It did not validate the previously stored event payload and envelope digests before returning the duplicate acknowledgement.

If an existing event's envelope digest had been corrupted, a retry of the original event could therefore return `status=duplicate` without surfacing the damaged durable record.

## 2. Fix

Before acknowledging an existing `event_id` as a duplicate, the append path now calls the standard event reader to validate:
- payload existence and content-addressed payload digest;
- event envelope digest, including the original received timestamp;
- basic event envelope fields.

Only after the stored event has passed integrity validation does the append path compare immutable content and return a duplicate result or raise an idempotency conflict.

## 3. Regression test

The new test:
1. appends a valid observation event;
2. deliberately removes the append-only trigger in the test database;
3. corrupts that event's stored envelope digest;
4. resubmits the exact original event;
5. asserts that duplicate submission raises `CognitiveIntegrityError` and does not append another event.

This verifies that idempotent retries do not mask pre-existing durable-history corruption.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 330 passed | 3.404s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 330 passed | 35.329s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- Hashes detect accidental or partial corruption; they are not keyed signatures or proof of writer authenticity.
- Continue reviewing duplicate proposal identity across domains, Recovery replay semantics, projection reconciliation, and backup/restore behavior.
