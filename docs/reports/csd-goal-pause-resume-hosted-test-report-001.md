# CSD Goal Pause/Resume — Hosted Test Report 001

> Status: **hosted CI passed on Linux and Windows; user-local Windows verification pending**  
> Tested code/test commit: `66ac0b157ba7c735726499fa60b2b38d21265c87`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43690735564)  
> Workflow run: **#264** — success on both matrix jobs

## 1. Implemented scope

CSD now supports explicit goal pause/resume as a separate lifecycle event family:

- `life.goal_pause_resume_proposed.v1`
- `life.goal_pause_resume_decided.v1`

The operation is a strict union of `pause` and `resume`; it is not a generic status setter.

Allowed transitions:
- `active → paused` through an explicit `pause_goal` choice;
- `paused → active` through an explicit `resume_goal` choice.

Each proposal carries the exact shared `based_on.state_version`, target `goal_id`, `expected_goal_version`, operation, rationale, and proposer metadata.

## 2. CSD authority and persistence

- CSD independently evaluates the current state and exact goal version.
- Stale shared state or goal versions are deferred without rebasing.
- Pause on a non-active goal and resume on a non-paused goal are rejected.
- Accepted transitions append goal version n+1 and increment shared state_version exactly once.
- Rejected/deferred decisions do not create a goal version or increment state_version.
- Original goal identity, origin class, source-signal version references, creation lineage, and prior versions are preserved.
- Pause/resume does not start, stop, schedule, or execute an activity and does not grant capability.
- Decision event identity and retry behavior are proposal-scoped and idempotent.

## 3. Migration, projections, and Recovery

- Added schema v4→v5 migration for the rebuildable `goal_pause_resume_proposals` projection.
- Legacy v1→v5 and v3→v5 migration paths are covered.
- v4→v5 migration rollback is tested under an injected DDL collision.
- Goal projection reconciliation now includes pause/resume proposal/decision events and all resulting goal versions.
- Recovery rebuilds the proposal table, goal version history, and latest goal state from authoritative events; it does not call a model or executor.
- Tampering with the pause/resume proposal projection is detected and repaired by Recovery.
- Recovery is tested across both `active → paused` and `paused → active` transitions.
- A pause/resume proposal that claims a future `based_on.state_version` is rejected at append time and cannot become valid after later state transitions catch up.
- Competing pause proposals against the same goal/version cannot both succeed: the first is accepted and the second is deferred.
- Reusing a pause/resume proposal ID with conflicting immutable content is rejected.
- An injected goal-version insert failure proves the decision event, proposal status, goal version, and shared state version roll back atomically.

## 4. Life Engine integration

- Added `resume_goal` to the provider-neutral choice contract.
- Pause/resume validation requires the correct current goal status and exact expected goal version.
- Pause/resume cannot be combined with candidate-goal creation or activity selection.
- The CSD proposal sink persists and evaluates pause/resume only; no activity is dispatched.

## 5. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 322 passed | 2.205s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 322 passed | 25.171s |

The workflow also passed `python -m compileall -q core tests` and every focused test step.

## 6. Explicit limitations

- This is hosted Windows CI, not the user's own Windows 11 / Python 3.12.14 environment.
- No real deliberator/model provider is connected; pause/resume requires an explicit supplied choice.
- Blocked/unblocked, satisfied, abandoned, superseded, and revise remain unimplemented.
- Blocked/unblocked still require a trusted ASM/prerequisite evidence contract.
- No activity execution, scheduler, external adapter, or permission grant is included.
- Hosted CI does not establish power-loss durability, process-interruption safety, or multi-process stress behavior.

## 7. Next validation gate

Continue adversarial review of event chronology, projection reconciliation, Recovery, and migration behavior. Then run the exact suite on the user's Windows 11 / Python 3.12.14 environment when the repository is cloned locally. Design blocked/unblocked only after the trusted ASM evidence boundary is defined.
