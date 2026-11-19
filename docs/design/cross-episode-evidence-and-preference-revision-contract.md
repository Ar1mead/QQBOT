# Cross-Episode Evidence and Preference Revision Contract

 > Status: partially implemented — historical claim resolver and CSD-owned pending-shadow proposal event with append-time validation and Recovery replay exist; reviewer v2, decision-time revalidation, and accepted preference/self-model revision remain unimplemented.
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

## 3.1 Historical reference resolver and append-time validation

Implemented on the active feature branch in core/csd/accepted_claim_references.py:

- Resolve only source_assertion claims contained in CSD-accepted grounded memories; inference claims remain excluded until recursive provenance and reviewer-v2 semantics are designed.
- Require the memory, grounded proposal, accepted decision, claim and source-observation lineage to agree.
- Compute a canonical SHA-256 digest from the stored claim and copy source event IDs from its evidence lineage; the model cannot invent or rewrite these values.
- Bind resolution to an expected CSD state version and one SQLite snapshot. If CSD already owns a transaction, reuse it.
- Support an exclusive through_sequence boundary. Historical resolution reconstructs accepted memories from immutable events before that boundary, so Recovery does not depend on projections that are still being rebuilt.
- The pipeline exposes only bounded opaque reference keys. Model-selected keys are re-resolved by CSD before use.
- Repeated selected keys are rejected/deduplicated at the selector boundary as appropriate; the cross-episode builder now rejects two different opaque keys that resolve to the same memory/claim identity, before an unpersistable candidate can be produced.

Tests are present in tests/test_csd_accepted_claim_references.py and tests/test_csd_cross_episode_proposals.py. They are wired into the workflow but have not been executed because the current Actions jobs fail before exposing test steps.

## 3.2 CSD-owned pending-shadow candidate event

Implemented in core/csd/cross_episode_proposals.py and core/csd/cognitive.py:

- Strict schema v1 and exact field allowlists; model output cannot inject authority fields, CSD event IDs, direct state mutations, actions or ASM dispatch instructions.
- The builder resolves only opaque support/counter-evidence keys from the pipeline context, re-resolving each against the expected CSD state.
- Requires at least one support reference; counter-evidence is separately typed and cannot overlap support. Repeated aliases of the same historical claim are rejected.
- Computes independent support-event count from distinct underlying source event IDs, not claim/key count.
- Separates user-owned preference_candidate from AI-owned interest_candidate, with separate coarse domain allowlists.
- Requires explicit scope, exclusions, uncertainty, alternatives and limitations. Every result is pending_shadow / shadow.
- append_cross_episode_proposal persists a CSD-owned immutable event. In the same SQLite write transaction, CSD re-resolves every reference against the exclusive event-history prefix and verifies canonical lineage, claim digest, source-event IDs, accepted status, state version and independent-event count.
- Persisted events omit copied claim text. The event log remains the source of truth; list_cross_episode_proposals derives pending status from the event.
- Direct reads, duplicate acknowledgement, projection application and Recovery replay repeat the same validation. No mutable projection table is introduced and pending events do not advance authoritative state_version.

Tests cover pending-only append/read, idempotency, provenance, digest and state-version tampering, stale state, owner/domain confusion, support/counter overlap, duplicate alias keys, and Recovery replay. The tests are not executed yet.

Not implemented: cross-episode semantic reviewer v2, decision-time revalidation, CSD-owned accepted preference/self-model projection and revision reducer, or Life Engine use of such state. A pending candidate must never be treated as an accepted preference or drive autonomous action.

## 4. Cross-episode synthesis proposal

Do not overload the existing single-observation GroundedMemoryCandidate schema. The first separate, versioned CSD-owned pending-only proposal family is implemented as cognition.cross_episode_candidate_proposed.v1.

The current v1 event supports one interpretation candidate per proposal and includes:

- stable proposal_id, schema version, provider identity/version and based_on_state_version;
- candidate kind and owner, currently limited to user preference candidates and AI interest candidates;
- an allowlisted non-sensitive domain, statement, scope and exclusions;
- confidence, uncertainty, reasoning summary, alternatives and limitations;
- bounded supporting and counter-evidence references selected from pipeline-provided opaque keys;
- an independent support-event count derived from distinct underlying source event IDs.

It contains no action instructions, direct CSD mutation fields, tool grants or ASM dispatch fields. The CSD append path re-resolves every reference and persists only canonical lineage/digests. The event remains pending_shadow / shadow; it is not an accepted preference and cannot drive Life Engine ranking.

Future schema versions may support multiple interpretation claims per proposal, but only with explicit per-claim evidence bundles and bounded review semantics. The first implementation deliberately avoids broad self-model/personality edits and keeps candidate domains narrow and observable.

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

