# CSD Cognitive-Memory Slice — Hosted Test Report 001

> Status: **hosted CI passed; Windows-local verification pending**  
> Tested commit: `1c05de81891ee889a6a6c9a239e9606eeb2c952e`  
> Current branch: `feature/csd-cognitive-memory-slice`  
> Current branch HEAD at report creation: `3d525e47a05e46c8e2d855f63297c59f038b5154`

## 1. Environment

- Runner: GitHub-hosted Ubuntu 26.04
- Python: CPython 3.12.16
- SQLite: Python standard-library SQLite build on the hosted runner
- Dependencies: Python standard library only
- Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43604272330)

The current branch has three documentation-only commits after the tested commit. A compare check confirmed no source or test files changed after the successful run.

## 2. Results

| Check | Result |
|---|---:|
| `python -m compileall -q core tests` | Passed |
| Cognitive-memory slice suite | 21 tests passed |
| Original CSD persistence baseline | 16 tests passed |
| Total | **37 tests passed** |

Workflow job: `132475427954` — success.

## 3. Cognitive-memory test coverage

The 21 tests cover:
- observation is not automatically accepted as memory;
- candidate proposal remains separate from accepted memory;
- CSD evaluation creates one accepted memory with evidence and decision provenance;
- public Event Submit cannot forge a CSD decision or claim its reserved event-ID namespace;
- event idempotency and changed-content conflicts;
- proposal identity deduplication and changed-content conflicts;
- valid and missing evidence outcomes;
- unsupported event types are rejected;
- stale proposal deferral;
- decision event and memory projection rollback together on injected failure;
- restart and recovery preserve accepted memory;
- recovery does not call the evaluator;
- recovery rebuilds a damaged projection from the event log;
- evaluation refuses to proceed when the accepted-memory projection is inconsistent with durable accepted decisions;
- event-envelope tampering is detected;
- repeated and concurrent evaluation produce only one decision and one accepted memory.

## 4. Baseline preservation

The original `CSDStore` source and its 16 tests were not modified by the cognitive slice. The new `CognitiveMemoryStore` is isolated in `core/csd/cognitive.py` and uses a separate SQLite database/schema.

This avoids silently changing the baseline spike. It does not settle the final production database topology or migration strategy.

## 5. Issues found and corrected during CI

The first CI attempts were not green:
1. The first compile check found an incorrectly escaped newline in `core/csd/__init__.py`. The export file was rewritten with valid Python syntax.
2. The first concurrency test attempted to use a SQLite connection from a thread other than the one that created it. The test was corrected to create one independent connection inside each worker thread. The implementation retains SQLite's default same-thread connection guard.

After those corrections, the cognitive suite and the unchanged baseline suite both passed.

## 6. What this result does not prove

This report does **not** prove:
- execution on the user's Windows 11 / Python 3.12.14 environment;
- Windows process-lock or multi-process behavior;
- sudden power-loss durability;
- production-grade authentication or isolation against hostile code in the same process;
- semantic correctness of candidate memory content;
- real-world observation, perception, autobiographical truth, memory consolidation, forgetting, or personality change;
- integration with DSH, SurfCore, Bilibili, QQ, or ASM.

The deterministic policy checks structure, evidence references, evidence type, and accepted-state version. It does not understand the meaning of the candidate text.

## 7. Next validation step

Before integrating this store with a runtime, run the test suites on the user's Windows machine using Python 3.12.14, then add Windows-specific process interruption, multi-process locking, backup/recovery, and durability tests. Do not use real personal data in the first local run.
