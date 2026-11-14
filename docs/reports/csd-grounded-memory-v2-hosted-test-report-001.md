# Grounded Memory v2 — Hosted Test Report 001

> Status: **hosted CI passed; Windows-local verification pending**  
> Tested commit: `7d57ed2dfbb3bed76fe8208de79a8cef49bdc4cf`  
> Branch: `feature/csd-cognitive-memory-slice`  
> Workflow: [CSD cognitive slice tests](https://github.com/Ar1mead/QQBOT/actions/runs/43607709889)

## 1. Environment

- Runner: GitHub-hosted Ubuntu 26.04
- Python: CPython 3.12.16
- Dependencies: Python standard library only
- Workflow job: `132485859315` — success

## 2. Test results

| Suite | Result |
|---|---:|
| `python -m compileall -q core tests` | Passed |
| v1 cognitive-memory store | 22 passed |
| v1 provider-neutral proposal pipeline | 11 passed |
| Grounded-memory v2 store and decision path | 24 passed |
| Grounded-memory v2 provider pipeline | 11 passed |
| Accepted-memory retrieval | 13 passed |
| Original generic CSD persistence baseline | 16 passed |
| **Total** | **97 passed** |

The original generic persistence implementation and its 16 tests remain unchanged.

## 3. Grounded-memory v2 coverage

The 24 store tests cover:
- pending proposal versus accepted memory;
- exact source text range and quoted-text matching;
- Unicode code-point offsets, including a supplementary-plane emoji;
- source-assertion text must equal the exact quote;
- out-of-bounds and mismatched quotes are durably rejected;
- missing observation evidence produces `needs_more_evidence`;
- evidence that is not an observation is rejected;
- non-text observations cannot ground a text-only v2 memory;
- inference references must resolve to source-assertion claims;
- inference-to-inference chains are rejected;
- duplicate claim IDs and unsupported epistemic types are rejected;
- multiple observation sources are not silently combined in v2;
- stale proposal deferral;
- atomic decision/projection rollback;
- accepted claim and locator recovery;
- rejected proposal recovery without accepted memory;
- recovery does not call the proposal evaluator;
- event/proposal identity and payload preservation.

The 11 provider-pipeline tests cover:
- the pipeline binds the observation event ID itself;
- provider identity/version and current state version are attached by the pipeline;
- provider calls execute outside a CSD write transaction;
- candidate events remain pending until CSD evaluates them;
- typed source assertions and inference claims are preserved;
- invalid offsets and provider failures do not mutate CSD;
- empty provider output creates no proposal;
- at most one candidate is accepted per v2 pipeline call;
- non-observation input is rejected before provider invocation;
- non-text observations are rejected before provider invocation.

## 4. Accepted-memory retrieval coverage

The 10 retrieval tests cover:
- accepted-only results, excluding pending proposals;
- case-insensitive substring matching across grounded claims and legacy content;
- source-assertion versus inference filters;
- evidence-event and memory-kind filters;
- stable insertion-order limit/offset pagination;
- full-provenance single-memory lookup;
- read-only behavior with unchanged event count and authoritative state;
- list and single-record reads fail closed when the accepted-memory projection is incomplete;
- Recovery restores the retrieval results from the event history;
- invalid filter arguments, including non-string epistemic-type filters.

This API is deterministic substring/filter retrieval, not embedding-based or semantic retrieval.

## 5. Implementation boundary

The v2 event type is `cognition.grounded_memory_candidate_proposed.v1`. The grounded acceptance policy is `csd.grounded-memory-text-evidence@0.1`.

The current deterministic checks establish:
- exact source-span identity;
- source event and payload integrity;
- text-modality restriction;
- claim-ID uniqueness;
- inference reference integrity and permitted inference graph;
- provenance retention through accepted-memory retrieval and recovery.

They do **not** establish:
- that the source's statement is objectively true;
- that a source assertion's quote is semantically important;
- that an inference is reasonable or entailed by its source claims;
- calibrated confidence;
- real audiovisual perception or multimodal evidence grounding.

No real model API is connected. The pipeline is provider-neutral and tested with synthetic providers only.

## 6. Issues found during testing

The first grounded-memory test run found a fixture-construction error: a deliberately nonexistent quote was passed to a helper that attempted to locate it in the source text before submitting the proposal. The test was corrected to supply an explicit locator so that the CSD evaluator—not the test setup—could reject the mismatched quote.

A subsequent review identified that the text-only v2 path did not explicitly enforce the observation's declared modality. The evaluator now rejects non-text evidence, and the provider pipeline refuses to invoke a provider for non-text observations.

After these corrections, all five suites and compile checks passed in the hosted workflow.

## 7. What this result does not prove

This report does **not** prove:
- execution on the user's Windows 11 / Python 3.12.14 environment;
- Windows process-lock or multi-process behavior;
- sudden power-loss durability;
- production security isolation against hostile code in the same Python process;
- semantic entailment or objective truth;
- real model-provider quality;
- image/video/audio locator correctness;
- memory consolidation, forgetting, diary motivation, personality evolution, or autonomous life behavior;
- integration with DSH, SurfCore, Bilibili, QQ, or ASM.

## 8. Next validation and implementation gates

1. Validate the full test set on the user's Windows/Python environment.
2. Add semantic review as a separate proposal-analysis input; CSD remains the sole authority that accepts state.
3. Add source-specific transcript and frame locators only after their artifact and coverage contracts exist.
4. Connect a real model provider in shadow/pending-only mode before granting any acceptance pathway.
5. Keep model output as untrusted candidate data; do not treat quote presence alone as proof that an inference is true.
