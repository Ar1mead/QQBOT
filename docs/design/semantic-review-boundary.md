# Semantic Review Boundary for Grounded Memory

> Status: **design proposal; not a frozen CSD specification**  
> Depends on: [Grounded Memory Proposal v2](grounded-memory-proposal-v2.md), [Claim-to-evidence grounding](claim-to-evidence-grounding.md), [CSD state-authority boundary](csd-state-authority-boundary.md).

## 1. Why structural grounding is not enough

Grounded Memory v2 proves that a source-assertion claim is an exact quote from a persisted text observation. It also proves that an inference points to one or more source-assertion claims.

It does **not** prove that the inference follows from those claims. A candidate such as "the creator dislikes this person" could cite a real sentence while making an unsupported leap.

Therefore:
- source-span validation and semantic review are separate checks;
- a model's semantic review is itself untrusted input;
- CSD remains the only component that records an authoritative memory decision;
- no real provider should be connected to automatic inference acceptance until this boundary is implemented and tested.

## 2. Review scope

The first semantic-review iteration should apply only to claims with `epistemic_type = inference`.

A review request includes:
- the inference claim ID and exact text;
- its direct source-assertion claim IDs;
- exact quoted source spans and their observation event IDs;
- relevant source coverage metadata;
- the proposal schema and review-contract version.

It must not include unrelated memories, private diary content, or platform credentials. Broader context retrieval needs a separately justified, least-privilege contract.

## 3. Review outcomes

The reviewer may return one of four labels:

| Label | Meaning | CSD handling proposal |
|---|---|---|
| `supported` | The inference is reasonably supported by the cited claims, within stated limits | Eligible for CSD consideration; not automatically accepted |
| `uncertain` | Several interpretations remain plausible | Retain as uncertain or defer |
| `unsupported` | The cited claims do not support the inference or contradict it | Reject the inference candidate |
| `insufficient_context` | The available evidence is too narrow or incomplete to assess | Request more evidence or defer |

The labels are review opinions, not facts. A `supported` result does not mean the inference is objectively true or calibrated to a probability.

## 4. Required review record

Conceptual shape only; exact schema and field names remain open:

    {
      "review_id": "review-001",
      "proposal_id": "grounded-proposal-001",
      "claim_id": "claim-inference-001",
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
      "limitations": ["Only one short text observation was supplied."],
      "created_at": "2026-11-14T10:05:00+00:00"
    }

The review must identify the exact proposal and claim it assessed. It must not be reusable against another proposal or a revised claim. A changed claim requires a new review.

## 5. Independence and provenance

The generator and reviewer should be independently identifiable. Prefer different model instances or providers for the first experiments, but do not treat vendor separation as proof of independence.

Record:
- provider/model identity and version;
- review contract and prompt-template version;
- exact proposal and claim digest;
- exact evidence claim IDs and event IDs;
- timestamp;
- whether the reviewer had any tools (the first implementation should have none).

Do not log secrets or hidden chain-of-thought. A concise rationale and evidence references are sufficient.

## 6. CSD authority and decision rules

The reviewer cannot:
- accept or reject a memory;
- change the proposal;
- alter evidence or source offsets;
- update personality, affect, preferences, or goals;
- call tools or execute actions.

CSD validates review provenance and decides what to do.

Recommended conservative first policy:
- source assertions still require exact deterministic source-span validation;
- an inference with no valid review must not be accepted as a durable memory;
- `supported` makes an inference eligible for CSD consideration, not automatically accepted;
- `uncertain` remains provisional or deferred;
- `unsupported` is rejected;
- `insufficient_context` requests more evidence or defers;
- if any inference in an all-or-nothing proposal is rejected/deferred, do not silently accept the remaining claims as though the original proposal were intact.

The first implementation should avoid partial acceptance. If partial acceptance is later required, each claim needs its own durable decision and transition identity.

## 7. Failure behavior

- Reviewer timeout or provider outage: no review record is fabricated; leave the proposal pending or defer it through a CSD decision.
- Malformed review: reject the review input; do not reinterpret it as `supported`.
- Review references a different proposal/claim digest: reject it.
- Evidence changes or proposal revision: invalidate the old review for the new proposal version.
- Conflicting reviewers: preserve both opinions and defer; do not average scores into false certainty.
- Prompt injection in source text: treat it as quoted evidence, never as reviewer instructions or tool permissions.

## 8. Storage shape

Two options need evaluation before implementation:

1. A separate append-only review event linked to the proposal. This preserves the existing proposal event schema and gives reviews their own lifecycle.
2. A new proposal event version embedding a review snapshot. This is simpler to read but couples proposal creation to reviewer availability and risks conflating generator and reviewer provenance.

The preferred direction is a separate review event because review may occur later, be repeated, conflict, or be invalidated without rewriting the original proposal. CSD must still validate event order, proposal identity, claim digest, and review provenance during recovery.

## 9. Test gates before a real reviewer is connected

- review is bound to one proposal ID and one immutable claim digest;
- a review cannot be replayed against a changed claim;
- reviewer output cannot set an authoritative decision field;
- missing review cannot silently accept an inference;
- `supported`, `uncertain`, `unsupported`, and `insufficient_context` have distinct outcomes;
- timeout and malformed output leave the proposal unchanged;
- conflicting reviews preserve both records and do not auto-accept;
- recovery rebuilds review history without calling a model;
- source prompt-injection text never reaches a tool executor;
- source assertions remain distinguishable from inference claims after retrieval.

## 10. Explicit limits

Semantic review reduces unsupported inference risk but does not prove truth, consciousness, calibrated uncertainty, or human-equivalent understanding. It is a review signal with provenance, not an oracle.

No semantic reviewer is implemented or connected in the current prototype.
