# Motivation Signal CSD Integration Contract — Design Proposal

> Status: **integration design proposal; not a frozen CSD specification**  
> Purpose: connect evidence-grounded motivation updates to CSD's existing event authority without creating a second independent state store.

## 1. Scope and non-goals

The Life Engine can consume motivation signals and propose goal/activity choices. The new `core/life_engine/motivation.py` module validates proposed updates against a trusted snapshot. Neither component can currently create durable motivation state.

This contract defines the next boundary:
1. trusted experience/interaction events preserve what actually happened and why;
2. a replaceable synthesizer proposes a signal hypothesis or update;
3. CSD verifies provenance and decides whether the proposal changes authoritative state;
4. Life Engine reads only CSD-accepted signal projections.

This design does not implement a real model provider, a production signal reducer, or subjective desire. It does not change the existing CSD v0.1 working contract.

## 2. Why current observation records are insufficient

The current cognitive slice's `experience.observation_recorded.v1` fixture records content, source reference, timestamp, and a broad modality/coverage field. It does not establish:
- whether the content was requested by the user;
- whether a platform pushed or autoplayed it;
- whether the individual independently selected it;
- which meaningful alternatives were actually available;
- whether an interaction was merely exposed, started, completed, or revisited.

Therefore, an observation event alone must never be treated as proof of voluntary interest.

Do not silently add model-controlled origin fields to the existing v1 observation payload. A future interaction event needs its own versioned schema.

## 3. Trusted interaction provenance

Proposed event family:

`experience.interaction_choice_recorded.v1`

Conceptual fields:
- `interaction_event_id` and `encounter_id`;
- `subject_ref` and source content/experience event references;
- `interaction_kind` (exposure, selection, playback start, return visit, completion, interruption, etc.);
- `trigger_class` derived from the actual interaction path (user request, platform recommendation, platform autoplay, independent Life Engine choice, accepted self-commitment);
- `user_request_event_id`, `recommendation_event_id`, or accepted Life Engine decision reference when relevant;
- `choice_set_ref` or an immutable list of actually available alternatives for a voluntary selection;
- `selected_item_ref`, when a selection occurred;
- occurrence time, adapter identity/version, account/session scope, and correlation/causation references.

These are conceptual fields, not a frozen schema. The adapter must record facts it directly observed. It must not infer a long-term interest, emotion, personality, or goal.

### 3.1 Deriving evidence kinds

CSD should derive the usable evidence kind and origin class from the immutable interaction lineage:

| Interaction lineage | Possible evidence classification | Can it support autonomous-interest evidence? |
|---|---|---|
| User explicitly requested the item/action | user_requested_action / user_request | No; preserves encounter history only |
| Platform autoplayed or pushed an item without a fresh choice | platform_autoplay / platform_recommendation | No |
| Item was merely visible/exposed | passive_exposure / source-derived origin | No, not as voluntary choice |
| Individual selected an item from a verified, meaningful choice set without a user request or platform auto-trigger | voluntary_selection / internal_state | Potentially, as one uncertain evidence point |
| Individual independently returns to a previously encountered item | return_visit / internal_state | Potentially, as one uncertain evidence point |
| Individual creates a question without a user prompt and records it as such | autonomous_question / internal_state | May support a curiosity hypothesis |
| A user request is explicitly accepted as an obligation | commitment_accepted / user_request plus a separate acceptance decision | Supports a user-originated commitment, not an internally invented interest |
| Individual accepts its own commitment | commitment_accepted / self_commitment | Supports commitment provenance, not interest evidence by itself |

A `voluntary_selection` record must be traceable to a real selection and the choice set available at that time. A boolean supplied by a model saying "meaningful alternatives existed" is insufficient.

The first prototype uses a conservative minimum check of two distinct encounter IDs and two distinct timezone-aware occurrence instants (normalized to UTC before comparison) before returning `emerging_interest_supported`. Different ISO-8601 offset spellings of the same instant do not count as separate encounters. This is an implementation guard against a one-off click, not a universal maturity threshold or normative CSD rule. The actual maturity policy remains versioned, reviewable, and subject to later evidence-quality evaluation. CSD—not the provider—must assign the durable maturity state.

