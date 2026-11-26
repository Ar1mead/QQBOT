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

## 3.13 Motivation and Goal are useful precedents, not interchangeable preference/self-model reducers — static audit (2026-11-26)

Static review of `core/csd/motivation.py`, `core/csd/goals.py`, their projection consistency/replay paths and their focused tests found mature reusable patterns, but also clear semantic boundaries.

### Motivation signal lifecycle

- Motivation records interaction evidence with explicit evidence kind and origin, then creates immutable proposal/decision history. Accepted signal versions are stored separately from the latest-signal projection; projection checks reconstruct expected versions from accepted decision events and compare both version and latest tables against that history.
- Each update targets an exact `target_signal_version`; stale global state or stale target versions defer rather than silently rebase. Updates retain prior support/counter-evidence references and append new evidence; pause and resolve create new versions rather than overwriting the prior version.
- Interest maturity is CSD-derived from distinct voluntary encounters at distinct instants; passive exposure/platform autoplay alone cannot count as an internally chosen encounter. Goal source lookup can retrieve the exact historical motivation signal version as of the goal decision sequence.
- **Semantic limitation:** `origin_class` describes the origin pattern of interaction evidence (internally initiated, user-requested encounter, externally exposed, mixed). It is not an ownership or subject-class field. It cannot, by itself, prove that a signal is the user's preference or that it is an AI-owned interest. The existing motivation signal model must not be reused as the preference/self-model ownership schema without a separate explicit subject/owner contract and migration plan.
- The current motivation operations are create, reinforce, weaken, contextualize, pause and resolve. Pause/resolved states are not a general-purpose preference revision vocabulary; resolved signals are not reopened by the current active-only update path. Do not infer a missing resume/reopen capability.

### Goal lifecycle

- Goal batches create candidate goals with exact source signal IDs and versions. Origin is derived by CSD from the historical signal versions; callers cannot directly choose the goal's origin class.
- Activation and pause/resume are separate, explicit CSD decisions. Each accepted transition appends an immutable `goal_versions` row and updates the latest goal projection atomically. Competing or stale proposals are rejected/deferred; Recovery replays the ordered proposal/decision history and checks every version plus the latest projection.
- A goal batch can create multiple candidate goals in one accepted decision event, so that atomic batch advances the shared accepted-decision state version once, not once per goal. Activation and each pause/resume are separate accepted decision events and each advance it once.
- Activation explicitly creates an active intention only; the current contract says it does not create activity or capability. Pause/resume likewise changes goal status only. These lifecycle transitions must not be confused with task execution, external side effects, or proof of completion.
- The inspected lifecycle currently covers candidate → active → paused → active. It does not yet define a first-class completed, abandoned, expired, blocked, superseded or outcome-evaluated lifecycle. Those states must be designed explicitly before treating goal management as a complete autonomous project lifecycle. A goal must not be auto-marked complete merely because an action was attempted or a timer elapsed.

### Reusable patterns and future requirements

Reuse the following patterns for future cognitive revisions: exact prior-version targeting; stale-state fail-closed behavior; CSD-derived classification; immutable version tables; single-transaction event/projection writes; deterministic replay; consistency checks against the event log; and tests for competing transitions, tampering, rollback and Recovery.

Do not reuse Motivation/Goal payloads as the preference/self-model schema. Future preference/self-model revisions need explicit ownership (user preference vs AI-owned interest/self-model), domain/scope, source and counter-evidence, confidence/epistemic status, correction/supersession lineage, and their own versioned reducers. Goal outcome learning should be a separate event family that records observed outcome evidence and a reasoned completion/abandonment decision; it must not silently mutate the originating motivation or user preference.

**Status:** static audit and design clarification only. No code or tests changed or executed. This section does not authorize implementation before the existing cross-episode review-record focused suite and full Ubuntu/Windows matrix pass.

## 3.10 CI workflow repair and current runner status

A static inspection found literal backslash-`n` sequences in `.github/workflows/csd-cognitive-slice.yml` in both path-filter sections and the cross-episode review test step. These have been replaced with actual YAML line breaks in commit `06408dbf1c577849be92a15bd39a5316a32ea5df`.

After that correction, Actions Run #808 (ID `44592352031`) created both Ubuntu and Windows jobs, confirming the workflow is now parsed. Both jobs still failed immediately with empty step lists and runner ID `0`; the job-log endpoint returned BlobNotFound. No checkout, compile, or test command executed. Therefore the malformed YAML was a real workflow defect, but the remaining failure is still at job/runner allocation and its exact cause is not established.


## 3.14 Goal outcome, lifecycle and learning boundary — design only (2026-11-26)

The current Goal implementation creates and activates intentions and supports pause/resume. It does not yet define a complete outcome lifecycle. This section specifies the boundary required before autonomous project execution can safely treat goals as completed, abandoned or replaced.

### Separate four different facts

Do not collapse the following into one goal status:

1. **Intention state** — what the AI currently intends to pursue (candidate, active, paused, blocked, or a terminal disposition).
2. **Execution history** — what an authorized activity or external action actually attempted. This belongs to the execution/ASM record and must preserve authorization, dispatch, attempt, response, verification and any compensation/rollback as distinct facts.
3. **Observed outcome evidence** — what happened in the world, supported by source observations or verified artifacts. An attempted action is not proof that its intended effect occurred.
4. **CSD outcome decision** — the reasoned, versioned decision about whether the goal's success criteria were met or whether it should be paused, blocked, abandoned, expired or superseded.

A Goal status must never be inferred solely from an ASM dispatch/attempt record, a tool's success-shaped response, elapsed time, a missing response, or the absence of further activity. ASM execution records and CSD goal decisions have different authority and must remain separately auditable.

### Proposed lifecycle vocabulary

- **candidate** — proposed but not activated.
- **active** — currently intended for pursuit; this creates no execution permission by itself.
- **paused** — intentionally suspended; it may later be resumed through an explicit CSD decision.
- **blocked** — progress is prevented by an identified dependency, missing permission, unavailable resource or unresolved safety condition. Record the blocker and the evidence supporting it. Removing a blocker does not silently reactivate the goal; resumption is a separate decision.
- **completed** — CSD has determined that the goal's declared success criteria are satisfied by sufficient, relevant and integrity-checked outcome evidence. Completion is not equivalent to an action being attempted.
- **abandoned** — CSD has explicitly decided not to pursue the goal further, with a reason and supporting context. It is not a synonym for temporary pause or blockage.
- **expired** — CSD has explicitly determined that a goal with a declared validity window is no longer actionable under its own terms. Merely passing a timestamp must not silently rewrite goal history; expiry requires a recorded decision and must preserve the deadline and evaluation context.
- **superseded** — CSD has explicitly retired this goal in favor of a linked successor or replacement. Preserve the successor ID and the reason for replacement; do not erase the old goal or imply that it was completed.