1. Historical claim-reference resolution over accepted CSD memories — implemented, including exclusive historical-prefix validation.
2. CSD-owned pending-shadow cross-episode proposal event — implemented with append-time reference revalidation and Recovery replay; focused tests are present but not yet executed.
3. Semantic reviewer v2 — next; it must receive exact support and counter-evidence bundles and return a bounded, non-authoritative review.
4. CSD-owned reviewer/decision event — next after reviewer v2; re-resolve every reference at decision time against the exact historical prefix and reject stale or altered lineage.
5. Separate CSD preference/self-model reducer with versioned propose/strengthen/weaken/narrow/retire transitions and preserved revision history.
6. Execute focused and adversarial tests, then full Ubuntu/Windows matrix; add any missing Recovery, conflict, duplicate-reference and stale-state coverage revealed by review.
7. Only after the above is implemented and verified may the Life Engine use accepted preference/self-model state for activity ranking.

## 9. Explicit non-claims

This design does not establish subjective experience, consciousness, objective truth, or a human-like personality. It specifies a traceable mechanism for proposing and revising interpretations while preserving the evidence, uncertainty and authority boundaries.


## 3.3 Historical-prefix resolution requirement

A reference resolver used by append-time validation, decision-time validation, or Recovery must evaluate the CSD state that existed immediately before the event being validated. Comparing only with the current state version is incorrect: later accepted decisions must not make an older, valid proposal appear stale, and future accepted decisions must never be visible to an earlier event.

The resolver now accepts an optional `through_sequence` **exclusive** boundary: only events with `sequence < through_sequence` existed in the requested prefix. It verifies that the referenced accepted-decision event exists strictly before that boundary. Because CSD's internal `_authoritative_state_version(..., through_sequence=...)` helper uses an inclusive sequence, the resolver converts the exclusive boundary to `through_sequence - 1` before calculating the state version. This distinction is essential: a decision at the boundary must not leak into the earlier state version. The caller must use the same exclusive boundary for every reference in one event validation. Regression coverage checks the prefix immediately before and immediately after an accepted decision, plus rejection of negative, boolean and non-integer boundaries. The pending-only CSD event now invokes this resolver inside its append transaction and during ordered Recovery replay. Decision-time validation remains a future gate.


## 3.5 Existing same-episode semantic-review input bounds

A separate hardening pass found that semantic-review v1 provider output and durable event validation checked field types and duplicate entries but did not cap the lengths of reasoning text or explanation lists. This allowed unnecessarily large model-authored review payloads to enter the event log.

The v1 review path now applies matching bounds before provider output is submitted and again when CSD validates the durable event:

- reasoning summary and each explanation/limitation item: at most 2,000 characters;
- alternative explanations and limitations: at most 8 items each;
- supporting source-claim IDs: at most 32;
- review/proposal/claim identity strings: at most 200 characters;
- digest fields: at most 80 characters.

This is input-size/schema hardening only. It does not improve semantic truth assessment and does not implement cross-episode reviewer v2. Focused regression tests were added for oversized text and lists, but have not yet been executed.

## 3.6 Cross-episode semantic reviewer v2 — implementation contract

The reviewer must inspect the candidate against both sides of its evidence, not merely repeat the candidate's reasoning. It remains an advisory component, never a CSD authority.

### Input snapshot

The pipeline must load the exact pending-shadow candidate event and resolve all support and counter-evidence references against the historical prefix immediately before that event:

- use the candidate event's sequence as the exclusive `through_sequence` boundary;
- use the candidate's recorded `based_on_state_version`;
- re-resolve each memory/claim pair through the CSD accepted-claim resolver;
- compare every persisted lineage field and claim digest with the fresh resolution;
- load each referenced source observation from the immutable event log, verify that it precedes the candidate event, and pass the exact claim plus its source evidence span and source content to the reviewer;
- deduplicate source observations by event ID while preserving which claims/references they support or contradict;
- bound the total review input size and fail closed rather than silently truncate evidence.

This historical-prefix rule is important: a later accepted memory must not invalidate an earlier candidate or leak into the evidence the reviewer saw when that candidate was created.

### Reviewer output

The provider returns one strict bounded review object containing:

- outcome: `supported`, `uncertain`, `unsupported`, `conflicting`, or `insufficient_context`;
- reviewer confidence in the review itself, separate from candidate confidence;
- a concise reasoning summary;
- selected support-reference keys and counter-evidence-reference keys, each a subset of the exact bundles supplied;
- scope assessment: `fits`, `too_broad`, `too_narrow`, or `unclear`;
- bounded alternative explanations and limitations;
- bounded risk flags, including possible sensitive inference, causal overreach, temporal instability, source ambiguity, and support/counter imbalance;
- whether independent human review is required.

The provider cannot return event IDs, CSD state changes, accepted preference values, actions, tool grants, or ASM instructions. Unknown fields, invented reference keys, support/counter overlap, malformed confidence, and oversized output fail closed.

### Authority boundary

