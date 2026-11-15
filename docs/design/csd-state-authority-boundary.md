# CSD State Authority and Cognitive Proposal Boundary

> Status: **design proposal; not a frozen CSD specification**  
> Purpose: define who may report evidence, who may propose cognitive changes, and who may commit durable state transitions.  
> Related: [Persistent Individual Runtime Model](../architecture/individual-runtime-model.md), [CSD persistence proposal](csd-minimal-persistence-proposal.md), [Specification status](../specifications/status.md).

## 1. Problem this contract addresses

The project needs a single authoritative durable state, but cognition cannot be reduced to deterministic database reducers. Models and cognitive services are needed to interpret experiences, form candidate memories, revise beliefs, and deliberate about goals. At the same time, those services must not be able to silently overwrite the individual's history or current state.

This proposal separates three things:

1. **Evidence:** what a source reported or what the system observed.
2. **Cognitive proposal:** an interpretation or suggested state change based on evidence.
3. **Accepted state transition:** a durable change committed through CSD's authoritative path.

A proposal is not a fact. A stored event is not automatically a memory. A model response is not an authorized state mutation.

## 2. Authority model

| Actor | May submit evidence/events | May produce proposals | May commit authoritative state | May perform external side effects |
|---|---:|---:|---:|---:|
| Platform adapter | Yes, within its observation/action result contract | No authoritative cognitive decision | No | Only its narrow executor when authorized by ASM |
| Runtime/model | May report invocation metadata and outputs | Yes, as untrusted candidate output | No | No direct side effects |
| Perception/interpretation service | Yes, through typed event submission | Yes | No direct write | No |
| Memory/personality/affect/relationship service | Yes, through typed event submission | Yes | No direct write | No |
| Life engine | Yes, for internal deliberation/activity lifecycle | Yes, including goal/activity proposals | No direct write | No |
| ASM | Yes, for action lifecycle and verification evidence | May propose action-state transitions within ASM rules | Owns ASM action state; does not own cognitive identity | Coordinates governed dispatch |
| CSD state authority | Accepts and validates submitted events/proposals | May request missing evidence or reject invalid proposals | **Yes, for durable cognitive state** | **No** |

This table describes logical authority. It does not require separate operating-system processes. Access control should enforce the same boundaries even if modules initially share a process.

## 3. Four record classes

### 3.1 Evidence event

An evidence event records that something was observed, reported, or occurred according to a named source.

Examples:
- platform.bilibili.video_observed.v1
- conversation.message_received.v1
- media.audio_transcription_completed.v1
- action.like_result_observed.v1
- runtime.session_started.v1

An evidence event must preserve source identity and the distinction between direct observation and the source's own claim. For external content, retain a reference to the original artifact where feasible, plus timestamp, extraction method, and coverage metadata.

Evidence events are not automatically true descriptions of the world. For example, a platform adapter can report "the API returned success"; it cannot upgrade that into "the creator definitely received and saw the like."

### 3.2 Cognitive proposal

A cognitive proposal suggests an interpretation or possible state update. Examples:
- candidate autobiographical memory;
- candidate semantic knowledge;
- possible preference or aversion;
- affect/drive estimate;
- relationship interpretation;
- self-belief revision;
- candidate interest or goal;
- diary-writing inclination.

A proposal should include:
- stable proposal_id;
- proposal type and schema version;
- references to the evidence and prior state used;
- originating service and version;
- confidence or uncertainty representation appropriate to the type;
- time/context scope;
- proposed operation (create, revise, relate, supersede, withdraw);
- expiry/review condition where the proposal is time-sensitive.

A proposal must not contain executable instructions or privileged capabilities. Text extracted from a webpage, video, comment, or message remains untrusted evidence even if a model repeats it in a proposal.

### 3.3 State-transition decision

The CSD authority path evaluates whether a proposal is valid and eligible to become durable state. The decision should record:
- proposal reference;
- accepted, rejected, deferred, or needs-more-evidence outcome;
- rule/validator version;
- supporting and conflicting evidence references;
- reason summary suitable for audit;
- decision time and correlation context.

CSD may request bounded analysis from cognitive services, but the final evaluation and acceptance decision remains with CSD. A delegated service returns evidence/analysis, not an authoritative verdict. CSD must not equate a high model confidence score with truth or acceptance.

A rejection or deferral is itself useful history when it affects future processing. It must not erase the original proposal or evidence.

### 3.4 Accepted state transition

An accepted transition is committed atomically with the event/provenance records needed to explain it. It updates the authoritative projection and produces a durable history of what changed.

