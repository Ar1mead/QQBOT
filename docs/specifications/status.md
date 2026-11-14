# Specification Status Register

This register records the status of specification work at repository initialization. It is not a substitute for the full source specifications.

## CSD

**Status: working contract; not frozen.**

A CSD contract v0.1 has been discussed. Its direction includes:

- CSD as the authoritative source of long-term cognitive state.
- Runtime components submit events rather than directly evaluating and mutating authoritative long-term state.
- Idempotent event ingestion, with deduplication and business-state updates committed atomically.
- Read interfaces for state snapshots, memory retrieval, and goal retrieval, plus event submission and recovery.
- Recovery reconciles durable logs and snapshots without replaying external side effects.
- Uncertain external outcomes are inspected and verified rather than blindly retried.

The CSD contract, recovery details, storage behavior, and test matrix still require implementation-level validation. Do not treat this summary as a verbatim specification.

### Cognitive-memory reference slice

A separate, non-production `CognitiveMemoryStore` prototype exists on branch `feature/csd-cognitive-memory-slice`. It preserves the original generic `CSDStore` baseline and uses a separate SQLite schema. The prototype distinguishes observation events, candidate-memory proposals, CSD decision events, and accepted-memory projections. The decision event and accepted projection are committed in one transaction; Recovery rebuilds projections from events without reevaluating proposals.

A provider-neutral proposal pipeline turns a replaceable provider's output into pending candidate events; it does not accept memory. Provider execution happens outside the CSD write transaction. The deterministic policy validates proposal shape, evidence existence/type, and accepted-state version only. It does not validate semantic truth or whether candidate wording faithfully represents source material. The in-process authority boundary is not security isolation against hostile code.

A text-first grounded-memory v2 path is implemented as a separate versioned proposal event. It validates exact Unicode-codepoint text spans, requires source-assertion text to equal its quote, keeps inference claims distinct, and preserves claim/evidence provenance in accepted memories. The grounded proposal pipeline binds the source observation, provider identity/version, and CSD state version; it can only submit pending proposals. This path does not establish semantic entailment or source truth, and no real proposal model provider is connected.

A semantic-review event and provider-neutral review pipeline have since been added in the current branch. Review records bind to immutable proposal and inference-claim digests. The reviewer submits attributed opinions only; CSD remains the decision authority. Missing reviews leave proposals pending, conflicting or uncertain reviews defer, unsupported reviews reject, and insufficient-context reviews request more evidence. This remains an in-process prototype: reviewer identity strings are not authentication, no real reviewer provider is connected, and semantic review does not prove objective truth. The semantic-review tests were added after the 97-test hosted run described below; that run does not validate the latest semantic-review code.

Deterministic accepted-memory retrieval is implemented with substring, memory-kind, epistemic-type, evidence-event, and pagination filters. Reads fail closed if the accepted-memory projection count differs from the authoritative decision count; Recovery can rebuild it from event history. Semantic/vector retrieval is not implemented.

Hosted CI on Python 3.12.16 passed 97 tests across the v1 cognitive store, v1 proposal pipeline, grounded-memory store, grounded proposal pipeline, accepted-memory retrieval, and original generic persistence baseline at commit `7d57ed2dfbb3bed76fe8208de79a8cef49bdc4cf`. This is a historical result for that commit, not the current branch head. Subsequent semantic-review code and tests require a fresh hosted run. Windows-local verification is also pending.

### Memory lifecycle

A separate design proposal now distinguishes epistemic standing, validity, accessibility, lifecycle relations, and privacy/retention. It covers revision, supersession, consolidation, accessibility decay, cognitive forgetting, privacy erasure, and diary isolation. None of these lifecycle operations is implemented in the current prototype. In particular, the current append-only plaintext event store cannot claim secure content erasure. See `docs/design/memory-lifecycle-and-revision-contract.md`.

This implementation remains an engineering experiment, not a frozen CSD rule set or a complete memory system. It does not yet implement autobiographical memory consolidation, forgetting, personality change, drives, autonomous goal formation, diary motivation, or autonomous life behavior.

## ASM-5.3

**Status: confirmed semantic working baseline; verbatim source restoration incomplete.**

The current confirmed baseline includes:

- ASM-5.3 is the decision gate for creating a new outbound business-action attempt.
- Retry eligibility depends on execution evidence, repeatability, and platform idempotency constraints.
- A confirmed execution prohibits retrying the same `business_action_id`; this does not prohibit other business actions under the same `correlation_id`.
- A 5.4 authorization result does not itself create an attempt; the 5.3 checks still apply.
- Verification-attempt creation/frequency is outside the retry rules for outbound business-action attempts.

This is a summary of the confirmed semantic baseline, not a replacement for the original clauses.

## ASM-5.4

**Status: under review; not frozen.**

A reconstructed, explicitly non-verbatim 5.4 text and a set of semantic questions have been discussed. The current working interpretation is that 5.4 handles retry-eligibility cases not conclusively decided by fixed 5.3 rules. It does not create attempts or change execution facts. Its decision outputs and audit requirements have been discussed, but several boundaries remain unresolved.

Do not present ASM-5.4 as finalized, and do not generate conformance tests from unresolved interpretations as if they were normative clauses.

## General handling rules

- Distinguish verbatim source text from reconstructed summaries.
- Label confirmed decisions, proposed patches, engineering assumptions, and unresolved questions separately.
- Do not silently promote an unresolved issue into a normative rule.
- Build conformance tests only against an explicitly selected and sufficiently stable source baseline.
