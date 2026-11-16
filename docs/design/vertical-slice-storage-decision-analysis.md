# Vertical-Slice Storage and Authority Decision Analysis

> Status: **engineering recommendation for review; not a frozen CSD specification**  
> Scope: select a low-complexity persistence shape for the first cognitive-state vertical slice only.  
> Related: [First cognitive-state vertical slice](first-cognitive-state-vertical-slice.md), [CSD v0.1 reconciliation](../reports/csd-v0.1-architecture-reconciliation.md), [CSD state authority boundary](csd-state-authority-boundary.md).

## 1. Decision to make

The first slice needs to persist four related things:

1. source observation;
2. candidate memory proposal;
3. CSD's decision about that proposal;
4. accepted-memory state transition, if accepted.

The decision and accepted projection must not split across a crash. Recovery must replay durable decisions, not rerun semantic evaluation.

Two broad storage shapes were considered.

## 2. Option A — one append-only event stream with typed reducers

All four record types are represented as versioned events in the existing event log. The accepted-memory projection is derived only from a valid CSD decision event.

Advantages:
- preserves the existing Event Submit abstraction;
- one ordered event sequence and one recovery path;
- event provenance and state transitions are linked through IDs;
- decision event and projection update can commit in one SQLite transaction;
- recovery replays a deterministic reducer and never reevaluates a proposal;
- no second proposal/decision write API is required.

Costs and risks:
- the event reducer becomes domain-aware and needs strict validation by event type;
- CSD-generated decision events need an internal-only append path;
- reserved event types must not be forgeable through the public Event Submit surface;
- proposal identity uniqueness is separate from event identity idempotency;
- event schema evolution must preserve old reducer semantics or use explicit upcasters/versioned reducers.

## 3. Option B — event log plus proposal/decision tables

Observation events remain in the event log, while proposals and decisions are stored in dedicated tables and the memory projection is updated from those records.

Advantages:
- proposal lifecycle can have direct indexes and query operations;
- proposal-specific uniqueness and status constraints can be expressed with relational constraints;
- domain data is not forced into a single event payload table.

Costs and risks:
- introduces a second persistence shape and more cross-table invariants;
- recovery must reconcile event history, proposal rows, decision rows, and memory projection;
- transaction boundaries become more complicated;
- it is easier for an auxiliary table to become an untracked second source of truth;
- it risks drifting from the existing Event Submit contract unless all writes remain behind CSD.

## 4. Recommendation for the first slice

Use **Option A: one append-only event stream with typed reducers**, while keeping the recommendation limited to this small prototype.

Suggested event types:
- experience.observation_recorded.v1
- cognition.memory_candidate_proposed.v1
- cognition.memory_candidate_decided.v1

Suggested flow:

1. External adapters and cognitive fixtures submit observation/proposal events through the existing Event Submit method.
2. The public submission path rejects CSD-reserved decision event types.
3. A CSD-owned internal evaluation operation opens a write transaction.
4. It loads the pending proposal and referenced evidence from the same database.
5. It runs only deterministic local validation for this first slice; no LLM, network, adapter, shell, or filesystem action is called inside the transaction.
6. It appends a CSD-authored decision event and applies the accepted-memory projection from that event in the same transaction.
7. It commits once.
8. Recovery replays the decision event into the memory projection. It does not run the evaluation operation.

This design keeps proposal submission and proposal acceptance distinct. It also gives a clear crash boundary: either the decision event and its projection commit together, or neither does.

## 5. Identity rules

Three identities must remain distinct:

- event_id identifies one immutable event submission;
- proposal_id identifies one candidate cognitive proposal across its lifecycle;
- transition_id identifies one accepted state transition.

The following behavior is recommended:

| Situation | Required behavior |
|---|---|
| Same event_id, same immutable event content | Return duplicate; do not append or reduce twice |
| Same event_id, changed immutable content | Conflict; preserve original |
| Different event_id, same proposal_id, same immutable proposal content | Preserve the distinct event identity, but resolve to the same proposal aggregate; do not evaluate or accept the proposal twice |
| Different event_id, same proposal_id, changed immutable proposal content | Proposal identity conflict; preserve the first proposal and reject the conflicting proposal event from creating a second proposal |
| Same proposal evaluated repeatedly | Return the existing terminal decision or current pending status; do not create a second decision/transition |
| Same transition_id, same immutable transition | Idempotent |
| Same transition_id, changed immutable transition | Conflict |

The exact representation of duplicate proposal submissions may be a second event with a duplicate-of reference or a rejected event-submission result. The invariant is more important than the representation: one proposal identity cannot silently change meaning or produce multiple accepted memories.

## 6. Authority and trust limitations

The first implementation is expected to run as a modular local application. In that arrangement:
- public adapter/runtime code should receive only the Event Submit and read interfaces it needs;
- the CSD evaluator/internal append operation should not be exposed as a general adapter tool;
- reserved decision event types must be rejected by the public submission method;
- the CSD-owned operation alone creates accepted-memory transitions.

A Python underscore method or module convention is not a security boundary against hostile code executing in the same process. This first slice can test architectural/API separation and accidental misuse prevention, not strong isolation against malicious in-process code.

Before untrusted plugins or platform parsers are given access to the same runtime, enforce the boundary with a separate process or authenticated local IPC, least-privilege OS identity, and a narrowly scoped CSD service API. Do not claim that the first slice supplies that security hardening.

## 7. Recovery semantics

The reducer for the decision event must be deterministic and side-effect-free.

Recovery:
- validates event and payload integrity;
- replays observation and proposal events as history;
- applies accepted-memory changes only from valid CSD decision events;
- does not call the evaluator;
- does not infer a missing decision from a proposal;
- does not call models or platform adapters;
- stops safely if a decision references a missing proposal/evidence record or violates transition invariants.

A proposal left pending when the process stops remains pending after recovery. A later normal CSD evaluation cycle may consider it again. Recovery itself must not decide it.

## 8. Why this recommendation is deliberately narrow

A single event stream is not declared the final storage architecture for all future cognition. Memory consolidation, large media artifacts, vector indexes, private diary content, relationship graphs, and high-volume observation data may require separate stores or projections later.

Those stores must still have explicit ownership, provenance, transaction/reconciliation rules, and a clear relationship to the authoritative CSD event history. This first slice should avoid designing those future stores before their access patterns and privacy requirements are known.

## 9. Consequences for implementation

Before coding the vertical slice, update the reference implementation design to account for:
- typed event schemas and version validation;
- reserved CSD-authored event types;
- unique proposal identity and immutable proposal digest;
- CSD-owned deterministic evaluation;
- a decision event appended atomically with accepted-memory projection;
- deterministic recovery from decision events only;
- Memory Retrieval with provenance;
- direct-write and duplicate-proposal tests.

Do not retrofit this into the current generic event-count reducer without a migration plan. The existing spike should remain reproducible as a baseline or be replaced on a new feature branch with its original commit preserved.