The lifecycle should be append-only and versioned. Each transition records the exact prior goal version and resulting version, the decision event, actor/authority, policy version, reason, and supporting/counter-evidence references. Stale or competing transitions fail closed rather than rebasing against a newer goal version.

### Outcome evidence and decision rules

- Each goal should declare bounded success criteria, scope, exclusions and (where relevant) a validity window before activation. Criteria may be refined only by an explicit versioned CSD decision; changing criteria after seeing an outcome must not retroactively manufacture success.
- A completion decision must cite evidence that directly addresses the declared criteria. Evidence may include a verified artifact, an authoritative external observation, an explicit user confirmation, or multiple independent observations where appropriate. The evidence's provenance and uncertainty must remain visible.
- A user statement can be strong evidence of the user's own intent or confirmation, but must not be represented as independent external verification of facts the user did not personally verify.
- Partial progress, a successful API response, a sent message, a downloaded file, or an action marked attempted is not by itself completion. If the goal is only to perform a bounded action, the declared criterion may be the verified performance of that action; the criterion still must be checked against the relevant execution and result evidence.
- A blocked decision must identify the blocker and what evidence would justify reconsideration. It must not grant extra permissions or cause ASM to retry automatically.
- Abandonment is a deliberate disposition, not a model-confidence threshold or a timeout. The AI may choose to stop pursuing a goal, but the decision and reason must be recorded; user-owned constraints and explicit user instructions remain authoritative within their scope.
- Expiry requires a previously declared deadline/validity rule and an explicit CSD evaluation. It must not be used to disguise failure or silently discard a goal.
- Supersession requires a traceable successor relation. The successor is a separate goal with its own criteria, evidence and lifecycle; it does not inherit completion status or execution authority automatically.
- A terminal disposition is not silently reversed. If circumstances change, create a new linked goal or use a separately specified, versioned reopening policy; do not mutate the old terminal history in place.

### Outcome learning is a separate cognitive event

A future Goal outcome-learning event should bind:

- exact goal ID and goal version evaluated;
- exact outcome decision event and lifecycle transition;
- declared success criteria and their version;
- observed outcome evidence references, provenance and uncertainty;
- relevant ASM execution/action IDs, without treating them as outcome proof;
- evaluator/policy identity and version;
- whether the result was success, partial progress, failure, blocked, abandoned, expired or inconclusive;
- a bounded explanation of what was learned and what remains unknown.

This event may inform future planning and goal selection only through an explicit CSD-controlled policy. It must not silently rewrite the original Motivation signal, user preference, AI-owned interest, self-model or goal source evidence. Any proposed change to those cognitive states requires its own proposal, evidence review, decision and immutable revision event. A single outcome may be relevant to several domains but must not automatically update all of them.

### Required adversarial tests before implementation

- Attempted/dispatched action without outcome evidence cannot complete a goal.
- A success-shaped tool response without criterion-matching verification cannot complete a goal.
- Completion with missing, stale, unrelated or tampered evidence is rejected, including when envelope hashes are recomputed.
- Criteria cannot be weakened retroactively to make an observed result count as success.
- Blocker removal does not silently resume a blocked goal or authorize ASM.
- Time passing does not silently expire a goal; an undeclared deadline cannot be used for expiry.
- Abandonment and supersession preserve prior versions and require explicit reasons; supersession binds a valid successor.
- Stale and competing lifecycle transitions fail closed; duplicate delivery is idempotent.
- Direct reads and Recovery reproduce the same complete goal lifecycle and outcome history.
- Outcome learning cannot mutate Motivation, user preference, AI-owned interest or self-model projections without their own CSD revision events.

**Status:** design only. No Goal lifecycle/outcome event family, completion evaluator, outcome-learning reducer, ASM execution integration or Life Engine feedback path is implemented by this section. Existing tests remain subject to the scheduled verification gate; this design does not authorize implementation before that gate passes.


## 3.15 Outcome feedback may inform planning without silently changing identity — design only (2026-11-26)

An evaluated outcome can be useful even when it does not justify a new preference, interest or self-model belief. Preserve that distinction: **learning how a particular approach worked is not the same as learning what the AI likes, who it is, or what it should value.**

### Separate learning targets

A future outcome-feedback path should classify each proposed lesson into an explicit target:

1. **Episode-local result** — what happened in this one attempt or project. It remains attached to that goal/outcome history and may be consulted when continuing the same project.
2. **Contextual planning constraint** — a bounded fact such as a dependency being unavailable, a tool failing under a particular condition, or a strategy being ineffective in a specific context. It may inform planning while the evidence remains current.
3. **Reusable strategy hypothesis** — a tentative expectation that a method may work or fail in a defined class of situations. It requires cross-episode evidence, scope limits, uncertainty and counterexamples; it is not a universal rule.
4. **Preference, interest or self-model revision** — a durable statement about what the user prefers or what the AI itself values, enjoys, avoids or believes about its capabilities. This is a separate cognitive revision and must use the explicit owner/subject, evidence, review and CSD decision contract. An outcome event cannot directly write it.

The first three targets may influence a future plan only through a bounded, versioned CSD planning-input projection. The fourth must never be inferred as a side effect of the first three.

### Evidence quality and attribution

- Preserve the evaluated goal, its declared criteria, context, chosen strategy, relevant execution records, outcome evidence and uncertainty. Do not reduce the result to a single success/failure score.
- Distinguish correlation from causal attribution. A failed outcome may be caused by unavailable resources, external changes, incomplete evidence, execution defects or an unsuitable strategy. Do not attribute it to the AI's ability or preference without evidence that supports that conclusion.
- Repeated retries of the same action in one episode are not independent cross-episode evidence. Count distinct source episodes/encounters, retain their context and avoid inflating confidence through duplicated observations.
- Preserve counterexamples and contradictory outcomes. A later success must not erase an earlier failure; a later failure must not erase a prior success. Planning should receive the bounded history or a deterministic summary that accounts for both.
- Evidence freshness is domain-specific. A transient service outage should not become a permanent planning rule. A changed tool/runtime version may invalidate an old strategy hypothesis without rewriting the historical outcome.
- A provider may propose a lesson or summarize evidence, but CSD must validate the referenced event history, scope and policy. Model confidence alone is not evidence and cannot authorize a durable lesson.

### Safe effect on planning

