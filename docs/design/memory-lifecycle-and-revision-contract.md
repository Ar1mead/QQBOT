# Memory Lifecycle and Revision Contract — Design Proposal

> Status: **architecture proposal; not a frozen CSD specification**  
> Scope: the lifecycle of an accepted memory after initial acceptance.  
> This document does not change the current event schema or prototype behavior.

## 1. Why a lifecycle contract is needed

The current cognitive slice can create, accept, retrieve, and recover memory records. It does not yet define what happens when a memory later becomes inaccurate, outdated, less accessible, consolidated with other memories, or subject to a request to forget it.

Without an explicit lifecycle, later modules may overload one status field to mean several different things. That would make memory history ambiguous and could cause a correction to erase the fact that the individual once held a different understanding.

The lifecycle must preserve continuity without treating every old interpretation as permanently true or permanently retrievable.

## 2. Keep separate dimensions separate

A memory should not have one overloaded status. At minimum, distinguish these dimensions:

| Dimension | Question | Illustrative values |
|---|---|---|
| Epistemic standing | What kind of claim is this and how is it supported? | source assertion, inference, self-experience, uncertain |
| Validity | Is this currently believed to be accurate? | current, challenged, superseded, retracted |
| Accessibility | How readily may ordinary retrieval return it? | active, low-salience, archived, inaccessible |
| Lifecycle relation | How does it relate to other memories? | revises, supersedes, consolidates, derived-from |
| Privacy/retention | May the content still be retained? | permitted, restricted, pending-erasure, erased |

These dimensions must not be collapsed. For example, a memory may be factually superseded but still historically relevant; an archived memory may remain valid; an uncertain inference may remain accessible as an uncertainty.

## 3. Lifecycle operations

### 3.1 Correction and revision

A correction creates a new immutable event and a new memory version or successor. It must reference the exact memory/claim being corrected and state the reason and evidence.

- Do not overwrite the prior accepted memory payload.
- Preserve the old claim as historical context, but mark its current validity as challenged or superseded through a new authoritative transition.
- A correction may narrow a claim rather than replace the whole memory.
- The new version must preserve its own evidence and epistemic type.
- Conflicting corrections remain visible as unresolved conflict; do not silently choose the newest statement solely because it is newer.

### 3.2 Supersession

Supersession means a newer accepted state replaces an older one for current use. It is not equivalent to deletion.

- The successor explicitly references the predecessor.
- Ordinary current-state retrieval prefers the successor.
- Historical retrieval may return both, with the relation made explicit.
- Supersession does not itself prove the predecessor was false; it may represent changed circumstances or a more precise understanding.

### 3.3 Consolidation

Consolidation creates a derived memory from multiple source memories.

- Every input memory and claim must be referenced.
- The consolidated result must distinguish direct source claims from synthesis/inference.
- Consolidation must not erase source records or their provenance.
- If the synthesis cannot be grounded, it remains a candidate and is not accepted as a fact.
- The first implementation should be deterministic about lineage and avoid automatic semantic compression.

### 3.4 Accessibility decay and archival

Retrieval salience may decrease over time or because a memory is rarely relevant. This is an accessibility change, not a claim that the memory is false or should be erased.

- Decay must not mutate the original event history.
- Importance, emotional salience, recency, and retrieval frequency are separate signals; no single signal should silently define truth.
- A low-accessibility or archived memory can still be retrieved by explicit historical query, subject to privacy policy.
- A memory must not become inaccessible solely because a timer elapsed unless an explicit retention rule authorizes that behavior.

### 3.5 Forgetting

The system's cognitive forgetting and privacy erasure are different operations.

**Cognitive forgetting** changes ordinary retrieval accessibility or salience. It may leave a minimal historical record that the memory existed, subject to privacy rules.

**Privacy erasure** removes or renders unrecoverable the protected content when a valid deletion/retention requirement applies. It cannot be implemented merely by hiding a record from normal retrieval.

Because the current event log is append-only and stores payload content, it cannot by itself satisfy strong content-erasure requirements. Before personal data is stored, the production design must decide among:
- separately encrypted content with per-record or per-subject keys and cryptographic erasure;
- an erasable content store referenced by immutable event metadata;
- another design with demonstrable deletion and backup-expiry guarantees.

