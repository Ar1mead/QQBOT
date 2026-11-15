# Life Engine reference slice

This directory contains an isolated, provider-neutral proposal layer for the first motivation and deliberation experiments.

## Files

- `contracts.py` — typed motivation signals (including CSD signal version, subject, and evidence polarity), goal state, trusted activity options, goal proposals, and deliberation choices.
- `csd_adapter.py` — maps event-verified CSD signal projections into Life Engine inputs and provides a snapshot reader backed by CSD's atomic, integrity-checked signal read; it does not authenticate the caller.
- `motivation.py` — validates evidence-grounded motivation update proposals against a trusted snapshot, including signal statement/version, supporting/counterevidence, and source-origin restrictions; it does not accept or persist signal state.
- `engine.py` — read snapshot -> ask deliberator -> validate references and hard admissibility -> submit a pending proposal to a CSD-facing sink.
- Active activity snapshots carry current permission and stop-condition state; continuation is blocked after permission revocation or a met stop condition. Stopping/continuing an external side-effect activity is flagged for ASM governance. A new activity may be motivated by an active signal or by an accepted ongoing goal; it must not be source-free. Ordinary activity options cannot advance paused or blocked goals.
- `__init__.py` — package exports.

## Current behavior

The prototype can represent:
- needs, interests, curiosity, affect, commitments, and opportunities as distinct signals;
- CSD-derived immutable origin classes (`internally_initiated`, `user_requested_encounter`, `externally_exposed`, `mixed_origin`);
- CSD-derived interest maturity and voluntary-encounter lineage, without rewriting the signal's initial origin;
- goal snapshots distinguish candidate, active, paused, blocked, satisfied, abandoned, and superseded states; only active goals may serve as current activity targets;
- candidate goals carry origin references and exact source signal-version lineage derived from the trusted snapshot, plus success, stop, and review conditions;
- start, continue, wait, request-information, pause, abandon, revise, decline, stop, and no-op choices;
- trusted activity options with explicit capability, prerequisite, and side-effect metadata;
- a distinction between read-only activities and choices requiring ASM governance.

Goal origin and exact source signal versions are derived from the referenced snapshot signals' CSD-owned state. The derived versions are proposal metadata only; CSD must independently resolve and verify them before persisting a goal. An initially user-requested or externally exposed interest that later develops an emerging pattern of voluntary encounters produces mixed goal lineage; its original origin is never rewritten as purely internal. The deliberator cannot declare its own goal to be internally initiated.

A selected side-effecting activity is only marked as requiring ASM governance. No action is dispatched. The package has no browser, shell, network client, platform adapter, or action executor.

## Explicit limitations

- No real model or deliberation provider is connected.
- No live CSD snapshot reader or proposal sink adapter is implemented. The pure `csd_adapter.py` projection mapper is available, but its caller must obtain records through CSD's event-integrity-checked read path.
- `motivation.py` provides proposal validation for create/reinforce/weaken/contextualize/pause/resolve operations, checks origin/event-kind compatibility, prevents evidence reuse on revisions, and distinguishes voluntary interest evidence from exposure or user-requested behavior. It does not synthesize signals, learn their semantics, accept changes, or persist them.
- No durable goal/commitment/activity event schema has been approved or implemented in CSD.
- No goal conflict resolution, long-running activity monitor, or autonomous scheduler is implemented.
- Local validation is not a security boundary; CSD must independently validate event schema, state version, provenance, permissions, and lifecycle transitions.
- The current activity permission fields are trusted snapshot inputs, not grants created by the deliberator.
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
