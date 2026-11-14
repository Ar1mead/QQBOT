# Semantic Review Boundary for Grounded Memory

> Status: **design boundary with an implemented reference prototype; not a frozen CSD specification**  
> Depends on: [Grounded Memory Proposal v2](grounded-memory-proposal-v2.md), [Claim-to-evidence grounding](claim-to-evidence-grounding.md), [CSD state-authority boundary](csd-state-authority-boundary.md), [Semantic Review Event v1](semantic-review-event-v1.md).

## 1. Why structural grounding is not enough

Grounded Memory v2 proves that a source-assertion claim is an exact quote from a persisted text observation. It also proves that an inference points to one or more source-assertion claims.

It does **not** prove that the inference follows from those claims. A candidate such as "the creator dislikes this person" could cite a real sentence while making an unsupported leap.

Therefore:
- source-span validation and semantic review are separate checks;
- a reviewer's semantic opinion is untrusted input;
- CSD remains the only component that records an authoritative memory decision;
- no real provider should be connected to automatic inference acceptance until the prototype is independently tested and the provider boundary is authenticated.

## 2. Review scope

The first semantic-review iteration applies only to claims with `epistemic_type = inference`.

A review request includes:
- the inference claim ID and exact text;
- its direct source-assertion claim IDs;
- exact quoted source spans and their observation event IDs;
- relevant source coverage metadata;
- the proposal schema and review-contract version.

It must not include unrelated memories, private diary content, or platform credentials. Broader context retrieval needs a separately justified, least-privilege contract.

## 3. Review outcomes

The reviewer may return one of four labels:

| Label | Meaning | CSD handling in the prototype |
|---|---|---|
| `supported` | The inference is reasonably supported by the cited claims, within stated limits | Eligible for CSD consideration; not automatically accepted |
| `uncertain` | Several interpretations remain plausible | Defer the proposal |
| `unsupported` | The cited claims do not support the inference or contradict it | Reject the proposal |
| `insufficient_context` | The available evidence is too narrow or incomplete to assess | Record needs-more-evidence |

The labels are review opinions, not facts. A `supported` result does not mean the inference is objectively true or calibrated to a probability.

## 4. Review record and immutable binding

The prototype uses a separate append-only event, `cognition.semantic_review_recorded.v1`. Each review binds to:
- proposal ID, proposal event ID, and canonical proposal digest;
- inference claim ID and canonical claim digest;
- reviewer component/version labels;
- review-contract version and outcome;
- concise rationale, supporting direct-source claim IDs, alternatives, and limitations.

A changed proposal or claim requires a new review. The original proposal event is not rewritten.

## 5. Independence and provenance

The generator and reviewer should be independently identifiable. Prefer different model instances or providers for experiments, but do not treat vendor separation as proof of independence.

The prototype records provider/reviewer labels and version strings. **These are provenance labels, not authentication.** Any code able to submit events to the same in-process store can potentially claim those labels. The prototype therefore does not provide a trustworthy reviewer identity boundary, independent-review quorum, or production isolation.

Do not log secrets or hidden chain-of-thought. A concise rationale and evidence references are sufficient.

## 6. CSD authority and decision rules

The reviewer cannot:
- accept or reject a memory;
- change the proposal;
- alter evidence or source offsets;
- update personality, affect, preferences, or goals;
- call tools or execute actions.

CSD validates review provenance and decides what to do.

The current prototype policy is conservative and all-or-nothing:
- source assertions still require exact deterministic source-span validation;
- every inference claim requires at least one valid review before acceptance;
- all non-conflicting reviews for an inference must say `supported` for that inference to be eligible for acceptance;
- `uncertain` or conflicting outcomes defer the proposal;
- `unsupported` rejects the proposal;
- `insufficient_context` requests more evidence;
- the proposal is not partially accepted when one of its inference claims fails review.

A `supported` review is eligibility evidence only. CSD still makes and records the decision. The prototype does not define an independent reviewer quorum or calibrated scoring policy.

## 7. Failure behavior

- Reviewer timeout or provider outage: no review record is fabricated; leave the proposal pending.
- Malformed review: reject the review input; do not reinterpret it as `supported`.
- Review references a different proposal/claim digest: reject it.
- Evidence changes or proposal revision: the old review cannot be reused for the changed proposal/claim digest.
- Conflicting review outcomes: preserve all opinions and defer; do not average scores into false certainty.
- Prompt injection in source text: treat it as quoted evidence, never as reviewer instructions or tool permissions.

## 8. Recovery and event order

- Review events are immutable and replayed as data only.
- Recovery never reruns a model or recreates a review.
- A review must occur after its proposal and before its terminal decision.
- A proposal with missing reviews remains pending after recovery.
- CSD evaluation reads the review set while holding its local write transaction; concurrent submissions are serialized before or after evaluation.
- An evaluation that sees an incomplete review set returns `awaiting_review` without a decision, so a later review can be added and evaluated.

## 9. Test and integration gates

Reference tests have been added for:
- proposal/claim digest binding and mismatch rejection;
- review target and supporting-claim validation;
- duplicate review identity and conflicting review outcomes;
- each of the four outcomes;
- missing reviews and multiple inference claims;
- review after terminal decision;
- provider failure and malformed output;
- provider calls outside CSD write transactions;
- recovery without reviewer invocation.

These tests were added after the historical 97-test hosted run. Their presence is confirmed, but a fresh hosted run against the current branch is still required before claiming they pass.

Before connecting a real reviewer:
- run the complete latest suite on GitHub-hosted CI and Windows;
- isolate the reviewer adapter behind a narrow process/IPC boundary;
- authenticate the adapter's identity to CSD;
- do not give it tools or action credentials;
- preserve exact invocation/model/contract provenance;
- keep it unable to write decision events.

## 10. Explicit limits

Semantic review is an attributed opinion about an inference, not a truth oracle. It does not prove source truth, semantic entailment, calibrated confidence, consciousness, or human-equivalent understanding.

A provider-neutral review interface and pending-only pipeline exist in the reference prototype. **No real semantic-review model/provider is connected.**
