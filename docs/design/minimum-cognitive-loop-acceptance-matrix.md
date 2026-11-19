# Minimum Cognitive Loop — API Mapping and Acceptance Matrix

> Status: implementation checkpoint and test plan, not a frozen CSD specification.
> Updated: 2026-11-20 (UTC+08:00)
> Scope: identify the smallest safe, model-backed cognitive slice using the current CSD and Life Engine APIs.

## 1. Purpose

The three-layer architecture is now documented. This file turns it into an implementation plan grounded in the current repository. It deliberately avoids adding another persistence layer or expanding platform/worker infrastructure.

The first model-backed milestone must prove that an actual cloud model can interpret bounded context and return a proposal while CSD remains the only authority for durable state. It must not claim human-like consciousness or semantic correctness merely because an LLM generated fluent text.

## 2. Existing API map

| Cognitive-loop stage | Existing implementation | Current capability / limit |
|---|---|---|
| Experience input | `CognitiveMemoryStore.submit_event(CognitiveEvent)`; observation v1/v2 | Durable, timestamped, provenance-bearing observations; v2 carries richer modality and coverage metadata. |
| Accepted-memory retrieval | `get_memories()`, `get_memory()` in `core/csd/cognitive.py` | Returns CSD-accepted records with proposal/decision/evidence lineage; not semantic vector retrieval. |
| Grounded model-proposal seam | `GroundedMemoryProposalProvider` and `GroundedMemoryProposalPipeline` in `core/csd/grounded_proposals.py` | Provider proposes source assertions with exact Unicode text offsets and optional inferences; pipeline binds observation ID, provider identity, and CSD state version. |
| CSD adjudication | `evaluate_grounded_proposal()` and related CSD-owned evaluation paths | Checks schema, exact source spans, claim references, chronology and state integrity; does not prove general semantic entailment or source truth. |
| Motivation / goal state | `core/csd/motivation.py`, `core/csd/goals.py` | Durable, versioned motivation signals and candidate/active goal transitions with evidence lineage. |
| Deliberation input | `CognitiveStoreLifeSnapshotReader` | Supplies an integrity-checked snapshot of motivation signals and goals. It currently supplies no accepted episode text and no activity options. |
| Deliberation contract | `LifeSnapshot`, `DeliberationProposal`, `ChoiceProposal` | Provider-neutral typed proposal. Includes `no_op`, wait, request-information, decline and lifecycle choices. |
| Deliberation orchestration | `LifeEngine.consider()` | Reads snapshot, calls injected `Deliberator`, validates exact state version and evidence references, then sends a proposal to the sink. No timers or external tools are invoked. |
| CSD proposal sink | `CognitiveStoreLifeProposalSink` | Persists/evaluates supported goal lifecycle proposals. It never executes activities. Unsupported activity choices return not-executed. |
| External action | ASM | Remains separate. No model proposal may dispatch an external action. |

## 3. Critical gaps

1. OpenAI-compatible grounded-memory and semantic-review provider implementations now exist, but neither has been smoke-tested against a live API and neither is wired into a production user-facing runtime.
2. The Life Engine snapshot is a motivation/goal snapshot, not a complete autobiographical context. It has no episode text or retrieved-memory context.
3. The grounded-memory provider receives one observation and state version; it does not yet receive prior accepted memories for cross-session synthesis.
4. CSD's grounded evaluator validates source location and structure, not broad semantic entailment, truth, personal significance, or psychological interpretation.
5. The current goal sink can immediately evaluate a valid candidate-goal proposal. Until a semantic review gate exists, model-generated goal creation must remain in a restricted/shadow path or be limited to candidate state with explicit evidence and no activity execution.
6. There is no production user-facing runtime wiring, credential configuration, or end-to-end cloud API test. No provider credentials should be committed to the repository.

## 4. Provider integration boundary

The first cloud-backed provider seams now exist; keep them behind the existing protocols rather than introducing another agent framework:

- `OpenAICompatibleGroundedMemoryProvider` implements `GroundedMemoryProposalProvider` for source-grounded episode extraction.
- `OpenAICompatibleSemanticReviewProvider` implements `SemanticReviewProvider` for reviewing an inference against direct source claims in the same proposal.
- Both use configurable HTTPS Chat Completions endpoints and environment/runtime credentials. Neither receives a CSD store, database connection, filesystem, browser, tool executor, or ASM handle.
- The grounded pipeline adds the versioned, bounded accepted-memory context. Historical text is untrusted continuity context; it is not proof for a new source assertion.
- Both providers parse strict JSON into typed proposals/opinions. Unknown fields, duplicate keys, unknown claim IDs, malformed output, oversized content and transport failures fail closed.
- The semantic reviewer returns an attributed opinion, not truth. The existing review pipeline binds it to immutable proposal/claim digests; CSD alone accepts, rejects, defers or requests more evidence.
- The combined fake-transport integration test covers observation → grounded provider → pending proposal → semantic review → CSD acceptance. This is not a live API test.
- Credentials remain outside source, tests, docs and event payloads. A live API smoke test requires separately configured runtime secrets and must be reported separately from fake-transport tests.

## 5. First vertical slice

### Slice A — cloud model creates a grounded episode proposal

1. Submit a synthetic or user-authorized observation through the existing CSD event API.
2. Read the exact observation and current CSD state version.
3. Call a real cloud model through a provider-only HTTP transport with the observation text and strict output instructions.
4. Require the model to return source assertions with exact quote text and Unicode code-point offsets; optional inferences must cite only those source-assertion claim IDs and include uncertainty.
5. Let the existing pipeline bind evidence ID, provider identity/version, timestamp, and state version.
6. CSD validates and accepts/rejects the pending proposal through its own evaluation path.
7. Retrieve the accepted memory and verify its evidence and decision lineage.
8. Close/reopen the store, run Recovery, and verify the same accepted record is returned.
9. Verify that a later provider invocation can be supplied a bounded read-only set of accepted memories before attempting cross-session preference formation. This context input is a required follow-up seam, not yet implemented by the current provider contract.

