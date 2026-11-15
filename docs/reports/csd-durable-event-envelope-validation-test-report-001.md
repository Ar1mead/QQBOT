# CSD Durable Event Envelope Validation — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `f8eda57c1dced7d5f8e29fb042e557d44fda83a0`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43692576455)  
> Workflow run: **#287** — success on both matrix jobs

## 1. Finding

Recovery verified event payload and envelope digests, then replayed the parsed event objects. It did not re-run the common event-envelope validator used by public submission and internal CSD decision writes.

Consequently, a durable event inserted outside the normal API could carry an event ID from a namespace reserved for CSD decisions while using a non-decision event type. The event could have internally consistent payload and envelope digests yet violate the event submission contract.

## 2. Fix

During the locked Recovery snapshot pass, each durable event is now checked through the same `_validate_event` contract used by append paths, with the appropriate internal flag for CSD decision events.

Recovery also requires the stored payload JSON to equal its canonical serialization. Validation failures are converted to `CognitiveIntegrityError` and abort the rebuild transaction.

This supplements—not replaces—the event digest, envelope digest, event-type-specific projection validation, chronology checks, and deterministic decision replay.

## 3. Regression coverage

A new durable-history test inserts an observation event directly into SQLite with:
- a reserved `csd-decision:` event ID;
- a valid observation payload;
- a correctly computed payload digest;
- a correctly computed event-envelope digest.

Recovery must reject it as an invalid durable event envelope rather than treating digest consistency as proof that the event could have been accepted through the CSD API.

The test uses a unique payload so the content-addressed payload table remains valid.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 329 passed | 3.087s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 329 passed | 17.886s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- Hashes detect accidental or partial corruption; they are not keyed signatures and do not authenticate a database writer with direct file access.
- Continue reviewing replay semantics, duplicate proposal identity across event types, projection reconciliation, and backup/restore behavior.