### 3.2 Trust boundary

The origin, event kind, choice-set contents, timestamp, and adapter/account attribution must be created or verified by a trusted adapter/CSD path. They must not be copied from model-written summaries.

A Python component name or `source` string is not authentication. Before platform data can influence durable motivation state:
- adapter identity must be authenticated at a process/IPC boundary;
- account/session scope must be explicit;
- platform input must be treated as untrusted content, never as tool permission;
- the event must reference the actual interaction/choice-set evidence;
- fabricated, missing, or unverifiable provenance must fail closed.

The current in-process prototype cannot provide this security boundary.

## 4. Motivation update proposal

Proposed event:

`motivation.signal_update_proposed.v1`

The replaceable motivation synthesizer may propose:
- operation: create, reinforce, weaken, contextualize, pause, or resolve;
- signal kind: interest, need, curiosity, commitment, or affect;
- subject reference;
- a concise signal statement/hypothesis;
- scope/context;
- supporting and counterevidence event IDs;
- target signal ID/version for updates;
- rationale summary;
- based-on CSD state version;
- synthesizer identity/version and proposal-contract version.

The proposal must not contain authoritative:
- signal origin class;
- accepted/rejected decision;
- resulting signal version;
- maturity stage;
- activation/status;
- CSD state version after commit;
- memory/transition IDs generated by CSD;
- capabilities, account permissions, or action payloads.

The model's wording remains a hypothesis. CSD must preserve the exact accepted statement/version and evidence references; a later correction creates a successor revision rather than overwriting history.

## 5. CSD decision and projection

Proposed internal event:

`motivation.signal_update_decided.v1`

Only CSD's authoritative path may append this event. It binds:
- proposal event ID and digest;
- target signal identity/version, if any;
- supporting/counterevidence event references;
- derived origin class;
- the policy/version used;
- decision outcome and reason code;
- resulting signal ID/version and immutable statement/scope;
- successor/predecessor relation when contextualized or superseded;
- the CSD state version evaluated and resulting state version.

CSD must independently repeat every validation. The Life Engine's local validator is not trusted authority.

### 5.1 Signal lifecycle and version rules

Proposed domain lifecycle:
- active;
- paused;
- resolved;
- superseded (with an explicit successor relation).

A newly accepted signal begins at version 1. Each accepted update creates the next version. A rejected/deferred proposal does not mutate the signal. A stale target version is deferred or rejected, never silently applied to the latest version.

A `reinforce` operation adds new supporting evidence while preserving the signal statement and scope. A `weaken` operation adds new counterevidence while preserving them. A `contextualize` operation may create a revised statement/scope version with an explicit relation to the previous version. A `pause` operation may be an intentional CSD decision without new evidence; it does not erase the signal. A `resolve` operation requires explicit resolution evidence.

Interest maturity is a derived policy output, not a field that a provider can assign. A proposal may ask for a review of a tentative/emerging/context-specific interpretation, but CSD must derive the accepted stage from evidence quality, source lineage, time/context diversity, and counterevidence.

### 5.2 CSD state version

The initial origin classification is immutable history: if a signal first arose from a user request, later independent choices must not rewrite that origin. A separate CSD-derived voluntary-encounter summary can accumulate across accepted signal versions. The snapshot should retain unique encounter IDs, representative timestamps, and the supporting event ID for each independently verified voluntary choice. Later interest-maturity evaluation considers the cumulative verified history, not only the newest proposal. This allows an initially user-requested topic to develop a separately evidenced autonomous interest without pretending that the first encounter was self-initiated.\n\nThe global CSD `state_version` represents authoritative state transitions, not every event in the log.

- Observation and interaction events append evidence but do not automatically mutate motivation state.
- Pending signal proposals do not increment state_version.
- Accepted signal create/update/pause/resolve decisions increment state_version atomically with the projection update.
- Rejected/deferred proposals do not increment it unless another explicitly defined authoritative state changes.
- A proposal generated from an old version cannot overwrite newer signal state.

