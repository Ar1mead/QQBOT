# Minimum Cognitive Loop — API Mapping and Acceptance Matrix

> Status: implementation checkpoint and test plan, not a frozen CSD specification.
> Updated: 2026-11-19 (UTC+08:00)
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

1. There is no real cloud-model provider implementation.
2. The Life Engine snapshot is a motivation/goal snapshot, not a complete autobiographical context. It has no episode text or retrieved-memory context.
3. The grounded-memory provider receives one observation and state version; it does not yet receive prior accepted memories for cross-session synthesis.
4. CSD's grounded evaluator validates source location and structure, not broad semantic entailment, truth, personal significance, or psychological interpretation.
5. The current goal sink can immediately evaluate a valid candidate-goal proposal. Until a semantic review gate exists, model-generated goal creation must remain in a restricted/shadow path or be limited to candidate state with explicit evidence and no activity execution.
6. There is no production user-facing runtime wiring, credential configuration, or end-to-end cloud API test. No provider credentials should be committed to the repository.

## 4. Smallest safe provider integration seam

Use the existing provider protocols rather than introducing a new agent framework:

- For evidence-grounded episode interpretation, implement a provider for `GroundedMemoryProposalProvider`.
- For bounded goal/activity deliberation, implement a provider for the existing `Deliberator` protocol.
- Keep model transport separate from provider-specific domain mapping. Prefer a configurable OpenAI-compatible Chat Completions transport so the model vendor and endpoint can be changed without changing CSD or Life Engine.
- The provider receives only a bounded, explicitly serialized snapshot/observation. Do not give it a database connection, CSD store object, filesystem access, browser, tool executor, or ASM handle.
- Parse a strict JSON response into existing typed dataclasses. Reject unknown fields, unknown IDs, unsupported dispositions, malformed evidence references, and invalid state versions before the existing validators run.
- A timeout, HTTP error, malformed response, or empty proposal must not mutate CSD.
- Keep credentials in environment/runtime secret configuration. Never store API keys in source, tests, documentation examples, or event payloads.
- Start with deterministic fake-transport tests. A real provider smoke test requires a separately configured credential and must be reported separately from unit tests.

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

## 7. Implementation order and gates

1. Add provider parser/transport unit tests using a fake HTTP transport; no network or credential required.
2. Add a configurable cloud provider behind the existing grounded-memory provider protocol.
3. Add the end-to-end fake-provider test from observation through CSD acceptance and Recovery.
4. Add bounded prior-memory context to a versioned provider contract; do not silently widen the existing v1 provider input.
5. Run focused tests and full CI when GitHub runners are available. The current Actions failure is before runner allocation and is not a test result.
6. Perform a real API smoke test only after runtime credentials are configured outside the repository.
7. Add the Life Engine cloud deliberator as a separate slice; preserve no-op and the ASM boundary.

## 8. Explicit non-claims

This plan does not claim that a model has subjective experience, that an accepted source assertion is objectively true, that a deterministic CSD check proves semantic entailment, or that the system already operates autonomously. It defines a small, auditable route from real observation to model proposal to CSD-owned durable memory.
