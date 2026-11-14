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

A semantic-review event and provider-neutral review pipeline have been added. Review records bind to immutable proposal and inference-claim digests. The reviewer submits attributed opinions only; CSD remains the decision authority. Missing reviews leave proposals pending, conflicting or uncertain reviews defer, unsupported reviews reject, and insufficient-context reviews request more evidence. This remains an in-process prototype: reviewer identity strings are not authentication, no real reviewer provider is connected, and semantic review does not prove objective truth.

Deterministic accepted-memory retrieval is implemented with substring, memory-kind, epistemic-type, evidence-event, and pagination filters. Reads fail closed if the accepted-memory projection count differs from the authoritative decision count; Recovery can rebuild it from event history. Semantic/vector retrieval is not implemented.

Hosted CI on Python 3.12.16 passed 97 tests at commit `7d57ed2dfbb3bed76fe8208de79a8cef49bdc4cf`. That historical result covered the v1 cognitive store, v1 proposal pipeline, grounded-memory store, grounded proposal pipeline, accepted-memory retrieval, and original generic persistence baseline. It did **not** cover the later semantic-review files or the new Life Engine prototype. The current workflow has been extended to include semantic-review and life-engine tests, but a current successful run has not yet been verified. Windows-local verification is also pending.

### Memory lifecycle

A separate design proposal distinguishes epistemic standing, validity, accessibility, lifecycle relations, and privacy/retention. It covers revision, supersession, consolidation, accessibility decay, cognitive forgetting, privacy erasure, and diary isolation. None of these lifecycle operations is implemented in the current prototype. In particular, the current append-only plaintext event store cannot claim secure content erasure. See `docs/design/memory-lifecycle-and-revision-contract.md`.

### Motivation and Life Engine

A provider-neutral reference slice has been added under `core/life_engine/`. It defines distinct motivational signal types, goal proposals with explicit origin references and lifecycle criteria, trusted activity options, and deliberation choices including a first-class `no_op`. Goal-origin classification is derived from the authoritative snapshot references; the deliberator cannot self-assert an internal origin. A selected external side-effect activity is only marked as requiring ASM governance; it is never dispatched by this package.

The slice has no real deliberation model, no CSD snapshot-reader or proposal-sink adapter, no persistent motivation/goal/activity event schema, and no learning/update reducer for drives or interests. It is not yet connected to CSD, DSH, SurfCore, Bilibili, QQ, or a scheduler. Its local validation is not a security boundary; CSD must repeat all authoritative checks. The 37-case Life Engine test suite was mirrored into an isolated verification environment and passed there under Python 3.13.5, including active-activity permission revocation, stop-condition enforcement, missing active-state metadata, ASM handoff classification, goal-sourced activities, paused-goal blocking, and self-commitment origin provenance. This is not a run of the exact remote checkout or the target Windows environment. The GitHub Actions workflow includes the Life Engine test step, but a successful hosted run on the current branch has not yet been verified. An evidence-grounded motivation update validator has been added. It distinguishes user-requested actions, platform autoplay/exposure, and independent choices; guards against one-off or repeated-in-one-encounter interest claims; enforces signal versions and evidence non-reuse; and stores a versioned signal statement separately from its subject/scope. Reinforcement cannot rewrite the statement or scope; contextualization creates an explicit content/scope revision. Self-commitment follow-through is not counted as independent interest evidence. It is still a pure proposal validator: the evidence snapshot must be constructed by a trusted CSD path, and the module cannot authenticate or prove its source metadata. A 44-case test file exists and the GitHub Actions workflow includes it, but the exact remote suite has not yet been verified as passing in hosted CI. In the assistant's isolated mirror, 37 Life Engine tests and 27 separate targeted motivation checks passed under Python 3.13.5; the 27 checks are not the exact 44-case repository test file and neither run is a Windows-local test. A CSD integration proposal defines trusted interaction provenance, signal decision events, projections, state-version rules, and Recovery.

The design intentionally rejects a universal weighted priority formula. Hard permissions and prerequisites are admission gates; remaining choices are deliberated with reasons, alternatives, uncertainty, and the option to wait or do nothing. The model may suggest a choice but cannot grant capabilities or bypass ASM.

See:
- `docs/design/motivation-and-life-engine-contract.md`
- `docs/design/life-engine-csd-event-contract.md`
- `docs/design/motivation-signal-formation-and-lifecycle.md`
- `docs/design/motivation-signal-test-contract.md`
- `docs/design/motivation-signal-csd-integration-contract.md`\n- `tests/test_motivation_synthesis.py`
- `docs/design/motivation-and-life-engine-test-contract.md`
- `core/life_engine/README.md`

This implementation remains an engineering experiment, not a frozen CSD rule set or a complete memory/motivation system. It does not yet implement autobiographical consolidation, forgetting, personality change, drive learning, autonomous goal formation by a real model, diary motivation, or autonomous life behavior.

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
