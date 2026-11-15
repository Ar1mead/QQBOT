# Life Engine reference slice

This directory contains an isolated, provider-neutral proposal layer for the first motivation and deliberation experiments.

## Files

- `contracts.py` — typed motivation signals (including CSD signal version, subject, and evidence polarity), goal state, trusted activity options, goal proposals, and deliberation choices.
- `csd_adapter.py` — maps event-verified CSD signal and goal projections (including goal versions) into Life Engine inputs, provides an atomic snapshot reader, and persists candidate/activation proposals through a narrow CSD sink; it does not authenticate the caller.
- `core/csd/goals.py` — CSD-owned candidate-goal creation, explicit activation, pause/resume proposal/decision paths, versioned projections, source lineage, and Recovery.
- `motivation.py` — validates evidence-grounded motivation update proposals against a trusted snapshot, including signal statement/version, supporting/counterevidence, and source-origin restrictions; it does not accept or persist signal state.
- `engine.py` — read snapshot -> ask deliberator -> validate references and hard admissibility -> submit a proposal to the CSD-facing sink. The sink persists candidate-goal and explicit activation transitions; it does not execute activities.
- Active activity snapshots carry current permission and stop-condition state; continuation is blocked after permission revocation or a met stop condition. Stopping/continuing an external side-effect activity is flagged for ASM governance. A new activity may be motivated by an active signal or by an accepted ongoing goal; it must not be source-free. Ordinary activity options cannot advance paused or blocked goals.
- `__init__.py` — package exports.

## Current behavior

The prototype can represent:
- needs, interests, curiosity, affect, commitments, and opportunities as distinct signals;
- CSD-derived immutable origin classes (`internally_initiated`, `user_requested_encounter`, `externally_exposed`, `mixed_origin`);
- CSD-derived interest maturity and voluntary-encounter lineage, without rewriting the signal's initial origin;
- goal snapshots distinguish candidate, active, paused, blocked, satisfied, abandoned, and superseded states; only active goals may serve as current activity targets;
- candidate goals carry CSD-derived origin references and exact source signal-version lineage, plus success, stop, and review conditions;
- start, continue, wait, request-information, pause, resume, abandon, revise, decline, stop, and no-op choices;
- trusted activity options with explicit capability, prerequisite, and side-effect metadata;
- a distinction between read-only activities and choices requiring ASM governance.

Goal origin and exact source signal versions are derived from the referenced snapshot signals' CSD-owned state. The derived versions are proposal metadata only; CSD must independently resolve and verify them before persisting a goal. An initially user-requested or externally exposed interest that later develops an emerging pattern of voluntary encounters produces mixed goal lineage; its original origin is never rewritten as purely internal. The deliberator cannot declare its own goal to be internally initiated.

A selected side-effecting activity is only marked as requiring ASM governance. No action is dispatched. The package has no browser, shell, network client, platform adapter, or action executor.

## Explicit limitations

- No real model or deliberation provider is connected.
- A live CSD snapshot reader is implemented for accepted signals and versioned goals. The CSD-facing sink can persist candidate-goal proposals and explicit candidate→active transitions. No real model provider is connected, so goal creation/activation still requires a supplied deliberation proposal.
- `motivation.py` provides proposal validation for create/reinforce/weaken/contextualize/pause/resolve operations, checks origin/event-kind compatibility, prevents evidence reuse on revisions, and distinguishes voluntary interest evidence from exposure or user-requested behavior. It does not synthesize signals, learn their semantics, accept changes, or persist them.
- CSD persists candidate and active goal states, and the branch implements explicit pause/resume transitions through a separate proposal/decision event family (hosted CI run #270 passed). Blocked/satisfied/abandoned/superseded/revise transitions, commitments, and activity execution are not yet implemented.
- No goal conflict resolution, long-running activity monitor, or autonomous scheduler is implemented.
- Local validation is not a security boundary; CSD must independently validate event schema, state version, provenance, permissions, and lifecycle transitions.
- The current activity permission fields are trusted snapshot inputs, not grants created by the deliberator. CSD also rejects proposal snapshot versions that did not exist at proposal append time across memory, grounded-memory, motivation, and goal proposal families.
- A no-op is a valid proposed choice, not a failed task.

Run the isolated tests from the repository root:

```powershell
py -3.12 -m unittest discover -s tests -p "test_motivation_synthesis.py" -v
py -3.12 -m unittest discover -s tests -p "test_life_engine.py" -v
```

The design contracts and proposed test coverage are in:
- [Motivation, Goals, and Intentions Contract](../../docs/design/motivation-and-life-engine-contract.md)
- [Motivation and Life-Engine Test Contract](../../docs/design/motivation-and-life-engine-test-contract.md)
- [Motivation Signal Formation and Lifecycle](../../docs/design/motivation-signal-formation-and-lifecycle.md)
- [Motivation Signal CSD Integration Contract](../../docs/design/motivation-signal-csd-integration-contract.md)

This is a reference prototype, not evidence of subjective desire, consciousness, or a complete autonomous individual.