A transition may:
- create a new state item;
- revise an existing item while retaining its previous version;
- add or remove a relation;
- change lifecycle status;
- mark an item uncertain or disputed;
- record that a previous interpretation was withdrawn or superseded.

Do not implement revision as an in-place destructive overwrite when the previous interpretation is relevant to the individual's history.

## 4. Proposed submission and read interfaces

These are conceptual interfaces for review, not final API signatures.

### 4.1 submit_event(event)

Purpose: submit source evidence or a lifecycle event.

Expected behavior:
- validate the event envelope and schema;
- verify referenced payload availability and integrity;
- enforce event-ID idempotency;
- append the immutable event;
- update only deterministic projections that are safe to derive from the event;
- return accepted, duplicate, conflict, or rejected status.

An event may be accepted without changing memory, personality, affect, or goals. Semantic interpretation happens outside the storage transaction.

### 4.2 Cognitive proposals within the existing event contract

CSD v0.1 already defines Event Submit as the write interface. This proposal does not establish a separate mandatory public proposal API.

A cognitive proposal can be represented as a typed event submitted through Event Submit, for example a versioned event whose payload contains:
- stable proposal identity;
- proposal type and schema version;
- references to supporting evidence and prior state;
- originating service/version;
- uncertainty/confidence metadata;
- proposed operation and any review/expiry condition.

Submitting the proposal persists a candidate; it does not accept the proposed state change. Repeated submission with the same identity and immutable content is idempotent. The same identity with different immutable content is a conflict.

A future convenience wrapper named submit_proposal may be added, but it must preserve the Event Submit semantics and must not become a second authority path.

### 4.3 CSD-owned proposal evaluation

Proposal evaluation belongs to CSD's authoritative state-evaluation path. A cognitive service or model may provide analysis when requested, but it cannot make the final acceptance decision or commit the state transition.

CSD evaluates a persisted proposal against current authoritative state and applicable policies:
- load the current state and referenced evidence;
- detect stale assumptions or superseded state;
- apply type-specific invariants and permission constraints;
- record accepted, rejected, deferred, or needs-more-evidence;
- if accepted, commit the state transition and its decision record atomically;
- never perform an external side effect.

This may be implemented as an internal CSD operation rather than a separately exposed API. Evaluation must be safe to repeat. If relevant state changed since proposal creation, CSD must reevaluate, defer, or reject rather than apply stale assumptions.

### 4.4 Read interfaces

Read APIs should return state together with relevant provenance and lifecycle information, not just flattened text.

Conceptual reads:
- get_state_snapshot()
- get_memory(query, scope, time_context)
- get_self_model()
- get_affect_and_drives()
- get_relationship(entity_id)
- get_goals(filters)
- get_proposal(proposal_id)
- get_event(event_id)

Read operations must not mutate authoritative state as a side effect. Retrieval may update separate operational metrics, but those metrics must not silently alter autobiographical memory or personality.

## 5. Transaction and execution boundary

CSD transactions should contain only local durable operations:

1. validate the request and referenced records;
2. establish idempotency and concurrency conditions;
3. append event/proposal/decision records as applicable;
4. apply deterministic state transition logic;
5. update projections and sequence offsets;
6. commit atomically.

Do not call an LLM, platform API, shell command, filesystem action executor, or ASM dispatcher while holding a CSD database transaction.

If a semantic model call is needed:
1. read a consistent state/evidence snapshot;
2. perform the model call outside the write transaction;
3. package its output as a proposal with provenance;
4. submit and evaluate the proposal against the latest state;
5. reject or reevaluate if its assumptions became stale.

CSD recovery may rebuild projections and accepted state from durable records. It must never execute proposals, re-run model calls, or dispatch external actions as a recovery side effect.

## 6. State-family invariants

The following are proposed invariants to guide later schemas and tests. They are not a substitute for domain-specific specifications.

### Evidence and event history
- Original source and observation time remain distinguishable from CSD receipt time.
- Corrections are appended as new records linked to the original; accepted evidence is not silently rewritten.
- A source's claim is not automatically promoted to an objective fact.

### Memories
- A candidate memory is distinguishable from an accepted/retained memory.
- Each accepted memory has links to supporting experience/evidence and an uncertainty representation.
- Consolidation may create a new synthesis but must preserve source episodes and provenance.
- Forgetting/accessibility policy must not silently falsify the historical event log.

### Self-model and personality
- Stable traits, values, preferences, self-beliefs, and context-specific expression are distinct types.
- A single isolated action or model inference is insufficient by itself to establish a durable trait.
- A change retains the prior value or version and its supporting evidence.
- Conflicting evidence can leave a self-belief uncertain rather than forcing an artificial single answer.