- Planning may use a supported contextual constraint or strategy hypothesis to compare candidate approaches, estimate dependencies and choose a cautious next experiment.
- The effect must be scoped to the context and validity conditions recorded with the lesson. If the context does not match, the lesson must not silently apply.
- A negative outcome may justify trying a different method, pausing for a missing dependency, or declining to repeat a costly action. It does not by itself justify abandoning an entire interest or goal domain.
- A positive outcome may justify reusing a method in similar circumstances. It does not by itself establish a durable preference, intrinsic enjoyment or a global capability claim.
- Planning must retain the option to question, test, ignore as stale, or supersede a prior strategy hypothesis when new evidence arrives. Any such change is versioned and auditable.
- The AI may choose not to pursue a plan even when prior outcomes predict success. Outcome history informs deliberation; it does not force activity or create quotas.

### Required safeguards and tests

- One successful or failed episode cannot directly create or revise a user preference, AI-owned interest or self-model claim.
- Duplicate attempts and repeated evidence from one episode do not satisfy cross-episode independence thresholds.
- Contradictory outcomes remain visible and prevent an overconfident universal strategy rule.
- A context-mismatched or stale lesson is not applied as if it were current.
- A changed tool/runtime version can invalidate a planning hypothesis without mutating historical outcome records.
- Provider-generated lessons with missing, unrelated or tampered source references are rejected by CSD.
- Planning may consult accepted, scoped lessons but cannot convert them into durable identity/preference state without the separate revision path.
- Recovery reproduces the same accepted lesson versions and planning-input projection; raw provider suggestions are never replayed as accepted lessons.

**Status:** design only. No outcome-learning event, accepted lesson projection, planning integration, preference/self-model revision or Life Engine feedback implementation is present. This section does not change the existing verification gate.


## 3.16 Goal outcome decisions, accepted planning lessons and shared state-version semantics — design only (2026-11-26)

Sections 3.14–3.15 define what may be learned from a goal outcome. This section defines when those facts become authoritative CSD state, how they affect the shared state version, and how Recovery must distinguish an outcome decision from a reusable lesson.

### Keep the event families and authority steps distinct

A future implementation should distinguish at least these stages:

1. **Observed outcome evidence** — an observation or execution result is appended with provenance. It is evidence, not a goal decision or accepted lesson.
2. **Outcome assessment proposal** — a provider or cognitive service may propose a classification/lesson bound to exact goal, criteria, evidence and execution references. It has no authority to change goal state or planning inputs.
3. **CSD goal outcome decision** — CSD validates the current goal version, declared criteria, evidence lineage and policy, then records a versioned lifecycle transition (for example completed, blocked, abandoned, expired or superseded). This is an authoritative goal-state change.
4. **Planning-lesson proposal** — a separate proposal may derive an episode-local result, contextual constraint or reusable strategy hypothesis from the recorded outcome. It is advisory until accepted.
5. **CSD accepted planning lesson** — if policy accepts a bounded lesson, a separate immutable CSD-owned event records the exact lesson, scope, validity/freshness conditions, supporting and counter-evidence, policy version and prior/result lesson version. Only this accepted projection may be consumed as durable planning input.

A goal outcome decision must not silently accept a planning lesson as a side effect. Conversely, accepting a planning lesson must not alter the goal's lifecycle status or imply that its success criteria were met. One atomic event may update multiple fields only if the schema explicitly declares them as one inseparable transition with one deterministic reducer; the first implementation should prefer separate event families to keep authority and replay auditable.

### Shared state-version rules

The shared CSD state version tracks accepted authoritative state transitions, not raw event-log length.

- Appending observation evidence, an outcome proposal, a planning-lesson proposal, or an advisory provider review does not advance the state version.
- A CSD goal outcome decision that changes an authoritative goal version advances the shared state version exactly once for that atomic decision event.
- A CSD acceptance/revision of a durable planning lesson advances the shared state version exactly once for that atomic accepted lesson event, because it changes authoritative planning input.
- A single accepted event that atomically changes several fields/records advances the version once, not once per field or goal. Separate accepted events each advance it once.
- Rejected, deferred, stale, duplicate-idempotent acknowledgements, and advisory-only outcomes do not create a new state version.
- Do not count both a goal outcome decision and a planning lesson merely because they describe the same outcome. They are separate version increments only when two distinct authoritative transitions are actually accepted: first the goal lifecycle decision, then (if separately accepted) a reusable planning lesson.
- Every proposal/decision binds the exact base state version and relevant goal/lesson versions. A later accepted transition makes a proposal stale under the existing fail-closed rule; do not silently rebase it or refresh its evidence.
- The event stream remains authoritative. The replay context, per-family ordinals, state snapshots, direct-read projection checks and Recovery must all include each new accepted event family consistently.

### Planning-input projection contract

An accepted lesson must include, at minimum:

- stable lesson ID and immutable lesson version;
- lesson class (episode-local, contextual constraint, or reusable strategy hypothesis);
- exact source goal/outcome decision and evidence event references;
- context predicates, applicability scope, exclusions and validity/freshness rule;
- strategy/tool/runtime/model version context where relevant;
- support and counter-evidence, distinct source-episode accounting and uncertainty;
- prior lesson version or explicit creation marker;
- accepting CSD decision event, policy ID/version and deterministic reason.

Episode-local outcome facts should normally remain attached to their goal/outcome record rather than being promoted into a reusable global lesson. Contextual constraints and strategy hypotheses require an explicit acceptance policy and bounded applicability. Expired or invalidated lessons remain in history but cease to affect the active planning projection through an explicit, replayable CSD transition or deterministic projection rule; they must not be silently deleted.

The planning projection is an input to deliberation, not an instruction queue. It may inform ranking or feasibility estimates, but cannot force Life Engine activity, grant ASM permissions, or override explicit user constraints and safety policy. Life Engine consumes only accepted, current, scope-matching lesson versions; it cannot write them back.

### Required adversarial tests before implementation

- Evidence/proposal/advisory review append does not advance state_version.
- One accepted goal outcome transition advances state_version once and creates exactly one goal version.
- One accepted planning-lesson revision advances state_version once and creates exactly one lesson version.
- A separately accepted goal outcome and lesson produce two ordered transitions; duplicate delivery of either is idempotent.
- A combined atomic event, if ever supported, advances state_version once and Recovery reproduces all declared fields atomically.
- Stale proposals created before either accepted transition fail closed; no silent rebase or evidence refresh occurs.
- Expired/context-mismatched lessons remain auditable but are excluded from active planning inputs consistently on direct read and Recovery.
- Replay, transaction rollback, duplicate event IDs, projection consistency and per-family ordinal accounting cover every new event family.
- A planning lesson cannot change goal status, preference, interest, self-model or ASM authorization; a goal outcome decision cannot implicitly create a planning lesson.

