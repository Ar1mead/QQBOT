# CSD Proposal Snapshot Chronology — Cross-Domain Test Report 001

> Status: **hosted CI passed on Linux and Windows; user-local Windows verification pending**  
> Tested code/test commit: `146c0b86e58e72af6cab7f419bba7236821b6be1`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43691014899)  
> Workflow run: **#270** — success on both matrix jobs

## 1. Finding

The earlier chronology review found that goal proposals could claim a future `based_on.state_version` and become apparently current after later accepted state transitions advanced the shared version.

The same invariant was missing from ordinary memory, grounded-memory, and motivation proposal submission paths. All these proposal families use `based_on.state_version` as the snapshot from which the proposal was formed. Without an append-time check, a proposal could claim a version that did not yet exist and potentially become valid retroactively.

## 2. Cross-domain fix

A common CSD proposal chronology guard now runs after the event is assigned its authoritative sequence and before its projection is applied. It covers:

- ordinary memory proposals;
- grounded-memory v2 proposals;
- motivation proposals;
- candidate-goal batch proposals;
- goal activation proposals;
- goal pause/resume proposals.

For every covered event:
- CSD reads the authoritative shared state version immediately before the proposal's event sequence.
- A claimed version greater than that value is rejected and the event transaction rolls back.
- An older version is allowed to be recorded, because state may have changed between deliberation and submission; its later evaluation must defer rather than silently rebase.
- Recovery applies the same invariant while replaying the event stream and fails closed on impossible proposal chronology.

The goal projection retains an additional event-order consistency check as defense in depth.

## 3. New regression coverage

Three new tests verify that:
1. an ordinary memory proposal cannot claim a future snapshot version;
2. a grounded-memory proposal cannot claim a future snapshot version;
3. a motivation proposal cannot claim a future snapshot version, while a valid proposal based on the actual current version can still be accepted.

Existing goal and pause/resume tests cover the same invariant for goal-related proposal families.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 325 passed | 2.819s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 325 passed | 22.161s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next gate

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- Recovery rejects invalid chronology during replay, but this report does not claim power-loss durability, process-interruption safety, or multi-process stress validation.
- The guard establishes chronology consistency, not semantic truth, subjective desire, or autonomous cognition.
- Continue reviewing event ordering, proposal idempotency, projection reconciliation, and migration behavior; then perform the local Windows verification when the repository is cloned locally.
