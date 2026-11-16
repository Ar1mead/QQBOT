# CSD Goal Activation — Hosted Test Report 001

> Status: **hosted CI passed on Linux and Windows; user-local Windows verification pending**  
> Tested commit: `d167794c7ae52d9c9dcdcc13d5d98abf438a3fba`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43688976461)  
> Workflow run: **#230** — success on both matrix jobs

## 1. Environments

| Runner | Python | SQLite |
|---|---|---|
| GitHub-hosted Ubuntu | CPython 3.12.16 | 3.46.1 |
| GitHub-hosted Windows | CPython 3.12.10 | 3.49.1 |

The workflow checked out the exact tested commit from the private repository. No third-party Python dependencies were required. Complete discovery took 2.416s on Ubuntu and 29.157s on Windows.

## 2. Results

Both runners passed:

- `python -m compileall -q core tests`
- All focused CSD, Life Engine, motivation, memory, and persistence suites
- Complete unittest discovery: **301 tests passed**

The focused CSD goal-state suite contains 29 tests, including candidate-goal and adversarial activation coverage.

## 3. Implemented activation path

The tested implementation adds:

- Schema v3→v4 migration creating the rebuildable `goal_activation_proposals` projection.
- Separate `life.goal_activation_proposed.v1` and `life.goal_activation_decided.v1` event types.
- CSD-authoritative accepted/rejected/deferred activation decisions.
- Exact shared state-version and goal-version checks; no silent rebasing.
- Candidate→active as a separate goal version transition.
- Accepted activation increments shared `state_version` once and the goal version once.
- Original candidate origin, source signal-version references, creation lineage, and creation time are preserved.
- Event-order goal projection reconciliation and Recovery from the append-only event history.
- Life Engine `activate_goal` choice validation with an exact expected goal version.
- A narrow CSD proposal sink for candidate-goal and activation proposals. It never dispatches activities.

## 4. Activation tests

Coverage includes:

1. A candidate remains unchanged until an explicit activation proposal is accepted.
2. Accepted activation creates goal version 2 with status `active` and increments shared state version once.
3. Stale shared state versions and stale goal versions are deferred without rebasing.
4. Unknown goals and already-active goals are rejected.
5. Two proposals against one candidate cannot both activate it.
6. Conflicting proposal identity rolls back; identical event/proposal identities remain idempotent.
7. Original goal origin and signal-version lineage remain unchanged even after the source motivation signal is paused.
8. Goal and activation-proposal projection tampering is detected; Recovery rebuilds the active goal.
9. A schema-v3 database migrates to v4; an injected v3→v4 DDL collision rolls back the schema version and partial migration.
10. The public Event Submit path cannot forge a CSD activation decision.
11. An injected failure while writing the new goal version rolls back the decision event and all projections atomically.
12. Coordinated tampering of both latest-goal and goal-version projections is detected and repaired from events.
13. The Life Engine activation sink persists only the goal transition; it does not create an activity or capability.

## 5. Explicit limitations

This result does **not** establish:

- Test execution on the user's own Windows 11 / Python 3.12.14 environment.
- Sudden power-loss durability, Windows-specific process interruption, or multi-process stress behavior.
- A hostile-code security boundary inside the Python process.
- Real model-based deliberation, subjective desire, consciousness, or autonomous goal formation.
- Goal pause/resume/blocked/satisfied/abandoned/superseded/revise transitions.
- Activity scheduling or execution, ASM governance, platform adapters, or Bilibili/QQ integration.

The Life Engine has a provider-neutral activation choice and CSD sink, but no real deliberator/model provider is connected. Activation is an internal state transition only; it grants no permission and starts no activity.

## 6. Next validation gate

Run the exact repository test suite on the user's Windows 11 / Python 3.12.14 machine after the repository is cloned locally. Then add target-machine process interruption, backup/recovery, and durability checks before connecting a real provider or runtime integration.
