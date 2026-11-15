# CSD Motivation Integration Test Report 001

## Result

**Result: PASS — hosted CI completed successfully.**

- Repository: `Ar1mead/QQBOT`
- Branch: `feature/csd-cognitive-memory-slice`
- Verified commit: `5f2b0dcc3d2682ed128b506de46d328c5f9820a1`
- Workflow run: [CSD cognitive slice tests #125](https://github.com/Ar1mead/QQBOT/actions/runs/43664862182)
- Linux runner: GitHub-hosted Ubuntu 26.04.1 — Python 3.12.16 / SQLite 3.46.1
- Windows runner: GitHub-hosted `windows-latest` — Python 3.12.10 / SQLite 3.49.1

Both operating-system jobs passed `python -m compileall -q core tests` and the full `python -m unittest discover -s tests -v` run (244 tests each). The Windows runner is a useful platform-compatibility check, but it is not the user's own Windows 11 / Python 3.12.14 machine.

## Exact commands

```bash
python -m compileall -q core tests
python -m unittest discover -s tests -v
```

Both commands completed successfully. Full test discovery reported:

```text
Ran 244 tests in 1.712s
OK
```

The workflow also ran the individual cognitive, motivation, proposal-pipeline, grounded-memory, retrieval, semantic-review, persistence, and Life Engine test modules. Every step passed.

## Migration coverage

The earlier migration test was invalid: it first created v2 motivation decisions and projections, then removed the v2 projection tables while relabelling the database as schema v1. That combination cannot represent a legitimate v1 database because motivation events/projections were introduced in v2.

The corrected migration test now:
1. Creates legacy observation and memory-proposal events.
2. Accepts a memory and records the legacy event/projection state.
3. Removes only the v2 motivation tables and sets the schema marker to v1.
4. Reopens the database and verifies migration to v2 while preserving legacy events, accepted-memory state, and proposal data.

A separate failure-path test deliberately creates a table-name collision partway through migration. It verifies that the migration transaction rolls back partial DDL and leaves `user_version` at 1.

## Projection reconciliation hardening

The first consistency check compared the latest motivation projection with its version-history table. That could miss coordinated corruption if both tables were changed to the same incorrect value. The check now reconciles:
- every motivation proposal projection row against its immutable proposal event, including terminal decision status and decision-event identity;
- every accepted signal version against the signal object embedded in its authoritative decision event;
- each latest-signal projection against the highest event-backed signal version.

Tests deliberately corrupt both signal projection tables identically and separately alter a proposal's projected status. Both cases are detected; Recovery rebuilds the correct projections from the event history.

A further idempotency test submits a second event for an existing immutable motivation proposal with a forged source component. The duplicate is rejected and the attempted event is rolled back; valid duplicate submissions remain idempotent.

Lifecycle coverage now includes create, reinforce, weaken, contextualize, pause, and resolve transitions. In this prototype, weakening is represented by appending counter-evidence; there is not yet a continuous strength/confidence or affect-dynamics model.

## Scope and limitations

This is hosted Linux verification only. It does **not** establish that the code has been tested on the user's Windows 11 / Python 3.12.14 environment.

The tests verify deterministic prototype behavior, persistence, migration, projections, and Recovery invariants. They do not prove:
- that caller-supplied adapter metadata authenticates an adapter;
- that platform/user provenance claims are truthful;
- that evidence semantically proves a real interest, need, feeling, or desire;
- that this deterministic rules layer constitutes autonomous cognition;
- Windows-specific locking, process termination, backup interruption, or power-loss behavior.

The motivation decision path remains deterministic CSD scaffolding. No model/provider, platform adapter, or external action executor is connected by this slice. The `weaken` operation records counter-evidence but does not yet calculate a numeric decrease in motivation strength.