**Status:** design only. No outcome-decision event family, planning-lesson event/reducer, state-version integration or Life Engine planning-input connection is implemented. Existing verification gates remain unchanged.


## 3.17 Explicit subject ownership, evidence provenance and revision authority — design only (2026-11-26)

The current pending-candidate v1 schema already pairs `preference_candidate` with owner `user` and `interest_candidate` with owner `ai`, and enforces separate coarse domain allowlists. This is a useful type-confusion guard, but it is not a complete ownership contract. In particular, evidence origin, the subject a claim is about, the authority that stores a claim, and the party allowed to correct it are different concepts and must not be represented by one overloaded field.

### Four distinct concepts

A future accepted revision schema should distinguish:

1. **CSD state authority** — CSD is always the authority that validates, accepts, versions, persists and replays durable cognitive state. This is invariant and is not the semantic owner of every claim.
2. **Claim subject class** — who the claim is about: `user` or `ai_individual`. This must be a closed enum in the schema, not free-form model text.
3. **Canonical subject reference** — which user or which AI individual the claim describes. The host/CSD context supplies this opaque stable reference; the model may not invent, substitute or rebind it. A claim about one subject cannot be projected onto another.
4. **Evidence provenance/origin** — where the evidence came from and how it arose (direct user statement, user choice, user-requested activity, externally exposed material, AI-selected activity, AI-authored output, execution result, and so on). Provenance does not determine claim subject.

The legacy v1 `owner` field remains a narrow candidate-kind guard (`user` for user preference, `ai` for AI interest). It must not be interpreted as evidence origin, account ownership, permission ownership, or proof of an inner mental state. A future schema version should introduce explicit subject fields rather than silently changing the meaning of v1.

### Separate claim families

The accepted revision system should define separate families with non-overlapping semantics:

- **User preference**: a bounded claim about what the identified user prefers, dislikes, requests or finds useful in a stated context. The subject is the user. Evidence may include direct statements and repeated choices, but the system must preserve whether a claim is explicit or inferred.
- **AI-owned interest**: an operational claim about a topic or activity the identified AI individual repeatedly chooses to explore, revisit, develop or create when it has a genuine choice among permissible alternatives. This describes a persistent pattern of self-directed attention/selection, not a claim that the model has human feelings or phenomenal consciousness.
- **AI self-model**: a claim about the AI individual's own system-level tendencies, capabilities, limitations, commitments or current projects. It must be grounded in relevant internal decision history, execution records, validated outcomes or explicit configuration—not inferred from user preferences or generated self-descriptions alone.

An AI interest is not automatically an AI self-model capability claim. Enjoying/choosing a topic does not prove competence; succeeding at a task does not prove enjoyment. Likewise, a user preference is not an AI interest merely because the AI has frequently helped with it.

The initial implementation should continue to exclude broad personality, emotional-state, consciousness and sensitive-attribute claims. No claim family may infer protected or sensitive user attributes from behavior, language, platform activity or demographic proxies.

### Evidence rules for subject attribution

Evidence must be evaluated against the claim's subject, not merely against topical similarity:

- A user request, instruction, preference statement or user-selected activity can support a user-preference claim where its content actually expresses a preference. A one-off request may instead be task-specific and must not be generalized.
- User-requested AI work, user praise, user-provided material, passive exposure, autoplay, platform recommendations and model-generated statements do **not** by themselves support an AI-owned interest claim.
- AI-interest evidence should come from attributable AI-side choice records: the AI individual selected or initiated an allowed activity among real alternatives, the choice was not required by a user request or policy, and the activity received meaningful follow-through (for example, voluntary return, further exploration or creation). Preserve the alternatives, context, constraints and whether the choice was actually voluntary.
- Repeated retries within one episode, scheduler invocations, mandatory maintenance, default queue selection and repeated exposure are not independent voluntary encounters. Count distinct episodes/encounters and retain counterexamples.
- AI self-model capability/limitation claims require task- and context-specific outcome evidence. Separate the model/provider version, runtime/tool version, resource constraints and external failures from the individual's own capability. A failed tool call is not automatically an inability; a successful tool response is not automatically proof of the AI's competence.
- Model-generated introspection can be stored as a statement or hypothesis with its provenance, but it is not independent evidence that the statement is true. It cannot bootstrap its own confidence by being repeated in later generated text.
- When evidence could plausibly describe either subject, or subject attribution is not recoverable from canonical event history, the candidate must be rejected or held for explicit human review; it must not be guessed from the wording.

### Choice, agency and the meaning of AI interest

The system should only describe an interest as AI-owned when the event history shows a meaningful AI-selected choice. The relevant evidence is the individual's recorded selection/continuation among allowed alternatives, not the model's rhetorical claim that it likes something.

The choice record should identify: the available alternatives (or a bounded representation of them), the selected option, the decision context, whether the choice was user-requested/required/defaulted, applicable policy constraints, the initiating component, and subsequent follow-through or disengagement. A constrained choice is not equivalent to unconstrained autonomy; record the constraint.

Interest strength or persistence may be revised from repeated, contextually comparable choices and counter-evidence. The system must allow the AI individual to lose interest, pause, change direction or decline to continue. It must not force engagement to meet a quota, and it must not treat a scheduled wake-up or repeated prompt as voluntary interest evidence.

This is an operational design definition. It does not assert subjective experience, consciousness, sentience or human-like emotion. User-facing language should avoid presenting an inferred behavioral pattern as certainty about inner experience.

### Correction, challenge and conflict authority

- The user may directly state, correct, qualify or retract claims about the user's own preferences. Such a correction is high-priority subject evidence and must trigger a review of affected accepted versions; weak behavioral inference cannot average it away. The correction itself remains attributable and versioned.
- The user may challenge an AI-interest or AI-self-model claim, provide counter-evidence, set behavioral constraints, or request that an activity stop. These inputs must be recorded and considered, but they do not automatically become factual claims about the AI's internal state. A behavioral instruction (for example, "do not pursue this topic") is a constraint/goal input, not proof that the AI dislikes the topic.
- The AI individual's own later choices and validated outcomes may support revision of its interests and self-model through the separate CSD decision path. A provider cannot unilaterally declare its own interest or rewrite accepted identity.
- Explicit user constraints and safety policy bound what the AI may do even where an AI-owned interest candidate exists. An interest never grants a capability, permission, account access or exemption from ASM.
- Conflicting evidence must remain visible. The first implementation should fail closed on unresolved material conflicts rather than choosing the latest, strongest-sounding or provider-preferred narrative. Any supersession/adjudication must be a separate versioned CSD decision with exact prior-version and evidence references.
- Subject references and claim families are immutable across revisions. A revision cannot relabel a user preference as an AI interest, or transfer a claim from one subject to another. A genuine change of subject requires a new claim with its own evidence and lineage.