- Reviewer v2 runs outside CSD write transactions and has no CSD mutation tools.
- Its result is a non-authoritative review artifact. It cannot accept, reject, strengthen, weaken, narrow, retire, or activate a candidate.
- A flagged or unclear sensitive inference must remain blocked; absence of a flag is not proof that the candidate is non-sensitive.
- The subsequent CSD-owned review/decision event must re-resolve all evidence again at its own sequence boundary. The reducer must independently enforce owner/domain policy, state version, explicit user corrections, support/counter balance, and revision history.
- Until that later event/reducer exists, reviewer v2 output must not affect Life Engine ranking or autonomous action.

## 3.4 CSD-owned pending cross-episode event

The first durable cross-episode event family is now implemented as `cognition.cross_episode_candidate_proposed.v1`:

- It persists only candidates with `pending_shadow` / `shadow` status; there is no accept/reject/strengthen/weaken transition.
- CSD validates event identity, provider provenance, strict/canonical schema, candidate kind/owner separation, bounded references and source-event IDs, duplicate references and the declared independent support-event count.
- Inside the same append transaction, every reference is re-resolved against the exclusive prefix ending at the new event sequence. The persisted memory/proposal/decision IDs, claim digest, source-event IDs, accepted status and state version must exactly match CSD's canonical resolution.
- Persisted references omit copied claim text. The immutable event log is the source of truth; the read API derives pending status from the event type.
- Candidate domains are allowlisted by owner: user-preference candidates are restricted to non-sensitive interaction, communication, creative, dining-environment, media and workflow domains; AI-interest candidates are restricted to research, creative, technical and learning topics. This is a coarse domain boundary, not a semantic classifier; reviewer v2 must still reject sensitive inferences inside otherwise allowed text.
- Recovery replays the event in sequence order and repeats the same historical validation. Regression tests cover successful append/read/Recovery, idempotent duplicate delivery, digest tampering, boolean state-version tampering, stale state and disallowed domains.
- This does not implement decision-time revalidation, semantic reviewer v2, accepted preference/self-model projections, revision history or Life Engine ranking. Those remain blocked.

The test cases are added to the repository workflow, but the current branch has no verified CI execution yet.

## 3.7 Cross-episode reviewer v2 — implementation status (2026-11-20)

The provider-neutral read-only pipeline is now implemented in `core/csd/cross_episode_review.py`:

- It targets exactly one existing `pending_shadow` proposal and reads the proposal, accepted claim lineage, and source observations inside one SQLite read snapshot.
- It re-resolves every persisted support and counter-evidence reference through `resolve_accepted_claim_reference`, using the candidate event sequence as the exclusive historical boundary and the candidate's recorded state version. Every persisted lineage field and claim digest must match the fresh resolution.
- It retrieves the immutable source observation events and verifies each quote's Unicode-codepoint range against the original source content. Source events are deduplicated by event ID while the evidence-span records preserve their reference key and claim association.
- Source content is bounded to 20,000 characters per observation and 100,000 characters in total; the complete serialized reviewer input has an additional byte ceiling. Oversized or inconsistent evidence is rejected, never silently truncated.
- Opaque account identity references are excluded from the reviewer input. Only bounded provenance fields needed to interpret the observation are passed.
- The provider is called only after the read snapshot closes. The provider receives no store handle, CSD mutation API, or ASM capability.
- Output validation enforces the five outcomes, finite reviewer confidence, exact support/counter reference allowlists, non-overlap, scope enum, bounded alternatives/limitations/risk flags, and a strict boolean human-review flag. `supported` requires selected support; `conflicting` requires both support and counter-evidence.
- The return value is an ephemeral `CrossEpisodeReviewArtifact` bound to proposal event ID, sequence, payload digest, state version, and reviewer identity. No review event is written and no CSD state version changes.

This implementation does **not** add a CSD-owned review/decision event, human approval workflow, accepted preference/self-model reducer, or Life Engine integration. Reviewer output remains advisory and must not influence activity ranking or autonomous action. The new focused suite `tests/test_csd_cross_episode_review.py` is wired into Ubuntu/Windows CI, but no execution result is claimed until the workflow exposes actual test steps and results.


### Reviewer-v2 static-audit tightening

A follow-up static audit added a 64-event ceiling for distinct source observations and a 32-span ceiling per referenced claim, in addition to the existing character and serialized-byte bounds. V2 observation coverage metadata is passed through as provenance, while opaque account identity remains excluded. Provider output must be the exact declared candidate dataclass (not an extended subclass), and an explicit `sensitive_inference` risk flag requires `requires_human_review=true`. These are fail-closed review-interface constraints, not a semantic guarantee that the model will detect every sensitive inference. Regression tests were added; execution remains unverified because the hosted workflow still exposes no runnable job steps.

The ephemeral artifact also records a digest of the exact canonical reviewer input, separately from the candidate-event payload digest. This makes the historical evidence bundle itself auditable without persisting the review or granting it authority.