### Affect and drives
- Dynamic state has a time/context scope and is not automatically permanent personality.
- Estimates preserve uncertainty and originating evidence.
- Expiration or decay changes current availability, not the fact that an earlier state was recorded.

### Goals and commitments
- A candidate goal is not an accepted active goal.
- A goal is not a commitment unless the individual explicitly accepts the obligation.
- Goal state changes retain reasons and prior lifecycle history.
- Pausing, revising, abandoning, and choosing not to pursue are valid outcomes, not necessarily failures.

### Diary
- A writing inclination is a proposal/activity candidate, not an obligation.
- Draft, saved entry, discarded draft, and published text are distinct states.
- Saving or publishing a diary entry is a separate decision from generating text.
- Diary content is not automatically converted into objective memory or personality state; any such interpretation requires a separate proposal and evidence path.

### External actions
- Action intent, dispatch attempt, platform evidence, and verified outcome are distinct.
- CSD may store references/summaries of ASM state but cannot authorize or dispatch an action by changing a cognitive projection.
- Recovery never retries an uncertain side effect.

## 7. Concurrency and stale proposals

A proposal may be based on state that has changed before it is evaluated. Each proposal should therefore identify the relevant state version or event offset used during generation.

At evaluation time:
- if referenced state is still current, validate normally;
- if unrelated state changed, evaluation may continue;
- if a relevant state item changed, reevaluate against current state;
- if the evidence was withdrawn or superseded, defer or reject as appropriate;
- if the proposal conflicts with a newer accepted transition, preserve the conflict and require a resolution path rather than overwriting the newer state.

The exact concurrency token (global event offset, per-aggregate version, or both) remains to be selected. A global lock is not a substitute for detecting stale semantic assumptions.

## 8. Event and proposal identity

Use separate stable identities for:
- source event (event_id);
- cognitive proposal (proposal_id);
- accepted state transition (transition_id);
- aggregate/entity being changed (aggregate_id or domain-specific identity).

Do not reuse one ID to mean all four things. Correlation IDs group related work but are not idempotency keys.

Retries of the same submission preserve the same event/proposal identity and immutable content. A genuinely new observation or a newly reasoned proposal receives a new identity, even if its text resembles an earlier one.

## 8.1 Proposal snapshot chronology

Every proposal family that carries `based_on.state_version` must prove that the claimed version existed immediately before the proposal event's authoritative sequence. CSD rejects a future version at append time; it may retain an older/stale version so evaluation can defer it without rebasing. Recovery enforces the same rule while replaying the event stream. This applies across memory, grounded memory, motivation, and goal proposals.

## 9. Failure behavior

| Failure | Required behavior |
|---|---|
| Duplicate event/proposal, same immutable content | Return the original accepted/persisted result; do not apply twice |
| Same identity, different immutable content | Explicit conflict; preserve original |
| Invalid schema or missing payload reference | Reject without partial durable mutation |
| Model timeout during proposal generation | No state change; retry or abandon the computation independently |
| Proposal validator failure | Preserve proposal and record failure/defer status as appropriate; do not partially update state |
| Database failure before commit | Roll back the entire transaction |
| Process exits after commit but before response | Caller retries with same identity; CSD returns duplicate/original result |
| Stale proposal | Reevaluate, defer, or reject; do not blindly apply |
| Corrupt event/proposal/transition history | Stop and preserve evidence; do not invent or silently discard state |
| Recovery | Rebuild local state only; no model invocation or external action |

## 10. Open questions requiring separate decisions

- Should proposal evaluation be performed by a CSD-owned orchestrator or by typed domain evaluators invoked under CSD authority?
- Which proposal types require model-based semantic review versus deterministic validation?
- What is the minimal provenance schema for each state family?
- How should privacy scopes, encryption, retention, and deletion interact with append-only provenance?
- Should state versions be global, per aggregate, or both?
- How should low-confidence or conflicting proposals be surfaced for later reconsideration?
- Which parts of state are allowed to expire, decay, or become inaccessible, and under what policy?
- How should a user correction be represented without treating the user's assertion as automatically authoritative for every domain?

These questions must be resolved before claiming a complete cognitive-state contract. This proposal intentionally does not settle them.

## 11. Recommended next step

Review this authority boundary against the existing CSD v0.1 discussion and the persistence spike. Then define a small typed event/proposal schema for one safe domain (for example, a read-only observation and a candidate memory) before adding production cognitive behavior. Keep all model and platform calls outside CSD transactions and preserve the ability to choose no action.
