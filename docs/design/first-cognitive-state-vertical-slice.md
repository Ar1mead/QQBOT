# First Cognitive-State Vertical Slice

> Status: **implementation design proposal; not a frozen CSD specification**  
> Scope: one synthetic observation becomes a candidate autobiographical memory, is evaluated under CSD authority, is committed as accepted state, can be retrieved, and survives restart/recovery.  
> Related: [CSD v0.1 reconciliation](../reports/csd-v0.1-architecture-reconciliation.md), [CSD authority boundary](csd-state-authority-boundary.md), [Persistence reference spike](../../core/csd/README.md).

## 1. Why this slice

The existing SQLite spike tests durable event storage and recovery. It does not test whether an experience can become a durable cognitive state item without allowing a model, runtime, or adapter to write that state directly.

This slice is deliberately narrow. It tests the boundary between:
- a source observation;
- a candidate memory proposal;
- CSD's evaluation decision;
- an accepted memory projection;
- retrieval and recovery.

It does **not** test whether a model's interpretation is psychologically or semantically correct. It does not implement general memory, personality, emotion, goals, or autonomous behavior.

## 2. Scope and non-goals

### In scope

- Submit a synthetic read-only observation using the existing Event Submit contract.
- Submit a candidate-memory proposal as a second typed event through the same Event Submit contract.
- Ensure proposal submission alone does not create accepted memory.
- Let CSD's own evaluation path decide whether the proposal is eligible for acceptance.
- Persist the decision and accepted state transition atomically.
- Retrieve the accepted memory with evidence/provenance references.
- Close and reopen the database, recover from durable records, and retrieve the same memory.
- Ensure recovery never reruns semantic evaluation or external actions.

### Explicitly out of scope

- LLM-based interpretation or semantic memory quality.
- Real Bilibili, QQ, desktop, network, or filesystem integrations.
- Real personal or sensitive content.
- Memory consolidation, forgetting, decay, contradiction resolution, or relationship modeling.
- User-facing memory editing or deletion policy.
- Personality, affect, drives, goal generation, diary motivation, or life-engine scheduling.
- Production authentication, encryption, multi-user isolation, or final retention policy.
- Any external side effect.

All fixtures must be synthetic and contain no real personal data.

## 3. Event flow

    Synthetic observation fixture
            |
            v
    Event Submit: experience.observation_recorded.v1
            |
            v
    Persisted observation event (not yet a memory)
            |
            v
    Candidate memory producer (test fixture only)
            |
            v
    Event Submit: cognition.memory_candidate_proposed.v1
            |
            v
    Persisted candidate proposal (not yet accepted memory)
            |
            v
    CSD-owned evaluation path
            |
            +---- reject / defer / needs-evidence
            |
            +---- accept
                     |
                     v
           CSD decision + accepted transition
           committed atomically
                     |
                     v
           Accepted memory projection
                     |
              Memory Retrieval
                     |
               close / reopen
                     |
                  Recovery
                     |
              Memory Retrieval

The candidate producer is a test fixture, not an autonomous cognitive service. The evaluator is a deterministic provenance policy, not a semantic judge. It does not determine whether candidate wording faithfully summarizes the source, whether the event is objectively true, or whether the content matters to a real individual.

## 4. Proposed event shapes

The event envelope continues to follow the CSD v0.1 working contract:

- event_id
- occurred_at
- received_at
- correlation_id
- event_type
- source
- payload_ref

The current prototype accepts a payload mapping and derives payload_ref from its canonical content; it generates received_at internally. This proposal does not change those envelope semantics.

The names and payloads below are proposed test schemas only. They are not frozen event names.

### 4.1 Observation event

Proposed event type: experience.observation_recorded.v1

Synthetic payload:

    {
      "observation_id": "obs-synthetic-001",
      "observation_kind": "text_fixture",
      "content": "A fictional blue paper boat floated beside a stone bridge.",
      "source_ref": "fixture://vertical-slice/observation-001",
      "observed_at": "2026-11-14T10:00:00+00:00",
      "coverage": {
        "modality": "text",
        "complete_for_fixture": true
      }
    }

