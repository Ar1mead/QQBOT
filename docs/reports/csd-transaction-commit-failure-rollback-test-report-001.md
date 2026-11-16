# CSD SQLite Commit-Failure Rollback — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `2e18abd66f87058801925689f22bd2811d87f9b1`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43693030270)  
> Workflow run: **#293** — success on both matrix jobs

## 1. Finding

The shared SQLite transaction context manager rolled back when the body raised an exception, but delegated successful-body commit directly to `COMMIT` without handling a commit-time failure.

SQLite can reject `COMMIT` while leaving the transaction active—for example, when a deferred foreign-key constraint fails at commit. In that case the context manager propagated the error but left the connection inside the failed transaction, which could cause later operations to fail with a nested-transaction error or observe uncommitted state.

## 2. Fix

The transaction context manager now:
- explicitly rolls back when the transaction body raises;
- attempts `commit()` when the body succeeds;
- catches commit-time exceptions;
- rolls back if SQLite still reports an active transaction;
- re-raises the original commit error.

The rollback is conditional on `in_transaction`, avoiding an unnecessary second rollback when SQLite has already ended the transaction.

## 3. Regression test

The new test opens the CSD transaction, enables deferred foreign-key checking, and inserts an event row referencing a missing payload. The body completes, but SQLite rejects the commit.

The test verifies:
- the expected `sqlite3.IntegrityError` is raised;
- the transaction is no longer active;
- no event row was committed;
- a subsequent valid event submission succeeds on the same store connection.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 331 passed | 1.491s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 331 passed | 22.279s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- This covers a deferred-constraint commit failure, not every possible I/O, disk-full, process-crash, or power-loss scenario.
- Continue review of concurrent writers, Recovery, event identity, migration/reopen behavior, and backup/restore guarantees.
