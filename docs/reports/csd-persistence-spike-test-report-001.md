# CSD Persistence Reference Spike — Test Report 001

- Branch: `feature/csd-persistence-spike`
- Test date: 2026-11-14
- Result: **16 tests passed**
- Status: prototype validation only; not a production acceptance report.

## Execution environment

Tests were executed in the assistant's isolated execution environment, not on the user's Windows machine:

- Python: 3.13.5
- SQLite library: 3.46.1
- Test runner: Python standard-library `unittest`
- Dependencies: Python standard library only

The user's local Python 3.12.14 environment has **not** yet been used to run this code. Compatibility with that exact local interpreter remains to be confirmed. The subprocess interruption tests ran on this isolated Linux environment; Windows process and file-locking behavior remains unverified.

## Test results

| Test | Result | What it checks |
|---|---|---|
| `test_accepts_event_and_updates_projection` | PASS | Event acceptance and atomic projection update |
| `test_duplicate_event_is_not_reduced_twice` | PASS | Idempotent duplicate submission |
| `test_same_id_with_different_payload_is_conflict` | PASS | Reused event ID with different content is rejected |
| `test_reducer_failure_rolls_back_payload_event_and_projection` | PASS | Reducer failure rolls back the whole transaction |
| `test_snapshot_plus_tail_recovers_after_reopen` | PASS | Snapshot load plus tail replay after reopening |
| `test_corrupt_snapshot_is_rejected_and_rebuilt_from_event_log` | PASS | Snapshot checksum failure falls back to event-log rebuild |
| `test_corrupt_payload_causes_safe_stop` | PASS | Payload corruption stops recovery and preserves the database |
| `test_recovery_api_has_no_action_executor_parameter` | PASS | Recovery API has no action-executor injection point |
| `test_journal_and_synchronous_mode_matrix_round_trip` | PASS | Basic reopen/recovery round-trip under WAL/DELETE × FULL/NORMAL |
| `test_process_exit_mid_transaction_rolls_back_event` | PASS | Abrupt child-process exit before commit leaves no accepted event |
| `test_process_exit_after_commit_is_safe_to_retry` | PASS | Abrupt child-process exit after commit is safely handled by idempotent resubmission |
| `test_multiple_connections_serialize_concurrent_writers` | PASS | 20 concurrent writes from 8 workers are serialized without losing events |
| `test_busy_timeout_fails_cleanly_then_retry_succeeds` | PASS | A held writer lock times out without partial writes; retry succeeds after release |
| `test_sqlite_backup_restores_event_log_and_projection` | PASS | SQLite backup restores a recoverable event log and projection |
| `test_event_envelope_tampering_causes_safe_stop` | PASS | Event-envelope digest mismatch stops recovery |
| `test_invalid_timezone_is_rejected` | PASS | Naive timestamps are rejected |

## What this proves

The current prototype can:
- persist a synthetic event and update a deterministic projection;
- avoid applying the same event twice;
- reject conflicting event-ID reuse;
- roll back payload, event, and projection changes together when the reducer fails;
- recover a projection using a snapshot and subsequent event tail;
- reject a damaged snapshot and rebuild from the event log;
- stop when payload integrity fails;
- run basic round-trip checks under four SQLite journal/synchronous combinations;
- survive simulated abrupt process exit before commit without accepting a partial event;
- safely handle a process exit after commit but before the caller receives the result, using idempotent resubmission;
- serialize 20 concurrent writes from eight independent worker connections;
- time out cleanly under a held writer lock and accept a retry after lock release;
- restore a recoverable event log and projection using SQLite's backup API;
- detect event-envelope tampering during recovery.

## What this does not prove

This run does **not** establish:
- behavior on the user's Windows 11 / Python 3.12.14 installation;
- Windows-specific process termination and file-locking behavior;
- physical power-loss durability;
- correctness under forced process termination at every transaction boundary;
- multi-process behavior on Windows or high-volume concurrent readers;
- backup/restore continuity;
- long-term event schema migration;
- encryption, privacy, or retention suitability;
- production readiness of WAL + FULL or any other SQLite mode.

The four-mode test is a functional round-trip test, not a comparative durability benchmark. No production mode is selected by this report.

## Next tests

1. Run the exact suite under the user's Python 3.12.14 interpreter after the user is ready to perform one local verification step.
2. Add forced process-termination tests around transaction boundaries.
3. Repeat multi-connection contention and busy-timeout tests on Windows.
4. Test backup/restore continuity across process restart and interrupted backup.
5. Review the event schema, recovery report, and privacy requirements before any real personal data is written.