### Required adversarial tests

- User-requested work and passive/external exposure cannot create AI-interest evidence.
- Model self-description repeated across turns cannot satisfy independent evidence requirements or prove an AI interest/self-model claim.
- A voluntary AI-selected activity is distinguishable from a scheduled, mandatory, defaulted or user-requested activity; only qualifying choices count toward AI-interest maturity.
- User preference evidence cannot be assigned to the AI subject, and AI decision/outcome evidence cannot be assigned to the user subject without a separately supported user claim.
- Missing, forged, substituted or cross-linked subject references are rejected on proposal append, decision, direct read and Recovery.
- A task success/failure cannot be converted into a global capability claim without accounting for context, runtime/provider/tool version and external causes.
- A user's explicit correction of their own preference cannot be diluted by weak inferred evidence; a user instruction about AI behavior is not misclassified as an AI preference.
- AI interest and AI self-model claims cannot be merged; topic selection does not prove competence, and task success does not prove interest.
- Conflicting subject evidence remains represented and cannot be hidden by a later favorable review or implicit latest-record selection.
- No accepted preference/interest/self-model claim grants ASM authority, overrides safety policy or forces Life Engine activity.
- Recovery reproduces exact subject identity, claim-family boundaries, evidence provenance, correction history and active revision projections.

**Status:** design only. Existing v1 code enforces a coarse candidate-kind/owner/domain pairing and keeps proposals pending-shadow. It does not implement canonical subject references, AI-side voluntary-choice evidence, separate AI self-model claim families, accepted revision reducers or the above correction/adjudication protocol. No implementation or verification gate is changed.


## 3.18 Existing interaction-choice events are evidence candidates, not proof of AI agency — static audit (2026-11-26)

A follow-up static inspection of `core/csd/motivation.py`, `core/csd/cognitive.py`, `core/csd/goals.py` and `adapters/contracts/observation.py` checked whether the current event model can already prove the voluntary AI choices required by §3.17.

### What exists today

The current `experience.interaction_choice_recorded.v1` event contains an encounter ID, `subject_ref`, evidence kind, origin, context, `meaningful_alternatives`, `choice_set_refs`, `selected_ref`, optional origin/related event IDs, adapter component/version and session scope.

Its validator enforces useful shape and chronology constraints:

- Evidence kinds and origins are enumerated.
- User-requested actions and platform autoplay require an earlier origin event; user-request and platform-recommendation origins are checked against earlier observation event kinds.
- Voluntary selection and return-visit evidence require `internal_state` origin, a declared meaningful choice set with at least two entries, and a selected reference contained in that set.
- A return visit must point to an earlier interaction event for the same subject and selected item, at a distinct later encounter/time.
- The event source string must match the declared adapter component.

Motivation then derives an `origin_class` from the evidence origins. Goal origin is derived from the historical motivation signal rather than caller-supplied directly.

### What these checks do not establish

The current validator does not yet provide the full attestation required to use these records as durable proof of an AI individual's self-directed interest:

- `subject_ref` is checked as non-empty text, but the inspected path does not bind it to a canonical AI-individual identity supplied by a trusted host/CSD identity context.
- `choice_set_refs` and `selected_ref` are checked as strings and membership, but the inspected validator does not resolve each alternative to an independently recorded, eligible choice option or prove that the alternatives were genuinely available to the AI.
- Matching `event.source` to `interaction-adapter:<component>` checks internal consistency of two caller-provided labels; it is not, by itself, attestation that the named adapter/runtime made the observation.
- The generic public event-submit guard reserves CSD decision/review event families, but does not reserve `INTERACTION_EVENT` to a CSD-owned attestation path. Therefore the event should not be treated as tamper-resistant proof of voluntary agency merely because it passes the current schema validator.
- `internal_state`, `self_commitment` and `autonomous_question` are provenance labels. They do not independently prove that an action was optional, non-defaulted, not scheduler-forced, not user-requested and not required by policy.

These are limitations of the current evidence contract, not evidence that existing Motivation/Goal behavior is otherwise invalid. Existing records remain useful as provenance-tagged motivation evidence under their current semantics. They must not be silently upgraded into the stronger AI-interest evidence defined in §3.17.

### Required future evidence-attestation boundary

Before AI-owned interest revisions can rely on voluntary-choice evidence, a future versioned event/API should:

1. Bind the subject to a canonical AI-individual reference issued by the host/CSD context; reject model/caller-selected subject substitution.
2. Bind the choice episode to a CSD-validated decision record that identifies the decision-maker, initiating cause, allowed alternatives, selected alternative, constraints and whether the activity was mandatory, defaulted, user-requested, scheduled or optional.
3. Resolve choice-set entries to canonical earlier events or host-issued opaque option records. A list of arbitrary strings is not sufficient evidence that alternatives existed.
4. Establish adapter/runtime provenance through the trusted host dispatch path and pinned adapter manifest/version; a self-declared source string alone is not attestation.
5. Preserve the original user request, policy constraint, scheduler/wakeup cause and other causal triggers so that a constrained action cannot be reclassified as voluntary after the fact.
6. Make the event immutable and validate its subject, choice lineage and attestation on append, direct read and Recovery. Public callers may submit observations or proposals, but cannot forge the host's record of an AI-internal choice.
7. Keep this evidence advisory until the separate CSD-owned interest revision decision accepts it. Even an attested voluntary choice does not itself create an accepted interest or grant activity/tool permissions.

### Additional adversarial tests

- A caller cannot forge an AI-internal choice by supplying `origin=internal_state`, `subject_ref`, `choice_set_refs`, `selected_ref` and a matching adapter source string.
- An unknown, substituted or non-AI subject reference is rejected.
- A selected option not present in the canonical prior choice set, or an option that was never actually available, is rejected.
- User-requested, scheduler-triggered, mandatory, defaulted and policy-required actions cannot be relabelled as voluntary by changing the evidence-kind/origin fields.
- A later change to adapter identity, decision provenance or choice lineage is detected by direct read and Recovery, including when outer event hashes are recomputed.
- A valid attested choice remains evidence only; it does not directly accept an interest, change self-model or authorize Life Engine/ASM activity.

