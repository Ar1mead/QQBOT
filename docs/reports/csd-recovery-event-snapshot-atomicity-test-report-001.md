# CSD Recovery Event-Snapshot Atomicity — Test Report 001

> Status: **hosted CI passed on Ubuntu and Windows; user-local Windows verification pending**  
> Tested code/test commit: `ff9f19acf6fe6ccb0c42a8824f5900f73643e7db`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43692297727)  
> Workflow run: **#282** — success on both matrix jobs

## 1. Finding

Recovery previously read and validated the event table before opening its `BEGIN IMMEDIATE` transaction. A second store connection could append an event after Recovery fetched its rows but before Recovery acquired the write transaction.

In that interleaving, Recovery could rebuild projections from the older parsed event list, omit the newly committed event from its replay, and still return success. The event would remain in the authoritative event table while its rebuildable projection was absent.

This was a snapshot-ordering race, not a failure of SQLite's transaction atomicity once the transaction had begun.

## 2. Fix

Recovery now acquires the writer reservation before:
- running SQLite integrity and foreign-key checks;
- reading and validating the authoritative event stream;
- clearing rebuildable projections;
- replaying events;
- calculating the returned projection counts.

The event snapshot and its rebuild therefore share one serialized write transaction. A concurrent writer cannot commit an event between the snapshot query and projection rebuild. Recovery returns counts from the same locked snapshot it replayed.

Any validation or replay failure rolls the entire projection rebuild back through the existing transaction context manager.

## 3. Regression test

A deterministic two-connection test seeds an initial event, then wraps the Recovery transaction entry so a second store appends another event at the exact boundary where the old implementation had already read its event rows but had not yet acquired its write transaction.

The test asserts that Recovery includes both events and that the event count in the store agrees with the returned replay count. The old ordering would have returned a stale count of one while the event table contained two.

## 4. Hosted verification

Follow-on Recovery envelope hardening is covered separately in [durable event-envelope validation report](csd-durable-event-envelope-validation-test-report-001.md).

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 328 passed | 2.916s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 328 passed | 17.533s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next review

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- The regression covers the event-snapshot race at transaction acquisition; it is not a broad multi-process stress test.
- Continue adversarial review of duplicate event/proposal identities, replayed event semantics, projection reconciliation, and migration/reopen behavior.
- Power-loss durability, backup/restore, and local filesystem behavior remain unverified.