The event records that the fixture supplied this content. It does not assert that the described scene existed in the real world.

### 4.2 Candidate memory proposal event

Proposed event type: cognition.memory_candidate_proposed.v1

Synthetic payload:

    {
      "proposal_id": "mem-proposal-synthetic-001",
      "memory_kind": "episodic_candidate",
      "candidate_content": "I encountered a fictional description of a blue paper boat near a stone bridge.",
      "evidence_event_ids": ["evt-observation-synthetic-001"],
      "origin": {
        "component": "test.memory_candidate_fixture",
        "version": "0.1"
      },
      "uncertainty": {
        "label": "fixture_only",
        "confidence": null
      },
      "based_on": {
        "state_version": 0
      },
      "operation": "create"
    }

The synthetic fixture text is authored to stay within what the observation record says. The current deterministic evaluator does not check this semantic relationship; it only checks evidence existence/type and state-version freshness. The record must not be presented as proof that the system physically saw, visited, or experienced a real place.

The proposal event is a persisted candidate, not an accepted memory. Its existence must not change the accepted-memory retrieval result.

### 4.3 CSD decision event

Proposed event type: cognition.memory_candidate_decided.v1

The decision event is generated only by CSD's internal evaluation path, not by the runtime, model, candidate producer, or platform adapter.

For the acceptance fixture, its payload should include:
- proposal_id;
- outcome (accepted, rejected, deferred, or needs_more_evidence);
- decision_policy and version;
- references to the proposal and supporting evidence event IDs;
- a concise reason code/summary;
- transition_id when accepted;
- the relevant state sequence/version used for evaluation.

This event is the durable record of CSD's decision. The accepted-memory projection changes only as a result of a valid accepted decision, never merely because a proposal event was submitted.

The prototype uses a CSD-generated decision event appended in the same SQLite transaction as its accepted-memory projection update. A failed transaction leaves neither durable decision nor accepted memory. This is a prototype implementation choice, not a frozen CSD normative clause.

## 5. Evaluation boundary

For this first slice, use a deterministic test policy with narrow mechanical checks:

1. The proposal schema and identity are valid.
2. Every referenced evidence event exists and is of an allowed observation type.
3. The evaluator validates evidence existence and type only; it does not semantically verify whether candidate wording overclaims the source.
4. The proposal's referenced accepted-state version is not stale for the fields it intends to change.
5. The same proposal has not already received a conflicting terminal decision.

This policy tests provenance, authority, idempotency, and transaction mechanics. It does not evaluate emotional significance, personal importance, truth beyond the source record, or whether a real individual would remember the experience.

CSD owns the decision. The test policy must run under CSD's evaluation boundary. A runtime-supplied accepted flag, model confidence score, or adapter-supplied decision is not authoritative.

A later semantic evaluator may provide bounded analysis, but CSD must still decide whether the proposed state transition is accepted. That later capability is not part of this slice.

## 6. Minimal accepted-memory projection

The first accepted-memory record should be intentionally small:

- stable memory_id;
- memory_kind;
- content;
- evidence_event_ids;
- proposal_id;
- transition_id;
- created_at / decision time;
- status (accepted for this slice);
- provenance to the decision policy/version.

Do not add importance, emotional intensity, decay, embedding vectors, personality effects, or inferred preference fields yet. Those require separate semantics and evidence.

Memory Retrieval should return accepted records only, with their evidence references and decision provenance. A candidate proposal may be retrievable through a diagnostic/proposal read, but it must not appear as an accepted memory.

### Identity distinction

Event identity and proposal identity are not interchangeable:
- the same event_id with identical immutable content is an idempotent duplicate;
- the same event_id with changed immutable content is a conflict;
- a different event_id with the same proposal_id and identical immutable proposal content remains a distinct event but must resolve to the same proposal aggregate and must not create a second evaluation/accepted memory;
- a different event_id with the same proposal_id but changed immutable proposal content is a proposal-identity conflict;
- a proposal can have at most one terminal decision for this slice;
- transition_id is distinct from both event_id and proposal_id.

