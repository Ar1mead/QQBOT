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

**Reviewer attribution hardening (2026-11-20):** `record_review()` now rejects an artifact unless its reviewer ID and version exactly match the provider identity configured on the pipeline performing the append. This prevents accidental or cross-pipeline misattribution of an otherwise valid artifact. A focused regression test was added; execution remains pending the next CI window. This is provenance hardening only, not a cryptographic trust boundary against hostile code in the same Python process.

This implementation does **not** add a CSD-owned review/decision event, human approval workflow, accepted preference/self-model reducer, or Life Engine integration. Reviewer output remains advisory and must not influence activity ranking or autonomous action. The new focused suite `tests/test_csd_cross_episode_review.py` is wired into Ubuntu/Windows CI, but no execution result is claimed until the workflow exposes actual test steps and results.


### Reviewer-v2 static-audit tightening

A follow-up static audit added a 64-event ceiling for distinct source observations and a 32-span ceiling per referenced claim, in addition to the existing character and serialized-byte bounds. V2 observation coverage metadata is passed through as provenance, while opaque account identity remains excluded. Provider output must be the exact declared candidate dataclass (not an extended subclass), and an explicit `sensitive_inference` risk flag requires `requires_human_review=true`. These are fail-closed review-interface constraints, not a semantic guarantee that the model will detect every sensitive inference. Regression tests were added; execution remains unverified because the hosted workflow still exposes no runnable job steps.

The ephemeral artifact also records a digest of the exact canonical reviewer input, separately from the candidate-event payload digest. This makes the historical evidence bundle itself auditable without persisting the review or granting it authority.

## 3.8 CSD-owned cross-episode review record

A provider review may be recorded as an immutable CSD audit event, but recording an opinion does not accept the underlying preference/interest candidate.

The reserved review event must bind the exact candidate proposal event identity, sequence, payload digest, recorded state version, canonical evidence-input digest, reviewer identity/version, and normalized bounded review output. At append time, CSD independently reconstructs the evidence input and re-resolves all accepted-claim lineage at the candidate proposal's exclusive historical boundary. The event itself must occur later than the proposal, and validation must also establish the evidence prefix is still valid immediately before the review event.

The same validator must be used for append, duplicate delivery, direct reads, and Recovery. Public event submission cannot forge the reserved event. Event identity must be deterministic and idempotent; distinct reviewers or versions can create distinct records.

This event has no reducer effect on accepted preferences, AI interests, self-model, goals, Life Engine ranking, or ASM permissions. It is an audit record only. Any later decision or preference revision is a separate CSD-owned event with its own policy, evidence revalidation, and Recovery contract.


### 3.9 CSD-owned review-record implementation status — 2026-11-20

The reserved audit event is now implemented in the active feature branch:

- Event type: `cognition.cross_episode_review_recorded.v1`; source is reserved as `csd.cross-episode-review-authority.v1`.
- `CrossEpisodeReviewPipeline.record_review(artifact)` rebuilds the candidate's canonical evidence snapshot, checks the ephemeral artifact's proposal event identity/sequence/payload digest, reviewer-input digest and recorded state version, revalidates the normalized bounded candidate, and appends a CSD-reserved immutable event.
- The event stores reviewer ID/version, review timestamp, exact proposal and evidence digests, state version, and the normalized bounded opinion. Its deterministic review ID is the digest of the canonical payload excluding the review ID; event ID is derived from that review ID.
- CSD rejects public submission of the reserved event type and reserved event-ID namespace. Internal append validation checks the reserved source.
- The shared event-local validator reconstructs the bounded review snapshot at the event's historical boundary, checks proposal chronology and exact digests, validates reviewer/result fields and reference selections, and rejects duplicate review identity.
- The same event-local validation path is invoked during append, duplicate acknowledgement, direct `get_event` reads and Recovery replay. The review event creates no mutable preference/self-model projection and has no effect on candidate acceptance, Life Engine ranking, goals or ASM.

**Verification status (reconciled 2026-11-26):** dedicated durable-review tests now exist in `tests/test_csd_cross_episode_review.py`: immutable audit append without state-version change; public-submit forgery denial; duplicate-delivery idempotency; direct-read rejection after payload and envelope hashes are recomputed around tampering; Recovery replay without candidate acceptance; and reviewer identity/version mismatch rejection. These six cases are wired into the workflow but remain **unexecuted** because hosted jobs have failed before runner allocation. The read-only pipeline tests also remain in the same file. Do not treat the durable review event as verified until the focused suite actually runs and passes.

### 3.11 Decision-time revalidation contract — design gate (2026-11-20)

The proposal append gate is not an acceptance gate. A future CSD decision path must independently reconstruct and validate the exact evidence at the decision event's exclusive historical sequence boundary; it must not trust the proposal-time snapshot, reviewer artifact, current projection, or model-supplied lineage.