**Status:** static audit and design clarification only. The current interaction event remains in place for existing Motivation semantics. No attested-choice event/API, canonical AI subject binding, choice-option resolver or new tests were implemented or executed. This finding does not change the existing hosted-test gate.


## 3.19 End-to-end observation actor and claim-subject binding — static audit (2026-11-26)

The §3.18 review focused on AI-side choices. A final pass traced identity from external observation into interaction evidence and then into Motivation/Goal.

### Current observation identity fields

Observation v2 records adapter/platform provenance and permits optional `account_ref`, `context_kind`, `context_ref`, `actor_ref`, `actor_role` and `parent_ref`. The event is required to remain untrusted, and the CSD checks the content digest, adapter identity/source shape and field consistency.

These fields preserve useful provenance, but `actor_ref` is optional and is supplied as part of external adapter evidence. It is not, by itself, a canonical CSD subject identity or proof that the actor is the owner of a preference claim.

### Missing cross-event binding

The current interaction validator requires a non-empty `subject_ref`. For user-request and platform-recommendation origins it checks that `origin_event_id` points to an earlier observation of the expected observation kind. The inspected path does not additionally require:

- the interaction `subject_ref` to resolve to a canonical user/AI subject registry;
- the interaction subject to match the actor/account identity resolved from the referenced observation;
- the claim subject in a later preference candidate to match the interaction subject;
- the candidate subject to be distinct from the message speaker when the statement is explicitly about another person;
- a host-issued AI-individual identity for internally generated interactions.

Consequently, event chronology and observation-kind checks establish that an earlier event exists, but do not yet establish end-to-end identity continuity from observed actor → interaction subject → motivation signal subject → cross-episode claim subject. A model-proposed `subject_ref` or a non-empty string must not be treated as proof of that continuity.

### Required end-to-end identity contract

A future versioned subject registry/binding layer should define:

1. **Canonical subject IDs:** CSD/host-issued opaque IDs for each supported user and AI individual. IDs are stable within the declared identity scope, not derived directly from display names, QQ numbers or arbitrary model output.
2. **Account/actor mapping:** trusted adapter context maps a platform account + actor identity to a canonical subject under an explicit account-linking policy. External `actor_ref` remains untrusted provenance until the host validates that mapping.
3. **Evidence actor vs claim subject:** preserve who authored or performed the observed event separately from whom the claim describes. A message from user A about user B is not evidence that the preference belongs to user A. Third-party preference/personality inference should be excluded from the initial scope unless a separate consent and privacy design is approved.
4. **Interaction binding:** a user-requested interaction must bind to the canonical subject represented by its source observation; an AI-internal interaction must bind to the host-configured AI-individual ID. The caller/model cannot choose a different subject.
5. **Motivation and goal binding:** each signal and goal retains the exact canonical subject ID and source-event lineage. Origin classification remains a separate provenance attribute and cannot substitute for subject identity.
6. **Cross-episode binding:** every candidate and eventual accepted revision binds the same canonical subject ID across all supporting/counter-evidence. Mixed-subject evidence must be split into separately supported claims or rejected; it cannot be pooled to increase confidence.
7. **Lifecycle and Recovery:** identity mappings are versioned and auditable. Account relinking, account removal or subject retirement must not silently rewrite historical subjects; Recovery must replay the identity mapping version that applied when each event was accepted.

### Required tests

- An observation with a missing or untrusted actor reference cannot silently become a canonical user identity.
- A user-request interaction cannot claim a different subject from the host-resolved actor in its source observation.
- A message authored by one user but describing another person cannot create a preference claim about the speaker or the third party by default.
- Two users' evidence cannot be combined into one preference or interest candidate.
- An AI-internal interaction cannot use a user subject ID, and a user interaction cannot use the AI-individual ID.
- Motivation signal, Goal and cross-episode candidate subject references must remain consistent with their historical source lineage.
- Account relinking or subject retirement does not rewrite historical event meaning; direct reads and Recovery preserve the historical identity mapping version.
- Model-generated subject IDs, aliases or account mappings are rejected unless resolved by the trusted host/CSD registry.

**Status:** static audit/design only. Existing observation v2 and interaction events preserve provenance but do not yet provide the complete canonical subject registry or end-to-end actor/subject binding above. No code or tests were changed or executed. The existing verification gate remains unchanged.


## 3.20 QQ multi-user identity and Private Home subject boundaries — architecture reconciliation (2026-11-26)

The platform/runtime architecture and the autonomous-life design are compatible with §§3.17–3.19, provided identity scopes remain explicit.

### QQ observations and multiple people

The initial QQ adapter is receive-first and normalizes private/group messages with account, conversation, sender, message and timestamp provenance. Therefore a conversation is not a single person and a group is not a single preference subject.

- Preserve platform account, conversation and sender identity as separate provenance dimensions.
- Resolve a sender to a canonical user subject only through the host's explicit account/actor mapping policy. Do not use a group ID, conversation ID, bot account ID or display name as the user subject.
- A message author's preference statement may support a claim about that author when it is genuinely first-person and contextually clear. A quoted message, forwarded text, third-party statement or group consensus must not silently become the author's preference.
- The initial implementation should not infer or persist third-party preferences, personality or sensitive traits. A third party mentioned in a group conversation is not automatically a project subject.
- Evidence from different senders must never be pooled as if it came from one user. Group-level patterns, if ever needed, require a separate aggregate contract with privacy thresholds and must not be written into any individual's preference state.

### AI individual identity and Private Home

- The canonical AI-individual subject is independent of the QQ bot account, DSH runtime, SurfCore installation, model provider, model version and any single platform adapter. Replacing one of these must not silently create a new individual or transfer the individual's identity to another subject.
- The AI individual's Private Home is its own activity/workspace record: diary drafts, research notes, creative work, project artefacts and private reflections remain distinguishable from user-authored messages and external platform material.
- A user message or external source copied into Private Home retains its original actor/source and untrusted provenance. Storage in the AI workspace does not convert it into an AI-authored experience, a voluntary AI choice or an accepted self-model fact.
- A Private Home document saying "I like this" is a self-description/document artefact, not sufficient evidence of AI interest. It must be evaluated through the same independent choice/outcome and CSD revision rules.
- The AI-individual ID remains stable across allowed runtime/provider/adapter replacement. A genuinely new individual requires an explicit identity-creation decision and must not inherit another individual's private state by default.

### Acceptance tests

