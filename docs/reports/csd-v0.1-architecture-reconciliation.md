# CSD v0.1 and Individual Architecture Reconciliation

> Status: **reconciliation note; working baseline, not a frozen specification**  
> Purpose: prevent the new runtime architecture proposal from silently changing previously discussed CSD v0.1 boundaries.  
> Related: [Specification status](../specifications/status.md), [Persistent Individual Runtime Model](../architecture/individual-runtime-model.md), [CSD state authority boundary](csd-state-authority-boundary.md), [CSD persistence proposal](csd-minimal-persistence-proposal.md).

## 1. Status and source discipline

The CSD v0.1 points below are the semantic working contract discussed in prior design work. This note is not a recovery of verbatim normative source text and must not be treated as a frozen specification.

The purpose here is architectural reconciliation:
- preserve previously agreed CSD authority and API boundaries;
- identify where the new architecture adds implementation detail;
- mark proposed additions as proposals;
- keep unresolved questions open rather than silently resolving them.

## 2. Existing CSD v0.1 working baseline

The current working baseline is:

1. CSD is the authoritative source of long-term cognitive state.
2. CSD alone evaluates and commits authoritative long-term state transitions.
3. Runtime components submit events and read state; they do not directly evaluate or mutate authoritative long-term state.
4. Event identity is idempotent. Deduplication and the corresponding business-state update are atomic.
5. Same event ID with same immutable content is a duplicate; same event ID with different immutable content is a conflict. Same content with a different event ID represents a different event.
6. External side effects are persisted and governed separately. Recovery/reconstruction does not replay side effects; uncertain outcomes are inspected rather than blindly retried.
7. The event envelope fields are:
   - event_id
   - occurred_at
   - received_at
   - correlation_id
   - event_type
   - source
   - payload_ref
8. The five conceptual API classes are Event Submit, State Snapshot, Memory Retrieval, Goal Retrieval, and Recovery.
9. Goal Retrieval is read-only from the runtime's perspective. If CSD determines that an active goal is no longer valid, the response may temporarily include pending_downgrade and a reason; the runtime must not advance that state. CSD itself performs the active-to-paused transition and appends the goal_downgraded event.
10. CSD may read an ASM business-action state summary, but it cannot trigger retry, confirmation, or abandonment.

These points remain subject to the exact status recorded in the specification register. They are not expanded here into new normative clauses.

## 3. Compatibility mapping

| Existing CSD v0.1 boundary | New architecture detail | Reconciliation |
|---|---|---|
| Event Submit | Evidence events and cognitive proposal records | Keep one authoritative submission path. A proposal may be represented as a typed event/payload submitted through Event Submit. |
| CSD alone evaluates durable state | Cognitive services produce interpretations and candidate updates | Services provide analysis/proposals only. CSD makes the final authoritative acceptance/rejection/defer decision. |
| State Snapshot | Distinct state families and provenance | Snapshot exposes current accepted state and version/offset; it must not flatten away the distinctions between memories, affect, goals, and diary. |
| Memory Retrieval | Memory lifecycle and evidence links | Retrieval returns accepted memory records with relevant provenance, uncertainty, and lifecycle metadata. |
| Goal Retrieval | Candidate goals, accepted goals, commitments, and goal lifecycle | Runtime reads only. CSD owns validity evaluation and any authoritative downgrade transition. |
| Recovery | Event/projection reconstruction | Rebuild local state only; no model calls, proposal execution, tool invocation, or external side effects. |
| ASM state summary read | Life engine and deliberation | A summary can inform deliberation; it cannot grant CSD authority over ASM action decisions. |

## 4. Proposed interpretation of proposal handling

The architecture needs a place to store candidate memories, preference hypotheses, self-belief revisions, affect estimates, relationship interpretations, and goal hypotheses. This does not require weakening CSD's authority.

Proposed flow:

1. An adapter or runtime reports an observation through Event Submit.
2. A cognitive service reads relevant state and evidence.
3. It may use a model to produce a typed candidate proposal outside a CSD write transaction.
4. The candidate is submitted through the existing Event Submit path as a versioned proposal event (or as a proposal payload referenced by such an event).
5. CSD validates and persists the candidate without treating it as accepted state.
6. CSD's own evaluation path decides whether to accept, reject, defer, or request more evidence.
7. If accepted, CSD commits the state transition and its provenance atomically.
8. The runtime and other services learn the result through read interfaces or returned event/result references.

A convenience wrapper such as submit_proposal may later be exposed, but it must be semantically equivalent to Event Submit. It must not create a second write authority.

A cognitive evaluator may be called by CSD to provide bounded analysis. Its output remains input evidence to CSD's decision, not the authoritative verdict. This distinction preserves the earlier rule that CSD alone evaluates long-term state.

## 5. What the persistence spike does and does not establish

The current SQLite reference spike implements a generic event log, content-addressed payload storage, idempotent event acceptance, a simple deterministic projection, snapshots, and recovery checks.

It is compatible with the persistence portion of the working baseline in principle, but it does not yet implement:
- the full CSD v0.1 API set;
- typed cognitive proposal events;
- authoritative semantic proposal evaluation;
- memory or goal retrieval semantics;
- goal validity and downgrade behavior;
- memory, personality, affect, relationship, or diary state;
- the ASM business-action read boundary;
- production schema evolution, privacy, encryption, and retention policies.

The spike's generic event-count projection is a test fixture, not a representation of the individual's cognitive state. Passing its tests does not prove the full CSD contract.

## 6. Boundaries that must not be changed accidentally

The following would be architectural regressions unless separately reviewed and explicitly approved:

- allowing DSH, SurfCore, a model, or a platform adapter to write authoritative long-term state directly;
- allowing a cognitive service's proposal to become accepted state merely because it was persisted;
- allowing a model confidence score to substitute for CSD's evaluation;
- introducing a second proposal-write API with semantics that bypass Event Submit;
- allowing runtime code to mutate goal state after reading pending_downgrade;
- allowing CSD goal evaluation to trigger an external action or ASM retry;
- replaying tools, model calls, or side effects during CSD recovery;
- collapsing observations, interpretations, memories, personality, affect, goals, commitments, and diary into one mutable prompt string.

## 7. Open questions retained

This reconciliation does not settle:

- exact event types and schema versions for proposal records;
- whether proposal payloads are stored in the existing event payload store or a separately versioned proposal table while retaining Event Submit semantics;
- how CSD performs semantic evaluation while retaining exclusive authority;
- whether state versions are global, per aggregate, or both;
- the exact consistency semantics of Goal Retrieval and pending_downgrade;
- detailed memory and goal lifecycle schemas;
- privacy, encryption, deletion, and retention behavior;
- how CSD reads ASM summaries without becoming an action authority.

These require separate decisions and, where appropriate, return to the original CSD source clauses.

## 8. Recommended next work

Before expanding the persistence code, define one narrow vertical slice that respects the existing CSD contract:

- submit a synthetic read-only observation event;
- submit a candidate memory proposal as an event through the same Event Submit boundary;
- have CSD evaluate the proposal and record a decision;
- commit an accepted memory projection only through CSD;
- retrieve the accepted memory with its evidence references;
- restart and recover without re-running the model or repeating any external action.

This should first be a design and test-contract exercise. Do not treat the existing generic event-count prototype as if it already implements this slice.
