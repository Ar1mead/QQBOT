# CSD Transactionally Consistent Read Snapshots — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `b4bddf5e4836d3262d621b2ec29432bce7277719`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43693344718)  
> Workflow run: **#297** — success on both matrix jobs

## 1. Finding

The Life Engine snapshot reader already used a read transaction, but the diagnostic `get_state_snapshot()` performed its version, count, and projection-consistency reads as separate autocommit statements. A concurrent append could therefore make one returned diagnostic object combine values from different database snapshots.

## 2. Fix

A shared `_ReadTx` context manager now provides explicit read-transaction boundaries and the same rollback-on-exit-error / rollback-on-commit-failure discipline as the write transaction helper.

Both `get_life_signal_snapshot()` and `get_state_snapshot()` now use this helper. The diagnostic snapshot reads the authoritative state version, event/proposal/projection counts, and all projection-consistency checks within one SQLite read snapshot.

The consistency helpers use the same store connection, so their event-history and projection reads remain inside that snapshot. A concurrent writer on a separate connection may commit, but its changes are not mixed into the already-open reader snapshot.

## 3. Regression coverage

The new test:
1. creates an initial observation;
2. starts a diagnostic snapshot;
3. during projection validation, appends another observation through a separate SQLite connection;
4. verifies the returned snapshot still reports the original event count;
5. verifies the durable event table contains the concurrent append after the snapshot completes.

The first test draft accidentally constructed the writer connection on the main test thread and then used it from the worker thread. GitHub Actions run #296 correctly exposed SQLite's default thread-affinity guard. The test fixture was corrected so the separate connection is created, used, and closed entirely within its worker thread. This was a test-harness defect, not a production snapshot implementation failure.

## 4. Hosted verification

Both GitHub-hosted runners passed in workflow run #297:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 332 passed | 3.138s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 332 passed | 64.750s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- This verifies snapshot isolation against a concurrent append; it does not replace process-interruption, backup/restore, disk-failure, or power-loss testing.
- Continue adversarial review of event append/replay, projection reconciliation, schema migration, and durability boundaries.
