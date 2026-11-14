# Accepted Memory Retrieval Contract

> Status: **prototype API contract; not a frozen CSD specification**  
> Implementation: `CognitiveMemoryStore.get_memories()` and `get_memory()`

## 1. Purpose

Memory Retrieval must expose accepted durable memory with its provenance and epistemic distinctions. It must not promote pending proposals, rewrite memory, or alter personality/affect as a side effect of reading.

The current implementation is a minimal deterministic retrieval API. It is not semantic search.

## 2. APIs

### 2.1 get_memories

Conceptual signature:

    get_memories(
        query=None,
        memory_kind=None,
        epistemic_type=None,
        evidence_event_id=None,
        limit=None,
        offset=0,
    )

Filters combine with logical AND:

- `query`: case-insensitive substring search across legacy `content` and v2 claim `text`;
- `memory_kind`: exact memory-kind match;
- `epistemic_type`: `source_assertion` or `inference`; returns only memories containing at least one claim of that type;
- `evidence_event_id`: exact source event identity match;
- `limit`: optional positive integer;
- `offset`: non-negative integer pagination offset.

The return value contains accepted memories only. It returns the complete memory record, not only the matching claim, so evidence, decision, proposal, transition, uncertainty, and locator provenance are retained.

### 2.2 get_memory

`get_memory(memory_id)` returns one accepted memory by stable ID, including full provenance. Unknown IDs raise `KeyError`.

## 3. Compatibility

- Legacy v1 memories expose a free-form `content` field and `evidence_event_ids`; they remain retrievable.
- Grounded v2 memories expose a `claims` array. Each claim retains its `epistemic_type`; source assertions include exact evidence locators, and inferences include their source claim IDs.
- An `epistemic_type` filter does not classify legacy free-form memories as source assertions or inferences.
- Pending proposals are available only through proposal/event diagnostic reads, not normal accepted-memory retrieval.

## 4. Read-only invariant

Before returning results, retrieval compares the accepted-memory projection count with the authoritative accepted-decision count. If they differ, it fails closed with an integrity error and requires Recovery; it does not return a partial list. The same consistency guard applies to both list retrieval and single-memory lookup.

Retrieval must not:
- append events;
- update a decision or memory status;
- change state version;
- update affect, preferences, self-model, or goals;
- create retrieval-derived memories;
- trigger an external action.

The current tests assert that event count and authoritative state snapshot remain unchanged after reads, and that list/single-record retrieval fails closed when the accepted-memory projection is incomplete.

## 5. Known limitations

- `query` is a case-insensitive substring filter only.
- No embedding/vector similarity, semantic ranking, recency scoring, salience weighting, or cross-language retrieval is implemented.
- Pagination uses stable accepted-memory insertion order but has no snapshot token; concurrent additions between pages can shift offsets.
- There is no retention, privacy-scope, redaction, or deletion policy yet.
- The query filter returns the complete containing memory, not a claim-only excerpt.

Do not describe this as semantic Memory Retrieval. It is the first deterministic read API with source and epistemic filters; semantic retrieval is a later layer that must preserve the same provenance and read-only boundaries.
