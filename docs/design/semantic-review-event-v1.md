# Semantic Review Event v1 for Grounded Memory

> Status: **prototype implementation proposal; not a frozen CSD specification**  
> Purpose: define an immutable, proposal-bound review record for inference claims without granting the reviewer authority over memory state.  
> Related: [Semantic Review Boundary](semantic-review-boundary.md), [Grounded Memory Proposal v2](grounded-memory-proposal-v2.md), [CSD state authority boundary](csd-state-authority-boundary.md).

## 1. Design decision

Use a **separate append-only review event** rather than embedding reviewer output into the proposal event.

Proposed event type:

`cognition.semantic_review_recorded.v1`

A review event is evidence about a proposed inference. It is not a memory decision and does not modify the proposal, accepted memory, personality, affect, goals, or diary.

The event is written through Event Submit after the target grounded proposal exists. CSD later reads the review records and decides whether the proposal can be accepted, rejected, or deferred.

## 2. Immutable binding

Each review event must bind to:
- `proposal_id`;
- the exact `proposal_event_id`;
- `proposal_digest`: SHA-256 of the canonical immutable proposal payload;
- `claim_id`;
- `claim_digest`: SHA-256 of the canonical claim object;
- reviewer identity/version;
- review-contract version.

The digest rules are:
- JSON is canonicalized with sorted keys, UTF-8, compact separators, and no non-finite numbers;
- proposal digest covers the complete stored grounded proposal payload;
- claim digest covers the complete claim object, including its epistemic type, text, references, and uncertainty;
- a changed proposal or claim requires a new proposal identity/review. A prior review must not be carried forward by matching only its text.

## 3. Proposed payload

Conceptual shape:

    {
      "review_id": "review-001",
      "proposal_id": "grounded-proposal-001",
      "proposal_event_id": "evt-grounded-proposal-001",
      "proposal_digest": "sha256:<canonical-proposal-digest>",
      "claim_id": "claim-inference-001",
      "claim_digest": "sha256:<canonical-claim-digest>",
      "reviewer": {
        "component": "independent.semantic_reviewer",
        "version": "0.1"
      },
      "contract_version": "semantic-review.v1",
      "outcome": "uncertain",
      "reasoning_summary": "The cited description is compatible with the interpretation but does not establish it.",
      "supporting_claim_ids": ["claim-source-001"],
      "alternative_explanations": [
        "The scene may be quiet without implying a stable creator preference."
      ],
      "limitations": [
        "Only one short text observation was supplied."
      ]
    }

The event envelope's `source` must identify the review pipeline that submitted the record. Reviewer identity fields are provenance labels, not cryptographic authentication.

## 4. Schema constraints

Allowed outcomes:
- `supported`
- `uncertain`
- `unsupported`
- `insufficient_context`

The first prototype supports reviews only for claims with `epistemic_type = inference` in a v2 grounded proposal.

Required validation:
- the proposal already exists and is still pending;
- proposal event ID and proposal digest match the immutable event history;
- claim ID exists in that proposal and is an inference;
- claim digest matches the exact stored claim;
- every `supporting_claim_id` exists in the same proposal and is one of the inference's declared direct `derived_from_claim_ids`;
- all list fields contain unique non-empty strings;
- reasoning summary, reviewer identity/version, and contract version are non-empty;
- unknown fields are rejected;
- a review event cannot be submitted after a terminal CSD decision.

A review ID is distinct from event ID. Reusing the same review ID and identical immutable content is an idempotent duplicate. Reusing it with changed content is a conflict. Multiple distinct review IDs may exist for the same claim so disagreements are preserved, not overwritten.

## 5. CSD evaluation policy

CSD runs deterministic source-span and claim-graph validation first. It then considers the review records for every inference claim.

| Review condition for an inference claim | CSD behavior |
|---|---|
| No review record | Return `awaiting_review`; keep proposal pending and do not append a decision event |
| All review records say `supported` | The inference is eligible for CSD consideration; it is not automatically accepted |
| All say `uncertain` | Defer the proposal |
| All say `unsupported` | Reject the inference proposal |
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

The CSD decision event should record the review event IDs it relied on, grouped by claim ID. Recovery validates that each referenced review:
- exists earlier in the event sequence than the decision;
- binds to the same proposal event and immutable digests;
- has the expected claim ID;
- has the outcome required by the CSD decision policy.

An accepted grounded memory preserves:
- the original inference claim and its epistemic type;
- review event IDs and reviewer metadata;
- the CSD decision event ID and policy version.

A `supported` review does not convert an inference into a source assertion or objective fact.

## 7. Provider pipeline boundary

A provider-neutral review pipeline should:
1. read one pending grounded proposal and its exact claim/evidence context;
2. call the reviewer outside every CSD write transaction;
3. receive one typed review candidate for each inference claim;
4. bind proposal/claim digests, reviewer identity/version, and contract version itself;
5. validate the candidate schema;
6. submit separate review events through Event Submit;
7. leave CSD evaluation as a separate operation.

The first pipeline should have no tools, browser, shell, filesystem writer, or platform action capability. Source text is quoted evidence, never reviewer instructions.

If a provider fails while reviewing a batch, no fabricated review is written. Any already submitted review for a different claim remains an immutable record; CSD keeps the proposal pending until every inference has a complete, non-conflicting review set.

## 8. Identity and security boundary

A local Python component name or event `source` string is not authentication. This prototype can verify schema, digests, and event order; it cannot prove which model/provider actually produced a review if hostile code can write to the same process.

Before connecting a real reviewer:
- isolate the reviewer adapter behind a narrow process/IPC boundary;
- authenticate the adapter's identity to CSD;
- do not give it tools or action credentials;
- preserve exact invocation/model/contract provenance;
- keep the reviewer unable to write decision events.

Do not present this prototype's reviewer label as proof of provider authenticity.

## 9. Recovery and concurrency

- Review events are immutable and replayed as data only.
- Recovery never reruns a model or recreates a review.
- A review must occur after its proposal and before its terminal decision.
- A proposal with missing reviews remains pending after recovery.
- CSD evaluation reads a consistent review set while holding its local write transaction; a concurrent review submission is serialized before or after that evaluation.
- An evaluation that sees an incomplete review set returns `awaiting_review` without a decision, so a later review can be added and evaluated.

## 10. Required tests

- review binds to exact proposal and claim digests;
- mismatched or stale proposal digest is rejected;
- mismatched claim digest is rejected;
- review cannot target source_assertion;
- supporting IDs must be direct source claims for the inference;
- identical review ID/content is idempotent; changed content conflicts;
- review after terminal decision is rejected;
- no review leaves proposal pending and returns `awaiting_review`;
- each of the four outcomes has distinct CSD behavior;
- conflicting review outcomes defer and preserve all records;
- accepted memory retains review references and inference epistemic type;
- recovery rebuilds review availability without invoking a reviewer;
- a crash before review submission leaves the proposal pending;
- provider failure does not fabricate review records;
- provider calls run outside CSD write transactions;
- source prompt-injection content never becomes a tool instruction.

## 11. Explicit limits

A semantic review is an attributed opinion about an inference, not a truth oracle. Even a supported result does not establish objective truth, calibrated confidence, subjective experience, or human-equivalent understanding.

This proposal does not define the actual model, prompt, confidence calibration, independent-review quorum, or production adapter authentication. Those remain separate decisions and gates.