Required decision transaction:

1. Begin one CSD write transaction and determine the next decision event sequence boundary. All reads below must share this transaction.
2. Load the unique pending-shadow proposal and its immutable proposal event. Reject missing, ambiguous, already-decided, malformed, or non-pending candidates.
3. Verify the proposal's `based_on_state_version` against the authoritative state version at the decision prefix. If it no longer matches, reject/defer as stale; do not silently refresh the proposal's evidence or reinterpret its original snapshot.
4. Re-resolve every support and counter-evidence `(memory_id, claim_id)` using the accepted-claim resolver at the decision prefix. Compare the canonical accepted decision/proposal lineage, claim digest, source-event IDs, and state version with the proposal's persisted reference envelope. Never accept copied claim text or reviewer-selected keys as authority.
5. Recompute distinct independent source-event counts and support/counter overlap from the re-resolved references. Duplicate references and multiple claims from one source event must not inflate independent episode counts.
6. Load the exact prior CSD-owned review record set for this proposal and this reconstructed review-input digest. The decision event must name the exact review event ID(s); it must not use an implicit "latest review", first-match, or provider-preferred lookup. Verify every referenced event is before the decision, belongs to this proposal, matches the proposal and review-input digests, and passes reviewer identity/version and opinion-schema validation. Also enumerate all prior review records for the same proposal/snapshot so the decision cannot omit an unfavorable opinion by selecting only a favorable record.
7. Apply deterministic CSD policy to the complete review set. Only an eligible `supported` opinion can proceed to a candidate-specific acceptance policy; `uncertain`, `conflicting`, `unsupported`, `insufficient_context`, sensitive-risk flags, or `requires_human_review` must not auto-accept. If multiple non-identical review records exist for the same proposal/snapshot, the first implementation must treat the set as ambiguous and refuse automatic acceptance unless a separately specified, CSD-owned supersession/adjudication protocol explicitly resolves it. A reviewer opinion alone is never sufficient.
8. Append a CSD-reserved decision event containing the exact proposal/review event references and complete reviewed-set digest, decision-time state version, canonical evidence lineage/digests, policy ID/version, outcome, and deterministic reason. The append and accepted-state reducer update must be atomic and idempotent.
9. Recovery and direct reads must replay the same event-local checks against the immutable historical prefix and reproduce identical accepted preference versions. Tampered, missing, reordered, duplicate, omitted, ambiguous, or post-decision references must fail closed.

Additional review-history rule (static audit, 2026-11-26): multiple immutable opinions may legitimately exist for one proposal because a reviewer can be run again. They must not create a "choose the favorable opinion" path. The first acceptance implementation should either (a) conservatively block automatic acceptance when more than one non-identical matching review exists, or (b) introduce a separately versioned CSD-owned supersession/adjudication event and deterministic policy. Do not infer supersession from timestamps, reviewer version strings, append order, or model-selected IDs.

Important distinction: proposal staleness is not repaired by merely re-resolving the old references. The decision must either be evaluated against the exact current authoritative prefix under an explicit refresh/reproposal protocol, or remain stale. The first implementation should choose the safer behavior: stale candidate → no acceptance; a new proposal may be created from a newly built snapshot.

Acceptance tests required before implementing the reducer:

- State changes after proposal append but before decision prevent acceptance.
- Recomputed payload/envelope hashes do not make altered claim digests or source-event lineage valid.
- Reviewer record created after the decision cannot satisfy the decision's review reference.
- Reviewer record for another proposal, another review-input digest, or a mismatched reviewer identity cannot be consumed.
- A `supported` reviewer opinion with stale/invalid references is rejected by CSD.
- Conflicting, unsupported, insufficient-context, sensitive-risk, and human-review-required opinions cannot auto-accept.
- Duplicate references and multiple claims from one source episode do not inflate independence.
- Recovery reproduces the same decision and preference revision history from the event log.
- A later favorable review cannot silently override or hide an earlier uncertain/conflicting review for the same proposal and snapshot; ambiguous multiple-review history fails closed unless an explicit CSD supersession/adjudication event exists.
- The decision's named review event IDs and reviewed-set digest exactly match the complete eligible prior review set; omitted, duplicated, reordered, or post-decision review IDs are rejected.

**Status:** design only. No decision-time acceptance API, decision event, preference reducer, or Life Engine integration is implemented by this section.

## 3.12 Reuse boundary with the existing CSD decision/replay machinery — design gate (2026-11-26)

Static inspection of `core/csd/cognitive.py` shows that the existing generic decision path is not a generic reducer API. `evaluate_proposal()`, `_apply_decision()`, and the `DECISION_EVENT` payload are specifically shaped around accepted memories and their proposal/evidence/review fields. A cross-episode preference/self-model decision must reuse the transaction, immutable event, historical-prefix, integrity and Recovery principles, but must not force a different state transition into the memory-specific payload or accepted-memory projection.

