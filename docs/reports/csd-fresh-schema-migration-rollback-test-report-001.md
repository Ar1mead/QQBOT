# CSD Fresh-Schema Migration Rollback — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `836a6efc0c255de7c842854fd648ca7e7fbf16bf`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43692065728)  
> Workflow run: **#279** — success on both matrix jobs

## 1. Finding

The fresh-database bootstrap (`user_version = 0` → schema v1) ran its DDL inside an explicit SQLite transaction, but unlike later schema migrations it did not catch failures and explicitly roll back an open transaction.

If a DDL statement failed after earlier statements had succeeded, the connection could be left inside the migration transaction with partial schema objects still present. A subsequent initialization attempt on that connection could then fail against the partial objects.

The later v1→v2, v2→v3, v3→v4, and v4→v5 migrations already had explicit rollback handling.

## 2. Fix

The v0→v1 bootstrap now uses the same failure-handling pattern as later migrations:
- execute the initial schema DDL;
- on any exception, check whether the connection remains in a transaction;
- roll back the partial DDL and user_version update;
- re-raise the original error.

Successful initialization behavior and schema version remain unchanged.

## 3. Regression test

A new failure-injection test uses a separate, genuinely fresh database. It pre-creates a conflicting `events` table so the bootstrap fails after creating `payloads` inside its transaction.

The test verifies:
- the initialization raises the expected SQLite operational error;
- the connection is no longer in a transaction;
- `PRAGMA user_version` remains 0;
- the partially created `payloads` table is rolled back;
- the pre-existing collision table remains;
- no partially created triggers remain.

The existing v1→v2 rollback test remains isolated on its own version-1 database and continues to pass.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 327 passed | 2.891s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 327 passed | 23.342s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- The test proves transactional rollback for an injected DDL failure; it does not establish power-loss durability or filesystem-level guarantees.
- Continue reviewing migration interruption/reopen behavior, Recovery atomicity, duplicate event identity, and event/projection reconciliation.
