# CSD Motivation Integration Test Report 001

## Result

<badge>Hosted CI passed</badge>

- Repository: `Ar1mead/QQBOT`
- Branch: `feature/csd-cognitive-memory-slice`
- Verified commit: `13db2b4540c98ffb3114f64981841c7c8843ae1c`
- Workflow run: [CSD cognitive slice tests #117](https://github.com/Ar1mead/QQBOT/actions/runs/43664232770)
- Runner: GitHub-hosted Ubuntu 26.04.1
- Python: 3.12.16
- SQLite: 3.46.1

## Exact commands

```bash
python -m compileall -q core tests
python -m unittest discover -s tests -v
```

Both commands completed successfully. Full test discovery reported:

```text
Ran 240 tests in 1.245s
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

## Scope and limitations

This is hosted Linux verification only. It does **not** establish that the code has been tested on the user's Windows 11 / Python 3.12.14 environment.

The tests verify deterministic prototype behavior, persistence, migration, projections, and Recovery invariants. They do not prove:
- that caller-supplied adapter metadata authenticates an adapter;
- that platform/user provenance claims are truthful;
- that evidence semantically proves a real interest, need, feeling, or desire;
- that this deterministic rules layer constitutes autonomous cognition;
- Windows-specific locking, process termination, backup interruption, or power-loss behavior.

The motivation decision path remains deterministic CSD scaffolding. No model/provider, platform adapter, or external action executor is connected by this slice.
