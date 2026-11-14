# Cognitive Memory Slice — Implementation Decision

> Status: **prototype implementation decision; not a frozen CSD specification**  
> Branch: `feature/csd-cognitive-memory-slice`

## 1. Preserve the persistence spike

The original `CSDStore` and its 16 baseline tests remain unchanged. The typed cognitive slice is implemented in a separate `CognitiveMemoryStore` module and uses a separate SQLite database file/schema. This avoids silently changing the original spike's schema or test meaning.

This is an intentional temporary separation, not a decision that the final product must keep two databases. A later integration decision must define migration, ownership, and backup/recovery boundaries before any merge into a shared production store.

## 2. Selected event model

The cognitive slice uses one append-only event stream with three versioned event types:

- `experience.observation_recorded.v1`
- `cognition.memory_candidate_proposed.v1`
- `cognition.memory_candidate_decided.v1`

The first two can be submitted through the public Event Submit method. The decision event is reserved: public submission rejects it. The internal evaluator appends the decision event and updates the proposal/accepted-memory projections in one SQLite transaction.

Proposal and accepted-memory tables are rebuildable projections, not independent sources of truth. The event log remains the source used by Recovery.

## 3. Identity and state version

- `event_id`: one immutable event submission.
- `proposal_id`: one immutable candidate proposal lifecycle.
- `transition_id`: one accepted state transition.
- `memory_id`: one accepted memory record.

Same event ID plus same immutable envelope/payload returns duplicate. Same event ID with changed content conflicts. Different event IDs with the same proposal ID and identical proposal payload remain distinct events but map to one proposal projection. Reusing a proposal ID with changed payload conflicts.

For this slice, `state_version` is derived from accepted decision events in the durable event history, not from the event sequence and not from the count of all decisions. The accepted-memory table is only a projection; before evaluation its count must agree with the event-derived version or evaluation stops and requires Recovery. Rejected/deferred proposals do not increment state_version. A proposal based on an older accepted-state version is deferred rather than applied blindly.

`needs_more_evidence` is a durable terminal outcome for that proposal ID in this slice. If new evidence later becomes available, the producer must submit a new proposal ID that references the new evidence/state basis. This avoids mutating an immutable proposal.

## 4. Evaluation policy: intentionally limited

The built-in policy `csd.memory-provenance-check@0.1` checks only:
- proposal schema and identity;
- evidence event existence;
- evidence event type is an observation event;
- proposal state version is current.

It does **not** determine whether the candidate wording is semantically faithful to the source, whether the event is objectively true, whether it is important, or whether a real person would remember it. The synthetic fixture is authored by the test itself. This slice validates authority, provenance wiring, transaction behavior, and recovery mechanics—not semantic memory quality.

No model call or external tool runs inside evaluation or a database transaction.

## 5. Grounded memory v2

A separate event type `cognition.grounded_memory_candidate_proposed.v1` supports atomic claims:

- `source_assertion` uses exactly one `unicode_codepoint` text span against one observation event; claim text must equal the quoted span.
- `inference` references one or more source_assertion claim IDs in the same proposal; inference chains are rejected.
- Unsupported epistemic types and unknown/authority-like fields are rejected.
- The grounded decision policy is `csd.grounded-memory-text-evidence@0.1`.
- Accepted-memory projections preserve claims, epistemic labels, evidence locators, provider provenance, and decision references.

The `GroundedMemoryProposalPipeline` binds evidence event ID, provider identity/version, and state version itself. Providers return typed source assertion/inference candidates, not arbitrary event payloads. Provider calls execute outside CSD write transactions. The pipeline stores proposals as pending only; CSD separately evaluates them.

This validates exact text provenance and schema boundaries, not source truth or inference entailment. No real model provider is connected.

## 5. Accepted Memory Retrieval

The prototype now exposes:
- `get_memories(...)`: accepted-only list retrieval with optional case-insensitive substring, memory-kind, epistemic-type, evidence-event, limit, and offset filters;
- `get_memory(memory_id)`: lookup of one accepted memory by stable ID.

Filters combine with AND semantics. Results preserve full memory provenance and do not mutate CSD state. Legacy v1 free-form content and grounded v2 claim text are both searchable by substring; only v2 claims can be filtered by epistemic type.

This is a deterministic lexical read API, not semantic retrieval. It has no embedding search, ranking, recency/salience policy, snapshot token for multi-page consistency, or retention/privacy scope.

## 5. Authority boundary and limitation

The public method rejects reserved decision event types. The decision append method is internal by convention and is called by the store's evaluation method.

This is an architectural boundary against accidental misuse, **not a security boundary against hostile code in the same Python process**. Python private/underscore methods, module imports, and the `source` string are not authentication. Before untrusted plugins or parsers can share this process, move CSD behind a separate process or authenticated local IPC with a narrowly scoped API and OS-level least privilege.

## 6. Recovery

Recovery validates SQLite integrity, foreign keys, event sequence continuity, payload hashes, and event-envelope digests. It clears and rebuilds the proposal and accepted-memory projections from the event stream in one transaction.

It never calls `evaluate_proposal`, a model, an adapter, or an external action. A proposal without a decision remains pending. A decision with missing/invalid provenance fails recovery.

## 7. Test and verification status

The test suites cover v1 observation/proposal separation, legacy provider behavior, v2 exact-span and claim-reference validation, Unicode offsets, stale state, missing evidence, proposal identity/idempotency, atomic rollback, projection inconsistency, recovery, tamper detection, provider execution outside transactions, pending-only behavior, and accepted-memory retrieval filters. The current suites contain 22 v1 cognitive-store tests, 11 v1 provider tests, 24 grounded-memory tests, 11 grounded-provider-pipeline tests, 10 retrieval tests, and 16 generic persistence tests.

The GitHub Actions workflow runs the new suite and the unchanged baseline suite on Python 3.12. A green hosted run is not a substitute for testing on the user's Windows 11 / Python 3.12.14 environment. No local Windows, power-loss, or hostile-process isolation claim is made.

## 8. Explicit non-goals

This implementation does not provide semantic memory interpretation, autobiographical truth adjudication, consolidation, forgetting, privacy/deletion policy, encryption, diary, personality, affect, drives, goals, life scheduling, Bilibili/QQ integration, ASM, or external actions.
