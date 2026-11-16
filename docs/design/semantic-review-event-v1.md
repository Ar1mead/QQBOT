# Semantic Review Event v1 for Grounded Memory

> Status: **implemented reference design; not a frozen CSD specification**  
> Purpose: define an immutable, proposal-bound review record for inference claims without granting the reviewer authority over memory state.  
> Related: [Semantic Review Boundary](semantic-review-boundary.md), [Grounded Memory Proposal v2](grounded-memory-proposal-v2.md), [CSD state-authority boundary](csd-state-authority-boundary.md).

## 1. Design decision

Use a **separate append-only review event** rather than embedding reviewer output into the proposal event.

Event type:

`cognition.semantic_review_recorded.v1`

A review event is evidence about a proposed inference. It is not a memory decision and does not modify the proposal, accepted memory, personality, affect, goals, or diary.

The event is written through Event Submit after the target grounded proposal exists. CSD later reads the review records and decides whether the proposal can be accepted, rejected, or deferred.

The reference implementation is in `core/csd/semantic_review.py` and `core/csd/cognitive.py`. It is a provider-neutral, pending-only pipeline; it does not connect to a real model provider.

## 2. Immutable binding

Each review event binds to:
- `proposal_id`;
- the exact `proposal_event_id`;
- `proposal_digest`: SHA-256 of the canonical immutable proposal payload;
- `claim_id`;
- `claim_digest`: SHA-256 of the canonical claim object;
- reviewer identity/version labels;
- review-contract version.

The digest rules are:
- JSON is canonicalized with sorted keys, UTF-8, compact separators, and no non-finite numbers;
- proposal digest covers the complete stored grounded proposal payload;
- claim digest covers the complete claim object, including its epistemic type, text, references, and uncertainty;
- a changed proposal or claim requires a new proposal identity/review. A prior review must not be carried forward by matching only its text.

## 3. Payload shape

The implementation validates a strict payload containing:
- review ID, proposal ID, proposal event ID, and proposal digest;
- claim ID and claim digest;
- reviewer component/version;
- contract version and one allowed outcome;
- concise reasoning summary;
- supporting claim IDs, alternative explanations, and limitations.

The event envelope's `source` must identify the review pipeline that submitted the record. Reviewer identity fields are provenance labels, not cryptographic authentication.

## 4. Schema constraints

Allowed outcomes:
- `supported`
- `uncertain`
- `unsupported`
- `insufficient_context`

The prototype supports reviews only for claims with `epistemic_type = inference` in a grounded v2 proposal.

Validation includes:
- the proposal already exists and is still pending;
- proposal event ID and proposal digest match immutable event history;
- claim ID exists in that proposal and is an inference;
- claim digest matches the exact stored claim;
- every supporting claim ID is one of the inference's declared direct source claims;
- list fields contain unique non-empty strings;
- reasoning summary, reviewer identity/version, and contract version are non-empty;
- unknown fields are rejected;
- a review cannot be submitted after a terminal CSD decision;
- duplicate review IDs with changed content conflict.

Multiple distinct review IDs may exist for the same claim so disagreements are preserved, not overwritten. The prototype does not require reviewer independence or a quorum.

## 5. CSD evaluation policy

CSD runs deterministic source-span and claim-graph validation first. It then considers review records for every inference claim.

| Review condition for an inference claim | CSD behavior |
|---|---|
| No review record | Return `awaiting_review`; keep proposal pending and do not append a decision event |
| All review records say `supported` | Eligible for CSD consideration; not automatically accepted |
| All say `uncertain` | Defer the proposal |
| All say `unsupported` | Reject the proposal |
| All say `insufficient_context` | Record `needs_more_evidence` |
| Review outcomes conflict | Defer; preserve every review and do not average conflicting labels |

For the first all-or-nothing proposal policy:
- if any inference is unsupported, reject the whole proposal;
- if any inference lacks review, the proposal waits for review;
- if reviews conflict or are uncertain, defer the whole proposal;
- do not silently accept source assertions from a proposal whose inference portion failed review.

A proposal with no inference claims requires no semantic review and continues through the deterministic v2 source-span path.

CSD records the final outcome in its own decision event. A reviewer never supplies the CSD decision, transition ID, memory ID, or accepted flag.

## 6. Decision provenance and accepted-memory projection

The CSD decision event records the review event IDs it relied on and the summarized review status. Recovery validates review history against the immutable proposal/claim digests and event order.

An accepted grounded memory preserves:
- the original inference claim and its epistemic type;
- semantic-review event IDs and review status;
- the CSD decision event ID and policy version.

A `supported` review does not convert an inference into a source assertion or objective fact.

## 7. Provider pipeline boundary

The provider-neutral review pipeline:
1. reads one pending grounded proposal and its exact claim/evidence context;
2. calls the reviewer outside CSD write transactions;
3. receives one typed review candidate for each inference claim;
4. binds proposal/claim digests, reviewer identity/version, and contract version itself;
5. validates candidate schema;
6. submits separate review events through Event Submit;
7. leaves CSD evaluation as a separate operation.

The first pipeline has no tools, browser, shell, filesystem writer, or platform action capability by contract. Source text is quoted evidence, never reviewer instructions.

If the provider fails while generating a batch, no review is submitted for that failed batch. Review events already committed in a separate submission remain immutable; CSD keeps the proposal pending until every inference has a complete, non-conflicting review set.

## 8. Identity and security boundary

A local Python component name or event `source` string is not authentication. This prototype verifies schema, digests, and event order; it cannot prove which model/provider actually produced a review if hostile code can write to the same process.

Before connecting a real reviewer:
- isolate the reviewer adapter behind a narrow process/IPC boundary;
- authenticate the adapter's identity to CSD;
- do not give it tools or action credentials;
- preserve exact invocation/model/contract provenance;
- keep the reviewer unable to write decision events.

Do not present the prototype's reviewer label as proof of provider authenticity.

## 9. Recovery and concurrency

- Review events are immutable and replayed as data only.
- Recovery never reruns a model or recreates a review.
- A review must occur after its proposal and before its terminal decision.
- A proposal with missing reviews remains pending after recovery.
- CSD evaluation reads a consistent review set while holding its local write transaction; a concurrent review submission is serialized before or after that evaluation.
- An evaluation that sees an incomplete review set returns `awaiting_review` without a decision, so a later review can be added and evaluated.

## 10. Verification status and limits

Reference tests exist for event validation, identity binding, outcome mapping, recovery, and provider-pipeline behavior. They were added after the historical 97-test hosted run. A fresh hosted run against the current branch is still required before claiming they pass.

A semantic review is an attributed opinion about an inference, not a truth oracle. It does not establish objective truth, calibrated confidence, subjective experience, or human-equivalent understanding. The prototype does not define a production model, prompt, independent-review quorum, or authenticated adapter.