- Two senders in one QQ group resolve to different canonical user subjects; neither the group nor bot account is used as a preference subject.
- A quoted/forwarded third-party preference is not stored as the sender's own preference or as a third-party profile.
- Evidence from multiple group members cannot be pooled into one person's preference revision.
- User-authored content placed in Private Home retains its source actor and cannot count as AI-authored diary, voluntary choice or AI-interest evidence.
- Replacing DSH, SurfCore, a model provider or QQ adapter preserves the same AI-individual subject without merging platform users.
- Creating a new AI individual does not inherit another individual's Private Home or accepted self-model unless an explicit, separately reviewed transfer policy exists.

**Status:** architecture reconciliation only. The current adapter contract already preserves QQ sender/account/conversation provenance and keeps the AI core identity separate from platform/runtime infrastructure, but canonical subject resolution and Private Home identity binding are not implemented. No code or tests changed or ran.


## 3.21 Implementation sequence and first safe vertical slice — design only (2026-11-26)

This section converts §§3.17–3.20 into an implementation order. It does not authorize implementation before the existing verification gate passes.

### Stage 0 — reopen the verification gate

1. Around 2026-12-02, inspect GitHub Billing and confirm the included Actions allowance has actually reset. Do not infer reset from the calendar.
2. Run `tests/test_csd_cross_episode_review.py` first. Confirm checkout and test steps really execute on an allocated runner and all focused tests pass.
3. Only after that, run the full Ubuntu/Windows matrix and require actual completed test jobs. A missing run, runner-allocation failure, empty job-step list or stale status is not a pass.
4. Do not add payment details, enable paid overage, make the repository public, run local tests or trigger unnecessary workflow runs without explicit authorization.

### Stage 1 — canonical subject registry and trusted identity binding

This is the first implementation slice after Stage 0. It is deliberately narrower than preference/interest revision.

**Identity records**

- Add a CSD-owned, append-only subject registry for `user` and `ai_individual` subject classes. The canonical subject ID is opaque, generated by the trusted host/CSD identity service, and never supplied or selected by the model.
- The AI-individual ID is supplied by stable host configuration and remains unchanged across DSH/SurfCore/provider/model/adapter replacement. A new individual requires explicit creation; no private state is inherited by default.
- User subjects are scoped to the local installation/identity domain. Different QQ senders are different subjects unless an explicit, separately authorized account-linking operation establishes that they are the same person.
- Keep platform account/actor identifiers out of canonical subject IDs. Prefer host-held mapping secrets and opaque binding keys in CSD; do not persist raw QQ identifiers or credentials in the subject registry.

**Trusted platform binding**

- Add a CSD/host-only binding path that maps a verified platform identity tuple (platform + adapter/account scope + actor) to one canonical user subject.
- The adapter/host resolves the identity from its authenticated connection/session. A model payload, observation field or public `submit_event` caller cannot create, relink or revoke an identity binding.
- Account linking requires an explicit user-authorized flow. Do not infer that two platform accounts belong to the same person from names, message similarity, group membership or model interpretation.
- Binding revocation/relinking is represented by new immutable events. Historical observations retain the mapping version that applied when they were accepted; revocation does not rewrite past authorship.
- The same platform actor key cannot be actively bound to two subjects in the same declared scope. Conflicts fail closed. Cross-platform identity merging is out of the first slice unless explicitly authorized and separately designed.

**Versioning and CSD integration**

- Identity events are CSD-reserved: public event submission cannot forge subject registration, binding, relinking or revocation. Event IDs and source namespaces are reserved; internal append validates event-specific schema, chronology, uniqueness and authority.
- Maintain a separate monotonic `identity_version` (or equivalent identity-registry revision) rather than overloading cognitive `state_version`. Each accepted atomic identity transition advances identity_version exactly once; observations and proposals do not.
- Any observation/interaction/candidate that uses identity resolution records the exact identity_version/binding reference used. If the mapping changes, stale proposals fail closed and must be rebuilt; they are never silently rebound.
- Direct reads, full-history validation, Recovery/replay and projection consistency checks reconstruct the same registry and active bindings. Duplicate delivery is idempotent; identity conflicts are integrity failures.
- Identity registry state is not a user preference, AI interest or self-model claim and must not be projected into Life Engine ranking or ASM permissions.

**Stage 1 acceptance tests**

- Only the internal CSD/host path can register a subject or create/revoke a binding; public submit cannot forge reserved identity events or namespaces.
- AI-individual subject identity is stable across runtime/provider/adapter changes; a new individual does not inherit the prior individual's private state.
- Two senders in one QQ group map to distinct user subjects by default; group, conversation and bot-account references cannot become user subjects.
- Missing/unverified actor provenance cannot resolve to a canonical user subject.
- One active platform actor binding cannot point to multiple subjects in the same scope; unauthorized relink and ambiguous cross-platform merge fail closed.
- Binding revocation preserves historical event attribution and increments identity_version once; duplicate delivery is idempotent.
- Tampering with subject/binding events, event envelopes, identity version projections or historical mapping versions is detected on direct read and Recovery.
- No raw credentials or model-invented subject IDs are accepted or persisted.

### Stage 2 — bind observations and interaction records

- Resolve Observation v2 actor/account provenance through the trusted host binding service; keep the original external actor reference untrusted and separate from canonical subject identity.
- Add a versioned interaction-choice attestation event created only by the trusted host/CSD decision path. Bind the canonical AI subject, exact choice-set records, decision/trigger lineage, policy constraints and whether the choice was optional, user-requested, scheduled, defaulted or mandatory.
- Preserve evidence actor, claim subject and source event as separate references. Do not infer third-party profiles. Mixed-subject evidence is split or rejected.
- Validate append, direct read and Recovery. Existing `experience.interaction_choice_recorded.v1` remains under its existing Motivation semantics and is not retroactively upgraded into attested agency evidence.

### Stage 3 — bind Motivation, Goal and cross-episode proposals

- Add canonical subject references and exact identity-version lineage to new versioned Motivation/Goal records. Do not silently reinterpret legacy records; provide an explicit migration/backfill policy or leave them unbound.
- Require all support and counter-evidence in a candidate to resolve to the same claim subject. Mixed-subject evidence cannot be pooled.
- Keep `origin_class` as provenance only. It never substitutes for subject identity.
- Keep user preference, AI-owned interest and AI self-model as separate claim families. AI interest requires Stage 2 attested voluntary choices; capability/self-model claims require context-specific validated outcomes.
- Continue to keep proposals pending-shadow until a separate CSD-owned decision accepts them.

### Stage 4 — accepted revisions and downstream projections