### Existing state-version semantics

- `_DecisionReplayContext.state_version_at()` counts accepted decision events, not every event in the event log.
- Observations, proposals and advisory review records do not advance the authoritative state version.
- Accepted memory/motivation/goal decisions currently contribute to the accepted-decision history used by this version calculation.
- A future accepted preference or self-model revision is a real authoritative cognitive-state transition and **must** advance the shared state version exactly once for that atomic revision event. A rejected/deferred decision or advisory review must not advance it.
- A batch that atomically revises several fields still advances the version once if represented by one revision event; it must not partially apply or count each field as an independent transition. If separate revision events are chosen, each must have its own explicit version boundary.

### Required integration points if a dedicated event family is introduced

Do not add a new event type only to `_apply_decision()`. The event family must be handled consistently across:

1. Reserved event constants/source authority and public `submit_event` denial.
2. Event-local payload/schema/identity checks in `get_event()` and `_validate_event_local_shape()`.
3. Historical proposal/review/evidence prefix validation in a dedicated decision validator; it must bind the decision to exactly one earlier cross-episode proposal and its complete eligible review set.
4. The decision replay index: `_build_decision_replay_context()` must include the new decision family when calculating accepted state versions and stable per-family event numbering.
5. The projection/reducer path: `_apply_projection_event()` must atomically append the accepted revision version and update the active projection, with no separate non-transactional write.
6. `recover()`'s reserved-source checks, known-event allowlist and sequential projection replay.
7. Projection consistency checks and state snapshot reads; direct reads and Recovery must derive the same active revisions and version history from the event log.
8. All event-ID, idempotency, duplicate-decision and stale-state checks must be deterministic and transaction-scoped.

The current code contains several explicit event-family sets and memory-specific field lists. These are not automatically extended when a new constant is added. Implementation must inventory every dispatch/allowlist/index and add regression tests for omission at each layer. Prefer a dedicated cross-episode decision/revision event and reducer over broadening the existing memory `DECISION_EVENT` contract with optional unrelated fields.

### Revision history semantics

- Store immutable revision events and versioned snapshots; never overwrite the previous preference/self-model value in place.
- Each revision identifies its owner and subject class (user preference vs AI-owned interest/self-model), domain, prior version, resulting version, operation, scope, exclusions, supporting/counter-evidence lineage, policy ID/version and deterministic reason.
- Operations such as strengthen, weaken, narrow, broaden, correct, suspend and retire must have explicit transition rules. A correction must preserve the corrected prior version and why it was superseded.
- The active projection is a rebuildable view. The event stream is authoritative; direct reads verify projection consistency, and Recovery must reproduce the same version chain.
- No revision may infer sensitive user attributes. User correction/explicit preference must outrank weak behavioral inference; absence of evidence is not evidence of a changed preference. AI-owned interests must remain distinct from inferred user preferences.
- A revision event must be atomic: either the event and resulting version become durable together, or neither does.

### Acceptance tests required before reducer implementation

- An accepted revision increments authoritative state_version exactly once; advisory review, proposal, rejected and deferred decisions do not.
- A proposal created before an accepted revision is stale at decision time and cannot be silently refreshed.
- Direct reads and Recovery reproduce identical active revision values, version numbers and prior-version links.
- Tampering with the revision payload, prior-version pointer, proposal/review references or event envelope is rejected even if outer hashes are recomputed.
- Duplicate delivery is idempotent; conflicting reuse of a revision/proposal identity is rejected.
- A failed reducer update rolls back the event append and every projection mutation in the same transaction.
- User-preference and AI-owned-interest subjects cannot be crossed or silently relabelled; explicit correction and retirement preserve the complete prior history.

**Status:** design only. No new decision event, state-version integration, preference/self-model reducer, or Life Engine connection is implemented. The existing focused review-record suite and full matrix must pass before crossing the implementation gate recorded in the handoff.

## 3.10 CI workflow repair and current runner status

A static inspection found literal backslash-`n` sequences in `.github/workflows/csd-cognitive-slice.yml` in both path-filter sections and the cross-episode review test step. These have been replaced with actual YAML line breaks in commit `06408dbf1c577849be92a15bd39a5316a32ea5df`.

After that correction, Actions Run #808 (ID `44592352031`) created both Ubuntu and Windows jobs, confirming the workflow is now parsed. Both jobs still failed immediately with empty step lists and runner ID `0`; the job-log endpoint returned BlobNotFound. No checkout, compile, or test command executed. Therefore the malformed YAML was a real workflow defect, but the remaining failure is still at job/runner allocation and its exact cause is not established.