No option is selected here. Do not claim that deleting a projection, tombstoning a row, or removing a retrieval result constitutes secure erasure. Backups, replicas, logs, caches, and derived memories must be included in any erasure design.

## 4. Authority and event boundaries

- Models and memory modules may propose revisions, consolidation, salience changes, or forgetting.
- Only the CSD-authoritative path may accept durable lifecycle transitions.
- A proposal must identify the target memory/claim versions, evidence, operation, origin, and state version.
- A lifecycle decision and its rebuildable projections must be committed atomically.
- Recovery replays lifecycle events as data and must not call models, re-evaluate proposals, or perform external actions.
- A lifecycle event must be idempotent and conflict if the same immutable identity is reused with changed content.
- External deletion from a platform is an ASM-governed side effect; recording a memory correction must not itself trigger a platform action.

This proposal does not amend the CSD v0.1 working contract or ASM clauses.

## 5. Retrieval behavior

Normal retrieval should be able to request a purpose and view:

- current view: current, non-superseded memories;
- historical view: prior versions and their relations;
- uncertain view: inferences and unresolved conflicts with epistemic labels;
- source view: original observations/quotes and provenance, subject to access controls;
- archived view: low-accessibility records when explicitly requested.

Retrieval must remain read-only. It must not update salience, create memories, or change lifecycle state merely because a memory was accessed. If retrieval frequency later becomes a salience signal, that must be a separate explicit event and policy.

## 6. Diary and private writing

Diary entries are not ordinary autobiographical memory candidates by default.

- A self-initiated diary entry is an authored artifact and must preserve its own text and creation context.
- The individual may choose not to save a draft.
- A diary entry may later inspire a memory proposal, but the entry and the derived memory remain separate records.
- The system must not silently extract every private diary statement into general memory.
- Privacy scope, access rules, retention, and deletion for diary content must be defined before diary storage is connected to a real model or platform.
- Diary writing is not a scheduled lifecycle operation and has no required frequency.

## 7. Proposed lifecycle event families

Names are illustrative and not frozen:

- `memory.revision_proposed.v1`
- `memory.revision_decided.v1`
- `memory.supersession_decided.v1`
- `memory.consolidation_proposed.v1`
- `memory.consolidation_decided.v1`
- `memory.accessibility_changed.v1`
- `memory.forgetting_decided.v1`
- `memory.erasure_requested.v1`
- `memory.erasure_completed.v1`

A single event family may be preferred after the state machine and schema are reviewed. The names above are not instructions to implement separate tables immediately.

## 8. Minimum test gates before implementation

1. A revision never overwrites the original immutable memory payload.
2. A revision references the exact predecessor version and evidence.
3. A stale revision proposal is deferred or rejected according to an explicit policy.
4. Conflicting revisions remain distinguishable and do not silently last-write-win.
5. Supersession affects current retrieval but preserves historical retrieval.
6. Consolidation preserves all input lineage and epistemic types.
7. Accessibility decay does not change epistemic validity.
8. Retrieval remains read-only.
9. Recovery reconstructs the same lifecycle graph without invoking a model.
10. Duplicate lifecycle events are idempotent; changed-content identity reuse conflicts.
11. Diary artifacts do not automatically become general memories.
12. Cognitive forgetting is not misreported as privacy erasure.
13. Erasure tests cover payloads, backups, replicas, logs, caches, and derived records before strong deletion is claimed.

## 9. Open decisions

The following must be decided before implementation:
- whether memory identity is stable across revisions or each revision gets a new memory ID;
- claim-level versus whole-memory revision granularity;
- how unresolved conflicting memories affect current retrieval;
- whether consolidation is automatic, self-initiated, or both;
- whether salience decay is time-based, context-based, or a combination;
- how privacy scope is inherited by derived memories;
- what a user deletion request means for immutable event metadata;
- cryptographic-erasure architecture and backup expiry;
- how diary entries are isolated from general memory;
- whether any lifecycle policy is normative CSD or a replaceable memory-domain policy.

## 10. Current implementation boundary

The current prototype does **not** implement revision, supersession, consolidation, accessibility decay, cognitive forgetting, privacy erasure, diary storage, or diary motivation. Its accepted-memory retrieval is deterministic substring/filter retrieval only.

This document is a design checkpoint to prevent those capabilities from being improvised as one overloaded status field. It is not evidence that a complete long-term memory system exists.
