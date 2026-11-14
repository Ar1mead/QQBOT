# Life Engine reference slice

This directory contains an isolated, provider-neutral proposal layer for the first motivation and deliberation experiments.

## Files

- `contracts.py` — typed motivation signals, goal state, trusted activity options, goal proposals, and deliberation choices.
- `engine.py` — read snapshot -> ask deliberator -> validate references and hard admissibility -> submit a pending proposal to a CSD-facing sink.
- Active activity snapshots carry current permission and stop-condition state; continuation is blocked after permission revocation or a met stop condition. Stopping/continuing an external side-effect activity is flagged for ASM governance. A new activity may be motivated by an active signal or by an accepted ongoing goal; it must not be source-free.
- `__init__.py` — package exports.

## Current behavior

The prototype can represent:
- needs, interests, curiosity, affect, commitments, and opportunities as distinct signals;
- user-requested, external-opportunity, and internally originated sources;
- candidate goals with origin references, success conditions, stop conditions, and review conditions;
- start, continue, wait, request-information, pause, abandon, revise, decline, stop, and no-op choices;
- trusted activity options with explicit capability, prerequisite, and side-effect metadata;
- a distinction between read-only activities and choices requiring ASM governance.

The origin class is derived from the referenced snapshot signals. The deliberator cannot declare its own goal to be internally initiated. User-requested work and external opportunities remain distinguishable from internally initiated goals.

A selected side-effecting activity is only marked as requiring ASM governance. No action is dispatched. The package has no browser, shell, network client, platform adapter, or action executor.

## Explicit limitations

- No real model or deliberation provider is connected.
- No CSD snapshot reader or proposal sink adapter is implemented.
- No drive/interest/affect learning or update reducer is implemented.
- No durable goal/commitment/activity event schema has been approved or implemented in CSD.
- No goal conflict resolution, long-running activity monitor, or autonomous scheduler is implemented.
- Local validation is not a security boundary; CSD must independently validate event schema, state version, provenance, permissions, and lifecycle transitions.
- The current activity permission fields are trusted snapshot inputs, not grants created by the deliberator.
- A no-op is a valid proposed choice, not a failed task.

Run the isolated tests from the repository root:

```powershell
py -3.12 -m unittest discover -s tests -p "test_life_engine.py" -v
```

The design contract and proposed test coverage are in:
- [Motivation, Goals, and Intentions Contract](../../docs/design/motivation-and-life-engine-contract.md)
- [Motivation and Life-Engine Test Contract](../../docs/design/motivation-and-life-engine-test-contract.md)

This is a reference prototype, not evidence of subjective desire, consciousness, or a complete autonomous individual.
