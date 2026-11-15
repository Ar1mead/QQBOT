# CSD Goal Proposal Snapshot Chronology — Test Report 001

> Status: **hosted CI passed on Linux and Windows; user-local Windows verification pending**  
> Tested code commit: `fc266b92851f5278b353368e961226d3e3ba9d0c`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43689478017)  
> Workflow run: **#238** — success on both matrix jobs

## 1. Finding

Adversarial review found a chronology gap in candidate-goal and activation proposals.

CSD compared a proposal's `based_on.state_version` with the current version at decision time, but did not ensure that the claimed version had existed when the proposal event itself was appended. A malformed or hostile proposal could therefore claim a future version, be appended before the relevant state existed, and become apparently current after later accepted transitions advanced the shared version.

That violates the meaning of `based_on`: it identifies the snapshot from which the proposal was formed, not a version that may become valid retroactively.

## 2. Change

CSD now checks the authoritative shared state version immediately before the proposal event's sequence:

- Candidate-goal batch proposals cannot claim a version greater than the state that existed when the event was appended.
- Candidate→active activation proposals use the same rule.
- A stale proposal whose claimed version is lower than the current version may still be recorded; its later evaluation is deferred under the existing no-rebase rule.
- Projection reconciliation independently checks the chronology invariant against event order.
- Recovery/replay encounters the same invariant and fails closed for an invalid event history.

The guard does not require exact equality at append time: a legitimate deliberation can become stale between snapshot read and event submission. Such a proposal may be recorded but cannot be silently rebased.

## 3. Regression coverage

Two new tests were added:

1. A candidate-goal proposal claims state version 1 while the event is appended at version 0. CSD rejects the event; later creation of the referenced source signal cannot retroactively make the proposal exist.
2. An activation proposal claims state version 2 while appended at version 0, before its target goal exists. CSD rejects it; later signal and candidate-goal creation cannot make that old proposal valid.

## 4. Hosted verification

Both GitHub-hosted runners passed:

| Runner | Python / SQLite | Full test discovery | Time |
|---|---|---:|---:|
| Ubuntu | Python 3.12.16 / SQLite 3.46.1 | 303 passed | 1.807s |
| Windows | Python 3.12.10 / SQLite 3.49.1 | 303 passed | 13.509s |

The workflow also passed `python -m compileall -q core tests` and all focused test steps.

## 5. Limitations and next gate

- This is hosted Windows CI, not execution on the user's own Windows 11 / Python 3.12.14 machine.
- It does not establish power-loss durability, process-interruption safety, or multi-process stress behavior.
- The CSD/ASM specifications remain working contracts, not fully frozen normative specifications.
- The Life Engine still has no real deliberator/model provider; this guard improves proposal chronology but does not create autonomous cognition.

Next: continue event-order/replay and migration adversarial review, then design the remaining goal lifecycle transitions as distinct, evidence-bearing CSD event families.
