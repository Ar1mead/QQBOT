# CSD Cognitive Slice — Hosted Test Report 002

> Status: **hosted CI passed; Windows-local verification pending**  
> Tested commit: `7d57ed2dfbb3bed76fe8208de79a8cef49bdc4cf`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43607709889)  
> Workflow job: `132485859315` — success

## 1. Environment

- Runner: GitHub-hosted Ubuntu 26.04
- Python: CPython 3.12.16
- Dependencies: Python standard library only
- Source/test files at the tested commit were checked out from the private GitHub repository.

## 2. Results

| Check | Result |
|---|---:|
| `python -m compileall -q core tests` | Passed |
| v1 cognitive-memory store | 22 passed |
| v1 provider-neutral proposal pipeline | 11 passed |
| Grounded-memory v2 store and decision path | 24 passed |
| Grounded-memory v2 provider pipeline | 11 passed |
| Accepted-memory retrieval | 13 passed |
| Original generic CSD persistence baseline | 16 passed |
| **Total** | **97 passed** |

All six unittest suites passed in the same workflow run. The original generic `CSDStore` implementation and its 16 baseline tests remain unchanged.

## 3. What was verified

### Event and authority path
- Observation events do not automatically become memories.
- Candidate proposals remain pending until CSD evaluation.
- Public submission cannot forge CSD decision events or claim the reserved decision ID namespace.
- Event and proposal identity conflicts are detected.
- CSD decision and accepted-memory projection updates roll back atomically on injected failure.
- Repeated and concurrent proposal evaluation produce one durable decision.

### Grounded-memory v2
- Source assertions must cite an existing text observation.
- Source assertion text must equal its quoted text.
- The exact Unicode-codepoint slice must equal the quote.
- Non-text observation modalities are rejected in the text-only v2 path, both before provider invocation and during CSD evaluation.
- Inference claims must refer directly to source-assertion claims; inference chains are rejected.
- Accepted memory preserves claim types, evidence locators, provider provenance, and decision references.
- Semantic entailment and source truth are not established.

### Provider boundary
- v1 and v2 proposal pipelines call providers outside CSD write transactions.
- Pipelines bind evidence and state-version provenance and submit pending proposals only.
- Provider failure, malformed output, and invalid offsets do not mutate accepted state.
- No real model API is connected; tests use synthetic providers.

### Memory Retrieval
- Accepted-only retrieval works across legacy v1 and grounded v2 memory shapes.
- Substring, memory-kind, epistemic-type, evidence-event, limit, and offset filters work.
- Single-memory retrieval preserves full provenance.
- Retrieval is read-only.
- Retrieval fails closed when the accepted-memory projection count disagrees with durable accepted decisions and requires Recovery.

### Recovery and event order
- Recovery rebuilds accepted memories, proposals, claim metadata, and evidence locators from the event log.
- Recovery does not call the proposal evaluator or external tools.
- During replay, a decision's state version is validated against the event-history prefix preceding that decision. It is not compared against future decision events that have not yet been replayed.
- The original generic persistence spike's recovery/concurrency/idempotency tests still pass.

## 4. Defect discovered and corrected

When retrieval was changed to fail closed on an incomplete accepted-memory projection, the existing recovery test first needed to be updated: it should expect an integrity error before Recovery, not an empty result.

That exposed a deeper recovery bug. Decision replay was comparing the partially rebuilt memory projection with the count of all accepted decisions in the complete event log, including future decisions. The check now uses the event sequence prefix before the decision currently being replayed.

The retrieval recovery test with multiple accepted memories and the complete suite pass after this correction.

## 5. Explicit limits

This hosted result does **not** prove:
- operation on the user's Windows 11 / Python 3.12.14 machine;
- Windows process-lock behavior, power-loss durability, or multi-process crash recovery;
- strong isolation against hostile Python code in the same process;
- semantic entailment or objective truth;
- calibrated confidence;
- real model-provider quality;
- image/video/audio perception or multimodal evidence locators;
- memory consolidation, forgetting, privacy/retention policy, diary motivation, personality evolution, or autonomous life behavior;
- integration with DSH, SurfCore, Bilibili, QQ, or ASM.

The current retrieval query is lexical substring filtering, not semantic search. The semantic-review boundary is a design proposal only; no reviewer is implemented or connected.

## 6. Next gates

1. Validate the repository test suites on Windows 11 / Python 3.12.14 before any runtime integration.
2. Define and implement the semantic-review event path for inference claims, keeping reviewer output non-authoritative and bound to immutable proposal/claim digests.
3. Add memory lifecycle semantics (revision, supersession, consolidation, accessibility/forgetting) without destructive history rewrites.
4. Only after those boundaries are tested, connect a real provider in pending/shadow mode.