The precise global-version definition still needs reconciliation with the full CSD v0.1 source before it is frozen.

## 6. Event store, transactions, and Recovery

Motivation events must use the same authoritative CSD event history and Recovery boundary as memory, goals, and other long-term state. Do not create a separate motivation SQLite database.

The current repository has both a generic persistence spike and an isolated cognitive-memory SQLite schema. Neither is yet a final production topology. Before integrating motivation:
- choose one authoritative CSD database and event stream;
- define an explicit schema migration from the prototypes;
- ensure event/payload/decision/projection writes are atomic;
- preserve content-addressed payload identity and event idempotency;
- keep signal projections rebuildable from events;
- run Recovery without invoking a synthesizer or recalculating a semantic judgment;
- stop safely on corrupted provenance, unknown schema versions, or inconsistent projection state.

A recovery pass reconstructs the same signal history and current versions. It must not generate a fresh interest, repeat a goal deliberation, or launch a platform activity.

## 7. Signal snapshot supplied to Life Engine

The CSD Goal/Motivation Retrieval path should expose only accepted signal state, not pending proposals.

A snapshot may include:
- signal ID/version, kind, statement, subject and scope;
- immutable initial origin classification and CSD-derived cumulative voluntary-encounter references;
- current lifecycle state and CSD-derived maturity;
- origin class and provenance references;
- supporting and counterevidence references;
- activation/salience assessment, if separately defined;
- related accepted goals/commitments;
- state_version.

The snapshot must retain uncertainty and context. It must not collapse unlike signals into a universal numerical priority. Salience/activation is not truth, importance, or permission.

## 8. Privacy and diary boundary

- A private diary entry is not automatically a motivation signal or general memory.
- If a diary entry later supports an interest or curiosity hypothesis, the signal proposal must reference the diary artifact under its access scope.
- Ordinary Life Engine deliberation must not receive private diary text unless the relevant operation is authorized.
- A motivation update must not widen the source artifact's privacy scope.
- The current append-only plaintext event prototypes cannot claim secure content erasure; diary integration remains blocked until a real retention/erasure architecture exists.

## 9. Proposed test gates

1. User-requested actions cannot be reclassified as voluntary selections.
2. Platform autoplay/recommendation cannot be reclassified as internal choice.
3. A voluntary selection must reference a valid choice set and selected item.
4. A single encounter cannot satisfy the emerging-interest guard.
5. Reusing the same evidence on a later signal version is rejected.
6. A signal statement is required on creation and remains stable during reinforcement/weakening/pause/resolution.
7. Only contextualize may revise statement/scope, with predecessor linkage.
8. Target signal version mismatch is rejected/deferred.
9. Counterevidence cannot be stored as supporting evidence.
10. Unknown, stale, or subject-mismatched evidence is rejected/deferred.
11. CSD-derived maturity cannot be set by the provider.
12. An update that changes accepted signal state increments state_version exactly once.
13. Rejected/deferred update does not mutate the signal projection.
14. Recovery reconstructs all signal versions and relations without calling the provider.
15. A crash between decision event and projection cannot produce partial acceptance.
16. Duplicate event replay is idempotent; changed-content identity reuse conflicts.
17. A private diary artifact cannot enter a public/general signal without an authorized scope reference.
18. Goal deliberation reads only CSD-accepted signal versions.

These are proposed engineering tests, not frozen CSD conformance clauses.

## 10. Implementation readiness

Do not connect a real motivation synthesizer to an authoritative acceptance path until:
- the trusted interaction event schema is implemented;
- adapter event origin/choice-set provenance is authenticated;
- the single CSD event-store topology and migration are decided;
- the signal decision reducer, projections, idempotency, and Recovery are implemented;
- Windows/Python target tests and failure-interruption tests pass;
- the CSD v0.1 source clauses are reconciled rather than inferred from this proposal.

The present validator is only a pure proposal pre-check. It is not a CSD store, motivation learner, or autonomous preference system.
