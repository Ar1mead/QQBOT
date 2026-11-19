# Cross-Episode Evidence and Preference Revision Contract

 > Status: design contract with partial read-only resolver groundwork; cross-episode proposal and CSD append/decision revalidation remain unimplemented.
> Updated: 2026-11-20.
> Scope: allow a model to propose a cautious pattern across multiple accepted episodes without allowing it to write identity state.

## 1. Why this contract is needed

The current grounded-memory proposal is intentionally tied to one observation:

- source assertions must quote exact spans from that current observation;
- inference claims may cite only source-assertion claim IDs in the same proposal;
- the semantic-review pipeline reviews those inferences against the same proposal's direct source claims;
- the prior-memory selector supplies historical context for continuity and salience, but that context is not accepted as evidence for a new fact.

This is safe for recording an episode, but it cannot represent a pattern such as "the user has repeatedly chosen quiet cafés" or a durable preference candidate supported by several independent experiences. Do not weaken the current exact-source rule to solve this. Add a separate, explicit cross-episode evidence-reference type.

## 2. Required separation of concepts

Do not conflate these records:

1. **Episode assertion** — what a source event explicitly contained, with exact event and span provenance.
2. **Historical claim reference** — a pointer to a claim already present in a CSD-accepted memory. It is not new evidence and cannot be fabricated by the model.
3. **Cross-episode interpretation** — a tentative model-generated synthesis that cites one or more historical claim references and describes uncertainty and alternatives.
4. **Preference candidate** — a proposed, revisable interpretation with support, counter-evidence, scope and confidence.
5. **Accepted preference state** — a CSD-owned, versioned projection created only after validation and the required review/approval path.

A fluent synthesis is not itself a durable preference. A semantic reviewer is not a truth oracle. A CSD-accepted preference is still a revisable system interpretation, not an immutable personality label.

## 3. Historical claim reference

The model must not provide free-form event IDs or quote historical text as if it had independently observed it. The pipeline may resolve only IDs that already appear in its selected accepted-memory context.

Proposed reference shape:

\`\`\`json
{
  "memory_id": "csd-memory:...",
  "proposal_id": "...",
  "decision_event_id": "csd-decision:...",
  "claim_id": "...",
  "claim_digest": "sha256:...",
  "source_event_ids": ["evt-observation-..."]
}
\`\`\`

Rules:

- \`memory_id\`, \`proposal_id\`, \`decision_event_id\`, and \`claim_id\` must resolve to the same accepted-memory projection and its authoritative accepted decision.
- \`claim_digest\` is computed by the pipeline/CSD over the canonical stored claim, never trusted from model output.
- \`source_event_ids\` are copied from the accepted claim's evidence lineage. The model cannot add, remove, or rewrite them.
- References must point to \`status=accepted\` memories only. Pending, rejected, deferred, needs-more-evidence, missing, or inconsistent projections fail closed.
- Duplicate references to the same claim do not count as independent evidence.
- Independence is measured by distinct underlying source event IDs, not the number of claims or repeated references.
- The proposal's \`based_on.state_version\` binds the exact CSD snapshot used to resolve references. A later state change makes the candidate stale and it must be re-evaluated or deferred.

The pipeline should send the model only a bounded allowlist of resolved references and claim contents. The model returns selected reference keys, not arbitrary IDs. The pipeline resolves those keys back to canonical references before persistence.

## 3.1 Partial implementation checkpoint — read-only resolver groundwork

Implemented on the active feature branch in `core/csd/accepted_claim_references.py`:

- Resolve only a claim contained in a CSD accepted-memory projection after projection-integrity validation.
- Require the memory's proposal ID, proposal event ID and accepted decision event ID to agree across the memory projection, proposal projection and authoritative decision event.
- Version 1 accepts only `source_assertion` claims with non-empty evidence lineage. Inference claims are deliberately excluded until recursive provenance and reviewer-v2 semantics are designed.
- Compute a canonical SHA-256 claim digest from the stored claim; copy distinct source event IDs from its evidence list.
- Bind resolution to an expected CSD state version and check it before/after reading.
- Read the accepted-memory projection, proposal, decision, proposal event and source events inside one SQLite read snapshot. If called while CSD already owns a transaction, reuse that transaction rather than opening a nested one.
- Verify the referenced proposal event is the matching grounded-proposal event; verify every source event is an integrity-valid observation/v2 event earlier than the proposal.
- The pipeline builds an allowlist from selected accepted-memory claims under opaque keys. The model may return only keys from that allowlist; the resolver re-resolves each selected key to canonical memory/claim lineage. Duplicate memory/claim pairs and repeated selected keys are deduplicated.
- Building the reference allowlist and resolving the model-selected reference bundle each happen inside one SQLite read snapshot (or reuse the caller's active CSD transaction), so a multi-claim bundle is not assembled from independently changing snapshots.

Tests added in `tests/test_csd_accepted_claim_references.py`; they are wired into the workflow, but **have not been executed**.

This is not yet the full contract above: the resolver is read-only and is not wired into a cross-episode model prompt/pipeline. New proposal append and decision paths do not yet re-resolve these references inside their own CSD transactions. No cross-episode proposal event, preference projection, reviewer v2, reducer, or Recovery exists. Therefore no preference or identity update may be accepted or used for activity ranking on the basis of this resolver.

Historical-prefix calls now reconstruct the accepted grounded memory directly from integrity-checked immutable proposal/decision/source events before the exclusive sequence boundary, rather than reading current accepted-memory/proposal projections. This is required for Recovery, which clears and rebuilds projections incrementally: a projection-wide consistency check cannot be used halfway through replay. A regression test deletes those projections and confirms that a historical-prefix resolution can still be reconstructed from event history. This remains a resolver-level primitive; the Recovery loop has not yet been extended to validate cross-episode events.

## 3.2 Partial implementation checkpoint — shadow-only candidate contract

Added `core/csd/cross_episode_proposals.py` with a typed, non-persistent proposal builder:

- Strict schema v1 and exact field allowlist; model output cannot inject memory IDs, decision IDs, event IDs, action fields, or persistence authority.
- Model output selects only opaque support/counter-evidence keys from the pipeline's resolved allowlist. The builder re-resolves every selected key against CSD at the expected state version.
- Requires at least one support reference; counter-evidence may be empty but is separately typed and cannot reuse a support key.
- Computes independent support-event count from distinct source event IDs, not the number of claims/keys.
- Separates user-owned `preference_candidate` from AI-owned `interest_candidate`; mismatched ownership is rejected.
- Requires explicit scope, exclusions, uncertainty, alternatives and limitations. The result is always `pending_shadow` / `shadow`.

This builder does not append an event, persist a candidate, change accepted memory, create a preference, or call Life Engine/ASM. One accepted episode can produce a shadow candidate for schema/testing purposes, but the independent event count exposes that it is only one episode; no reducer is allowed to promote it.

Tests in `tests/test_csd_cross_episode_proposals.py` cover valid shadow output, provenance retention, authority-field rejection, owner separation, unknown/stale keys, support/counter overlap, and malformed booleans/enums. The tests are wired into both workflow path filters and a focused CI step, but **have not been executed**.

## 4. Cross-episode synthesis proposal

Do not overload the existing single-observation \`GroundedMemoryCandidate\` schema. Introduce a separate versioned proposal family after this design is accepted.

Minimum fields:

- stable \`proposal_id\`, proposal schema/contract version, provider identity/version;
- \`based_on.state_version\`;
- one or more typed interpretation claims;
- each interpretation's statement, epistemic type, uncertainty label/confidence, reasoning summary, alternatives and limitations;
- a bounded list of historical claim references selected from the pipeline-provided context;
- explicit support and counter-evidence reference lists;
- explicit scope (what situations the interpretation applies to and what it does not claim);
- a candidate kind, initially limited to \`preference_candidate\` and \`interest_candidate\`;
- no action instructions, no direct CSD mutation, no ASM dispatch fields.

The first implementation should not support broad self-model/personality edits. Keep the first candidate domain narrow and observable.

## 5. Preference candidate and revision semantics

A preference candidate should distinguish:

- **explicit statement**: the person directly stated a preference;
- **repeated choice**: multiple independent episodes show a similar choice;
- **inferred tendency**: an interpretation that may have alternative explanations.

Minimum candidate state:

- owner/subject (user preference versus AI-owned interest must never be conflated);
- domain and statement;
- scope and exclusions;
- confidence/uncertainty;
- support references and counter-evidence references;
- independent source-event count;
- revision action: propose, strengthen, weaken, narrow, broaden, or retire;
- optional \`revision_of\` reference to the prior accepted preference version.

Guardrails:

- One ambiguous event may create a tentative interpretation, but must not silently create or rewrite a stable preference.
- Repeated evidence can increase confidence only when it is independently sourced and contextually comparable.
- Counter-evidence must remain visible; do not delete it to make a preference look consistent.
- A preference may be narrowed, weakened, superseded or retired. Preserve every prior version and the reason for change.
- A direct correction from the person is explicit evidence and must trigger review of the current interpretation; it must not be averaged away as just another weak signal.
- Do not infer sensitive personal attributes. Preference candidates should remain in the non-sensitive, task-relevant domain.

## 6. Review and CSD authority

The cross-episode semantic reviewer should receive:

- the exact candidate interpretation;
- exact canonical historical claim records and their source lineage;
- both support and counter-evidence;
- the candidate's scope and uncertainty;
- the state version and selector/retrieval metadata.

The reviewer may return supported, uncertain, unsupported, or insufficient-context, with supporting and counter-evidence reference keys, alternatives and limitations. It must not write CSD.

CSD must independently re-resolve every historical reference at proposal append and decision time, verify the accepted decision lineage and claim digest, check the state version, and reject unknown or stale references. The CSD reducer—not the model—owns preference versioning and accepted state transitions.

**Implemented append-time gate:** the new CSD-owned `cognition.cross_episode_candidate_proposed.v1` event is append-only and pending-shadow only. Its append path re-resolves every support/counter reference inside the same CSD write transaction against the exclusive event prefix, compares canonical memory/proposal/decision lineage, claim digest and source-event IDs, and recomputes the independent support-event count. The event stores lineage and digests, not copied claim text. Recovery replays and revalidates the event from immutable history; there is no separate mutable projection to become inconsistent.

**Not implemented:** a reviewer/decision event, decision-time revalidation, preference/self-model reducer, or any transition from pending-shadow to accepted state. Until those exist and pass tests, these events must not appear as accepted preference state or drive autonomous actions.

## 7. Required acceptance tests

| ID | Scenario | Expected result |
|---|---|---|
| XEP-01 | Model references a memory ID not present in supplied context | Pipeline rejects before event append |
| XEP-02 | Reference points to pending/rejected/deferred memory | CSD rejects; no preference state |
| XEP-03 | Memory, proposal, decision or claim IDs do not resolve to one accepted lineage | Reject |
| XEP-04 | Claim digest or copied source-event lineage is modified | Reject |
| XEP-05 | Same claim is repeated under several reference keys | Count once |
| XEP-06 | Two claims derive from the same source event | Do not count as two independent episodes |
| XEP-07 | Two independent accepted episodes support a tentative candidate | Candidate may be proposed, not auto-accepted |
| XEP-08 | Supporting and counter-evidence conflict | Preserve both; review as uncertain/conflicting or narrow scope |
| XEP-09 | One ambiguous observation is the only support | Do not promote to stable preference |
| XEP-10 | State changes after references are resolved | Candidate is stale and cannot be accepted against the old snapshot |
| XEP-11 | User explicitly corrects a preference interpretation | Append correction/revision evidence; retain old version and audit trail |
| XEP-12 | Reviewer says supported but references invalid evidence | CSD rejects; reviewer outcome cannot override provenance checks |
| XEP-13 | Candidate proposes an action or direct identity write | Schema rejects; ASM remains separate |
| XEP-14 | Recovery rebuilds preference history | Accepted versions and revision lineage are identical |

## 8. Implementation sequence

1. Add immutable typed historical-reference resolution over accepted CSD memories.
2. Add cross-episode proposal schema and pending-only pipeline; do not mutate accepted preference state.
3. Add semantic reviewer v2 that receives exact support and counter-evidence bundles.
4. Add CSD event-history validation for each referenced accepted decision and claim digest.
5. Add a separate CSD preference reducer with versioned propose/strengthen/weaken/narrow/retire transitions.
6. Add Recovery, conflict, stale-state and adversarial reference tests.
7. Only after the above passes should the Life Engine be allowed to use accepted preference state for activity ranking.

## 9. Explicit non-claims

This design does not establish subjective experience, consciousness, objective truth, or a human-like personality. It specifies a traceable mechanism for proposing and revising interpretations while preserving the evidence, uncertainty and authority boundaries.


## 3.3 Historical-prefix resolution requirement

A reference resolver used by append-time validation, decision-time validation, or Recovery must evaluate the CSD state that existed immediately before the event being validated. Comparing only with the current state version is incorrect: later accepted decisions must not make an older, valid proposal appear stale, and future accepted decisions must never be visible to an earlier event.

The resolver now accepts an optional `through_sequence` **exclusive** boundary: only events with `sequence < through_sequence` existed in the requested prefix. It verifies that the referenced accepted-decision event exists strictly before that boundary. Because CSD's internal `_authoritative_state_version(..., through_sequence=...)` helper uses an inclusive sequence, the resolver converts the exclusive boundary to `through_sequence - 1` before calculating the state version. This distinction is essential: a decision at the boundary must not leak into the earlier state version. The caller must use the same exclusive boundary for every reference in one event validation. Regression coverage checks the prefix immediately before and immediately after an accepted decision, plus rejection of negative, boolean and non-integer boundaries. The pending-only CSD event now invokes this resolver inside its append transaction and during ordered Recovery replay. Decision-time validation remains a future gate.


## 3.4 CSD-owned pending cross-episode event

The first durable cross-episode event family is now implemented as `cognition.cross_episode_candidate_proposed.v1`:

- It persists only candidates with `pending_shadow` / `shadow` status; there is no accept/reject/strengthen/weaken transition.
- CSD validates event identity, provider provenance, strict schema, candidate kind/owner separation, reference bounds, duplicate references and the declared independent support-event count.
- Inside the same append transaction, every reference is re-resolved against the exclusive prefix ending at the new event sequence. The persisted memory/proposal/decision IDs, claim digest, source-event IDs, accepted status and state version must exactly match CSD's canonical resolution.
- Persisted references omit copied claim text. The immutable event log is the source of truth; the read API derives pending status from the event type.
- Candidate domains are allowlisted by owner: user-preference candidates are restricted to non-sensitive interaction, communication, creative, dining-environment, media and workflow domains; AI-interest candidates are restricted to research, creative, technical and learning topics. This is a coarse domain boundary, not a semantic classifier; reviewer v2 must still reject sensitive inferences inside otherwise allowed text.
- Recovery replays the event in sequence order and repeats the same historical validation. A regression test covers successful append/read/Recovery, digest tampering, boolean state-version tampering and stale state.
- This does not implement decision-time revalidation, semantic reviewer v2, accepted preference/self-model projections, revision history or Life Engine ranking. Those remain blocked.

The test cases are added to the repository workflow, but the current branch has no verified CI execution yet.