See the [storage and authority decision analysis](vertical-slice-storage-decision-analysis.md) for the recommended representation and reserved internal decision-event boundary.

## 7. Persistence and recovery requirements

The following must hold:

- Observation, candidate proposal, decision, and accepted-memory transition have durable event identities.
- Duplicate submissions with the same event ID and immutable content are idempotent.
- Reusing an event ID with different immutable content is a conflict.
- Proposal identity is distinct from event identity and transition identity.
- The accepted-memory state update and decision record are atomic.
- Retrieval does not mutate the accepted memory or its meaning.
- Recovery rebuilds the same accepted-memory projection from durable records.
- Recovery does not call a model, rerun proposal evaluation, or execute an adapter/tool action.
- A corrupt or contradictory decision/event history causes a safe stop rather than silently inventing or discarding accepted memories.

The current generic event-count reducer cannot satisfy these semantics by itself. The prototype therefore preserves it unchanged and adds a separate typed CognitiveMemoryStore with a separate SQLite schema. This is a temporary implementation boundary, not a final two-database architecture.

## 8. Proposed API mapping

Keep the CSD v0.1 conceptual API classes:

| Existing API class | Use in this slice |
|---|---|
| Event Submit | Submit observation and candidate proposal events; internal CSD path records decision |
| State Snapshot | Inspect current accepted state/version for test assertions |
| Memory Retrieval | Retrieve accepted memory and provenance |
| Goal Retrieval | Not exercised |
| Recovery | Rebuild accepted memory projection and verify retrieval after reopen |

Do not introduce a second public write API. Internal CSD evaluation is not a new runtime write authority.

The current reference implementation has only a basic Event Submit, generic State Snapshot, and Recovery shape. Memory Retrieval and the typed CSD evaluation path are new work and must be implemented explicitly before this slice can be called complete.

## 9. Exit criteria

The slice is complete only when all of the following are demonstrated by automated tests:

- An observation event is accepted but is not itself returned as a memory.
- A candidate proposal is accepted into the event history but is not returned as an accepted memory.
- CSD's evaluation path, not the caller, chooses the decision.
- A valid accepted decision creates exactly one accepted memory with provenance.
- A rejected/deferred proposal creates no accepted memory.
- Duplicate event/proposal submissions do not duplicate state.
- Same identity with changed immutable content is rejected as a conflict.
- Invalid/missing evidence is rejected or deferred without partial state mutation.
- A stale proposal is not blindly applied.
- A crash at the decision/transition boundary cannot create partial accepted state.
- Restart/recovery yields the same accepted-memory result.
- Recovery does not rerun the evaluator or call external tools.
- Memory Retrieval returns evidence and decision provenance.
- No runtime, model, or adapter path can write accepted-memory state directly.

Passing this slice demonstrates a small authoritative cognitive-state transition path. It does not demonstrate general intelligence, subjective experience, robust semantic memory, or autonomous life.

## 10. Decisions still required before implementation

- How internal CSD authority will be enforced before untrusted code can share the process; the current Python boundary only prevents accidental use through the public API.
- Whether the prototype's separate SQLite database should later be merged with the generic persistence store, and how to migrate without losing provenance.
- The minimal read shape and pagination/consistency behavior for Memory Retrieval.
- Whether a future proposal may be reopened after a needs_more_evidence decision; the current slice treats that outcome as terminal and requires a new proposal ID when new evidence is available.
- Whether candidate proposal records are retained indefinitely or governed by a later retention policy.
- How schema migrations preserve historical event interpretation.
- How this slice maps to the exact CSD v0.1 source text once verbatim clauses are restored.

Do not resolve these questions by convenience alone. Record any selected implementation choice separately and keep it replaceable where practical.
