# Life-Engine to CSD Event Contract — Design Proposal

> Status: **proposed integration contract; not a frozen CSD specification**  
> Depends on: [Motivation, Goals, and Intentions Contract](motivation-and-life-engine-contract.md), [CSD State Authority Boundary](csd-state-authority-boundary.md), and [ASM-5.3 confirmed semantic baseline](../specifications/status.md#asm-53).

## 1. Purpose

The initial Life Engine reference package can read a snapshot, produce a typed deliberation proposal, validate its references, and hand the result to a sink interface. It does not yet persist goals, motivation state, or activity choices.

This document defines the missing authority boundary before a CSD adapter or database schema is implemented. Its purpose is to prevent the Life Engine from becoming a second state store.

CSD remains the sole authority for durable long-term cognitive state. The Life Engine is a replaceable deliberation component.

## 2. Proposed event families

Event names and payload details are proposals, not frozen identifiers.

### 2.1 Deliberation proposal

Candidate event:

`life.deliberation_proposed.v1`

The proposal should bind:
- unique proposal and event IDs;
- occurred/received timestamps and correlation ID;
- deliberator component, model/provider, and contract versions;
- `based_on_state_version`;
- proposed goal candidates and their signal-origin references;
- one choice disposition (including `no_op`);
- considered activity-option IDs;
- concise rationale and evidence references;
- no model-asserted permissions, CSD decisions, action IDs, transition IDs, or execution results.

This event is untrusted candidate data. Submitting it does not create an active goal or start an activity.

### 2.2 CSD decision

Candidate event:

`life.deliberation_decided.v1`

Only the internal CSD authority path may create this event. It binds the exact proposal event and digest, the state version evaluated, policy version, decision outcome, and any accepted state transitions.

The decision path must distinguish:
- accepting a goal as a new active/paused/blocked state;
- rejecting or deferring a goal candidate;
- accepting a pause, revision, or abandonment transition;
- recording a valid wait/decline/no-op choice;
- authorizing the next internal activity transition;
- identifying a side-effecting action request that must be handed to ASM rather than dispatched by CSD or Life Engine.

A model or provider must never supply the authoritative decision outcome, accepted state version, or generated transition identities.

### 2.3 Activity lifecycle observations

Candidate event families:
- `life.activity_started.v1`
- `life.activity_progress_observed.v1`
- `life.activity_stopped.v1`
- `life.activity_outcome_observed.v1`

These record what actually happened, not what was planned. A runtime or adapter may report an observation, but CSD validates it as evidence. For external side effects, ASM owns attempt creation, dispatch, verification, retry, and recovery; the Life Engine activity record references the ASM business-action identity and observed outcome without duplicating action authority.

## 3. State-version semantics

`state_version` should represent authoritative cognitive-state mutations, not every event in the append-only history.

- An observation, pending proposal, or no-op decision may append an event without incrementing the state version.
- Accepting a new goal or changing an accepted goal state increments the version atomically with its decision/projection update.
- Rejected or deferred proposals do not increment the version unless a separately specified durable state actually changes.
- A no-op is retained as a decision record but does not create an artificial state mutation.
- A proposal based on a stale version must be deferred or re-deliberated; it must not overwrite newer state.

The precise state-version increment policy must be finalized when the CSD transition reducer is designed.

## 4. Goal projection and lifecycle

Only CSD-accepted goals appear in the authoritative goal snapshot. Candidate goals remain pending and do not become eligible activity targets until accepted.

A goal projection should retain:
- goal ID and version;
- desired condition;
- original origin classification derived from referenced motivation signals;
- supporting and contradicting event references;
- success, stop, and review conditions;
- current lifecycle state;
- predecessor/successor and related-goal references;
- decision event, policy version, and transition identity.

CSD must recompute origin classification from immutable signal history. It must not trust a `self_initiated=true` field supplied by a model.

A goal that was originally user-requested remains marked as user-requested if it later becomes a commitment. A later self-generated decision to continue or reinterpret it may be recorded separately, but must not rewrite its origin history.

## 5. Motivation signal ownership

The initial Life Engine code only consumes motivation signals from a snapshot. It does not learn or update drives/interests.

Before implementing signal updates, define a separate typed contract for:
- signal hypothesis creation;
- evidence supporting and contradicting the hypothesis;
- reinforcement, weakening, contextualization, and resolution;
- signal provenance and uncertainty;
- time/context validity;
- distinction between user-requested behavior and voluntary choice.

Do not accept raw click counts as direct preference truth. Do not let every model output create a new drive. A signal proposal must cite events and a versioned evaluation policy. CSD controls whether it enters the authoritative signal projection.

## 6. Trusted activity options and capability checks

Activity options in a Life Snapshot must be assembled from trusted current state and capability policy, not generated freely by the deliberation model.

CSD (or a trusted capability broker) supplies:
- option ID and kind;
- origin signal and goal references;
- prerequisites and current availability;
- capability required;
- current permission decision and its policy/provenance;
- side-effect classification;
- resource envelope and stop conditions.

The deliberator can select only a known option ID. It cannot add an option, claim a permission grant, alter prerequisites, or lower its side-effect level. A normal activity option may advance only an active goal. Active activities also need a trusted current-state record: continuation is blocked when permission was revoked or the stop condition has been met; missing active-state metadata fails closed. Stopping remains possible, but an external side-effect stop/continue must be governed by ASM.

The local `validate_life_proposal` function is only a defensive input check. CSD must repeat authoritative validation when the proposal is submitted because the process may be stale, buggy, or compromised.

## 7. Activity selection and ASM

A selected activity is not equivalent to permission to execute it.

- Internal/no-side-effect activities may be started only under the accepted Life Engine/CSD transition rules.
- Read-only platform activities require the specific read capability and current account/session availability.
- Any activity with an external side effect must be converted to an ASM-governed action request.
- Life Engine must never call a side-effecting adapter directly.
- CSD recovery must not dispatch or replay an activity.
- ASM's own retry and verification semantics remain governed by its tracked specification status.

The first Bilibili integration remains read-only. Likes, favorites, comments, follows, QQ messages, and publishing are separate side-effecting capabilities.

## 8. No-op and decision history

`no_op`, `wait`, `decline`, and `request_information` are valid deliberation outcomes.

CSD should preserve the outcome and compact rationale so later reflection can distinguish:
- nothing was salient;
- an option existed but was not worthwhile;
- a capability or prerequisite was unavailable;
- the system intentionally waited;
- the system declined;
- more information was needed.

These are not failed scheduled tasks. A no-op must not trigger retries or manufacture a goal. It should not increment state_version unless a separately specified state mutation occurs.

Do not store hidden chain-of-thought. Record a concise reason summary, alternatives considered, relevant evidence, and outcome.

## 9. Diary activity

A self-initiated diary entry is an internal activity candidate that may appear only when the current state supports a genuine writing inclination or another explicitly grounded reason.

- A timer or wake event alone cannot create a diary activity.
- A no-op is valid when no writing inclination exists.
- A draft may be discarded without becoming an event or general memory.
- A saved diary artifact is stored under its own privacy/retention boundary.
- Extracting a memory from a diary requires a separate proposal and explicit scope validation.
- Diary text must not be added to ordinary model context unless the active task is authorized to read it.

The current Life Engine prototype does not implement diary storage, privacy enforcement, or self-generated writing motivation.

## 10. Atomicity, idempotency, and recovery

The eventual CSD integration must guarantee:
- proposal event and pending proposal projection are committed atomically;
- decision event and all authoritative state projections for that transition are committed atomically;
- duplicate event IDs with identical immutable content are idempotent;
- identity reuse with changed immutable content conflicts;
- stale proposals cannot update newer state;
- recovery reconstructs goals, motivation signals, decisions, and activity records from durable events;
- recovery never calls a deliberator, re-evaluates a proposal, or executes an action;
- incomplete or inconsistent projections fail closed and require Recovery.

Migration from the existing cognitive-memory prototype must be designed explicitly. The first Life Engine adapter must not create a second SQLite file as an independent authority.

## 11. Required integration tests

1. Pending goal proposals do not appear in the active-goal snapshot.
2. CSD derives goal origin from immutable signal references.
3. A user-requested activity cannot be relabeled as internally initiated.
4. A running activity cannot continue after its permission is revoked or its stop condition is met.
5. A side-effecting continue/stop request is handed to ASM and is never directly dispatched by Life Engine.
4. A stale deliberation proposal cannot mutate current state.
5. Identical event replay does not duplicate goals or choices.
6. Changed-content ID reuse conflicts.
7. A no-op is durably recorded without creating a goal or artificial state-version increment.
8. A permission change between snapshot and submission invalidates the selected activity.
9. A model cannot invent an activity option or capability.
10. Side-effecting choices create an ASM handoff request but no direct dispatch.
11. A failed/unknown ASM action remains uncertain during Life Engine recovery.
12. Recovery reconstructs goal and activity state without invoking the model.
13. A stopped or abandoned goal cannot silently resume from a timer.
14. A diary draft discarded by the individual does not become general memory.
15. A saved diary artifact retains private scope and is not retrieved by ordinary memory search.

## 12. Integration readiness

Do not connect a real deliberation model or platform adapter until:
- the current motivation/goal/activity contracts are reviewed;
- CSD event schemas and state-version rules are implemented and tested;
- a trusted snapshot reader and CSD proposal sink exist;
- CSD independently validates all references and capabilities;
- ASM handoff semantics are proven for every external side-effect class;
- Recovery and Windows-local tests pass.

This document is an integration design, not evidence of a connected or autonomous life system.