- Only after earlier stages and their tests pass, implement decision-time full evidence/identity revalidation, versioned preference/interest/self-model revision events and reducers, correction/adjudication rules, direct-read/Recovery checks and idempotency.
- Integrate accepted projections into deliberation/Private Home/Life Engine as bounded planning inputs. No projection forces activity or grants ASM authority.
- Goal outcome learning and planning lessons remain separate from identity and preference revisions under §§3.14–3.16.

### Scope exclusions for the first implementation

No cross-platform person matching, third-party profiling, group-level preference inference, raw identifier/credential storage, automatic identity merging, personality/consciousness claims, self-model generated from introspection alone, accepted preference/interest reducers, Life Engine wiring or ASM permission changes.

**Status:** implementation sequence only. No code or tests were changed or executed by adding this plan. Stage 0 remains pending; Stage 1 is the first code slice only after focused and full hosted verification passes.


## 3.22 Privacy-safe platform references and identity-key lifecycle — static audit (2026-11-26)

A static trace of `adapters/platforms/surfcore/mapping.py` → `ObservationEvidence` → `adapters/csd_mapping.py` → Observation v2 found that QQ `sender_ref` is copied to `actor_ref`, and `account_ref`, `context_ref` and other source references are copied into the durable CSD observation payload. The current observation validator checks these fields are non-empty strings; it does not establish that they are opaque or safe to persist. The SurfCore mapper also derives `observation_id` using an unkeyed SHA-256 over `platform + account_ref + record_id`, which is deterministic but is not a privacy-safe identity pseudonym when inputs can be guessed.

This is a concrete gap between the existing adapter data path and the privacy requirement in §3.21. The fact that an observation is marked `untrusted` does not make its identifiers private.

### Required data boundary

1. Raw platform account IDs, sender IDs, group/conversation IDs, private message IDs, cookies, access tokens and other credentials must remain inside the authenticated adapter/host boundary and must not be written to CSD event payloads, durable projections, logs, diagnostics, prompts or model context unless a separately reviewed data-minimization exception requires a specific non-identity resource reference.
2. Before creating a durable Observation v2 event, the trusted host must transform identity-bearing references into opaque, purpose-separated pseudonymous references. At minimum this covers account scope, actor/sender, conversation/group and any message/resource reference that embeds or directly reveals a person/account identifier.
3. Do not use plain SHA-256, unsalted hashes, reversible encodings or model-generated aliases for identity pseudonyms. Use a keyed construction such as HMAC-SHA-256 with domain separation and explicit schema/key version, or a host-generated random opaque mapping token. Treat the output as pseudonymous and still linkable—not anonymous.
4. Keep distinct pseudonym namespaces for account scope, actor, conversation and resource/message references. Do not reuse one token across fields or platforms where that would create unnecessary cross-context linkability.
5. Resolve a canonical user subject only from the trusted host's authenticated platform/account/actor tuple. A group/conversation pseudonym is context provenance, never a user identity. The bot's own account scope is not the sender's subject.
6. Preserve non-sensitive public resource references only when their schema and retention purpose are explicit. If a reference may contain an account/person identifier, pseudonymize it or omit it from the durable event; retain a separately approved retrieval handle only in the protected adapter boundary.
7. The worker may transport raw identifiers transiently only as required to obtain/normalize observations. The trusted host must pseudonymize them before CSD submission. Worker output, exception text, logs and telemetry must not leak raw identifiers or credentials.

### Key custody, rotation and loss

- Define a platform-neutral host `IdentityKeyProvider` contract. The CSD database and event log store key IDs/versions and pseudonymous references, never secret key material.
- The key must be generated by the trusted host, kept outside Git and the CSD database, protected by the host's secure credential facility or an equivalently protected encrypted secret store, and never exposed to model prompts or adapters running as untrusted workers.
- HMAC input encoding must be canonical and domain-separated, including installation scope, platform, adapter/account scope, reference class and the raw identifier. Ambiguous string concatenation is forbidden.
- Rotation is a versioned migration, not silent key replacement. During an authorized rotation the host may resolve with the old key and create a new pseudonym with the new key, preserving the same canonical subject through an explicit CSD binding-transition event. Old key versions remain available only as long as required for migration/restore and are retired under a documented policy.
- Loss of the key must fail closed: existing bindings become unresolved, not reassigned. Do not generate a replacement key and silently bind the same incoming accounts to new or guessed subjects. Recovery requires restoring the protected key backup or an explicit user-authorized relinking process that preserves historical attribution.
- Backups must cover the protected key material and CSD database as a coordinated recovery unit. A database-only restore must not claim identity resolution is complete.

### Existing data and migration

The current mapping path can persist identity-bearing references in Observation v2. New identity work must not assume those historical payloads are already pseudonymized.

- New writes must use the privacy-safe host mapping before CSD append.
- Existing immutable events must not be edited in place or silently rehashed. Their historical actor/subject attribution remains as originally recorded, with an explicit legacy/unverified identity status.
- Legacy events must not be used to create canonical user bindings or accepted preference claims until a separately reviewed migration establishes provenance and retention handling.
- If a deployed database already contains raw platform identifiers, any sanitization requires a separately approved, auditable migration/rebuild and backup-retention plan. Do not claim that appending new pseudonymous events erases the old copies.
- The project must decide before deployment whether historical raw identifiers are retained under restricted local access, migrated to an encrypted restricted archive, or removed through a controlled rebuild. The choice must account for backups and exported logs as well as the active SQLite database.

### Additional acceptance tests

- Raw QQ account, sender, group/conversation and message identifiers never appear in durable Observation v2 payloads, projections, logs or model context.
- Two distinct senders in the same group produce distinct actor pseudonyms and canonical user subjects; group pseudonym is not accepted as a subject.
- Equal raw identifiers in different platforms, accounts or reference namespaces do not produce the same pseudonym.
- Plain SHA-256 or a model-supplied pseudonym cannot satisfy the host identity-binding contract.
- The same raw actor under the same authorized account scope resolves consistently with the same key version; ambiguous canonical encoding is rejected.
- Rotation creates versioned new bindings without changing the canonical subject; old events retain their historical key version.
- Missing/lost key makes bindings unresolved and blocks automatic subject reassignment; restored key plus database recovers the same mapping.
- A database-only restore is reported as identity-incomplete; no silent key regeneration or cross-account merge occurs.
- Existing raw-reference events remain marked legacy/unverified and are not silently treated as canonical identity evidence.

**Status:** static audit and design clarification only. The current QQ mapping demonstrably carries `sender_ref` into `actor_ref` and persists account/context/actor references through the CSD mapper; no tokenization, key provider, rotation workflow, migration or tests were implemented or executed. Stage 0 verification gate remains unchanged.