### Slice B — Life Engine deliberation

After Slice A's provider boundary is proven, implement the cloud `Deliberator` over the current `LifeSnapshot`:

1. Serialize only current signals, goals, eligible options, and state version.
2. Require one strict `DeliberationProposal`, including an explicit `no_op` when nothing is justified.
3. Reuse `validate_life_proposal()` and the existing CSD sink.
4. Initially do not dispatch activities. Goal candidates remain candidates; activation and any side effects retain their separate CSD/ASM gates.
5. Add semantic review before treating model-generated personal preference or self-model interpretations as durable identity updates.

Slice B is not required to prove the first model-backed autobiographical memory loop; it follows once the simpler provider boundary is working.

## 6. Acceptance matrix

| ID | Scenario | Expected result | Authority / test boundary |
|---|---|---|---|
| LOOP-01 | Persist a new observation with source and time | Event exists; it is not automatically an accepted memory | CSD event store |
| LOOP-02 | Model returns a source assertion with exact quote and offsets | Typed pending proposal is created; pipeline binds evidence and state version | Provider + grounded pipeline |
| LOOP-03 | Model invents an offset, quote, evidence ID, or unknown claim reference | Proposal rejected; no accepted memory | Pipeline/CSD validation |
| LOOP-04 | Model returns malformed JSON, extra authority fields, invalid confidence, or unsupported output type | Fail closed; no CSD mutation | Provider parser |
| LOOP-05 | Provider times out or returns HTTP error | No proposal or state transition is created | Transport/pipeline |
| LOOP-06 | CSD accepts a valid grounded proposal | Accepted memory has source assertion, uncertainty, proposal, decision and event lineage | CSD only |
| LOOP-07 | CSD rejects/defer/needs-more-evidence | No accepted memory is returned; outcome remains auditable | CSD only |
| LOOP-08 | Proposal was based on a stale state version | No blind application; defer/reject under CSD chronology rules | CSD only |
| LOOP-09 | Restart and Recovery after acceptance | Same accepted memory and provenance are retrieved | CSD Recovery |
| LOOP-10 | Provider is swapped while using the same CSD database | Durable state and history remain unchanged | Provider-neutrality test |
| LOOP-11 | Life Engine deliberator returns no-op | Valid no-state-transition result; no invented activity | Life Engine |
| LOOP-12 | Deliberator cites unknown signal/goal/activity/evidence or stale state | Rejected before sink | Life Engine validator |
| LOOP-13 | Deliberator requests an external activity | Not executed by Life Engine/CSD sink; requires ASM authorization | ASM boundary |
| LOOP-14 | One ambiguous event suggests a personal preference | Keep it as tentative interpretation; do not silently rewrite identity | Future semantic-review/state contract |
| LOOP-15 | Repeated evidence and explicit correction conflict | Preserve both evidence streams and revision lineage; no silent overwrite | Future preference/self-model reducer |
| LOOP-16 | A later observation is processed with accepted history | Provider receives a bounded, versioned, untrusted context containing only accepted memories; pending/rejected proposals are excluded | Prior-memory selector + grounded pipeline |
| LOOP-17 | Cloud grounded provider emits an inference | Separate cloud semantic reviewer returns an attributed outcome; CSD remains pending until review and its own evaluation; supported is not treated as objective truth | Cloud providers + semantic-review pipeline + CSD |
| LOOP-18 | Model infers a stable preference from several historical episodes | Not yet supported; no cross-episode evidence reference or preference revision contract may be bypassed | Future cross-memory synthesis contract |
| LOOP-19 | Pipeline resolves a historical source-assertion claim | Resolver verifies accepted memory/proposal/decision lineage, matching grounded proposal event, integrity-valid earlier observation source events, claim digest and state version inside one SQLite read snapshot (or reuses the active CSD transaction); duplicate pairs deduplicate; append/decision-time revalidation is still required | Accepted-claim resolver groundwork (not full cross-episode proposal support) |
| LOOP-20 | Model proposes a cross-episode interpretation | Strict typed candidate uses only opaque accepted-claim keys, preserves support/counter-evidence and scope/uncertainty, distinguishes user preference from AI interest, counts distinct source events, and remains shadow-only/non-persistent | Cross-episode candidate builder; CSD event persistence and append/decision gates remain future work |

## 7. Implementation order and gates

1. Keep deterministic fake-transport tests for both grounded extraction and semantic review; no network or credential is required for these tests.
2. Verify the combined cloud-provider → pending proposal → semantic review → CSD acceptance integration test.
3. Run focused tests and full CI when GitHub runners are available; runner-allocation failures are not test results.
4. Configure credentials only in a future runtime secret store, then perform a separately reported live API smoke test.
5. Define a versioned cross-episode evidence-reference contract and adversarial tests before allowing multiple historical memories to support a preference candidate.
6. Add a CSD-owned preference/self-model proposal, review, revision and retirement contract; never allow direct model writes to identity state.
7. Add the Life Engine cloud deliberator as a separate slice; preserve no-op and the ASM boundary.

## 8. Explicit non-claims

This plan does not claim that a model has subjective experience, that an accepted source assertion is objectively true, that a deterministic CSD check proves semantic entailment, or that the system already operates autonomously. It defines a small, auditable route from real observation to model proposal to CSD-owned durable memory.
