# CSD Goal Activation — Design Proposal

> Status: **design proposal; not a frozen CSD/ASM specification**  
> Scope: the separate transition from a persisted candidate goal to an active goal  
> Depends on: `csd-goal-state-integration-proposal.md`

## 1. Purpose

The candidate-goal slice now persists hypotheses in CSD. The next distinct decision is whether the individual chooses to pursue one of those candidates.

Activation must not be inferred from:
- candidate creation;
- a user request;
- a scheduler wake-up;
- the existence of an activity option;
- an activity being started;
- a model's goal ranking or priority score.

The Life Engine must make an explicit choice. CSD must validate and persist that choice as a separate state transition.

## 2. Semantics

- `candidate`: CSD accepted a goal hypothesis as durable state. It is not currently a pursuit commitment.
- `active`: the individual explicitly chose to pursue the goal. This is a durable commitment to keep it under consideration and make progress when worthwhile and permitted.
- An active goal does **not** imply that an activity is running, that the system must act on every wake-up, or that a schedule exists.
- The individual may still wait, revise its approach, pause, or later abandon the goal through separate decisions.
- Activation is an internal cognitive-state transition, not an external side effect. It does not require ASM and grants no capability.

This preserves the architecture's distinction between a long-lived goal and a bounded activity.

## 3. Proposed Life Engine choice

Add `activate_goal` to the deliberation disposition set.

Validation rules:
- `goal_id` is required and must identify a goal in the trusted snapshot.
- The goal must currently be `candidate`.
- No activity ID or active-activity ID may be included in the same choice.
- Activation does not start an activity. A later deliberation may choose a bounded activity serving the now-active goal.
- Choosing `wait`, `decline`, or `no_op` leaves the candidate unchanged.

This keeps activation explicit and separate from action selection.

## 4. Proposed CSD event family

### 4.1 Proposal event

`life.goal_activation_proposed.v1`

Conceptual payload:
- `proposal_id` — stable idempotency identity;
- `based_on.state_version` — exact shared CSD state version used by deliberation;
- `goal_id` — candidate goal to activate;
- `expected_goal_version` — exact goal version visible in the snapshot;
- `rationale` — concise decision summary, not hidden chain-of-thought;
- `origin.component/version` — proposer metadata;
- `contract_version`.

The proposal does not assign a new goal version, status, decision ID, transition ID, or capability.

### 4.2 CSD decision event

`life.goal_activation_decided.v1`

CSD alone appends the decision event. It records:
- proposal and proposal-event identity;
- evaluated shared state version;
- exact target goal ID and expected goal version;
- policy ID/version;
- outcome: `accepted`, `rejected`, or `deferred`;
- accepted transition identity and the new goal version/status;
- reason code/summary.

An accepted activation creates the next goal version with status `active`. The update to `goal_versions`, `goals`, and the proposal decision projection is one SQLite transaction.

## 5. Validation and concurrency

CSD must verify:
1. the proposal event and its immutable identity;
2. the proposal's `based_on.state_version` equals the current shared state version;
3. the goal exists and is currently `candidate`;
4. `expected_goal_version` equals the current goal version;
5. the goal projection reconciles with the authoritative event history;
6. the proposal has not already received a decision.

A stale state version or changed goal version is deferred; it is never silently rebased. A goal that is already active or terminal is rejected for this candidate-activation operation.

An accepted activation increments the shared state version exactly once. Rejected/deferred decisions do not increment it. Decision identity is deterministic and proposal-scoped; identical retries return the existing decision, while conflicting proposal identity is rejected.

## 6. Source lineage and changing motivation

**Recommended rule:** activation does not require the original motivation signals to remain active.

The candidate already carries immutable, CSD-verified source signal versions. Those references explain how the goal originated; they are not a permanent requirement that the original signal remain active forever. A goal can remain worthwhile after an interest changes, a need resolves, or a question is answered in part.

Therefore:
- activation preserves the goal's original `origin_class` and `origin_signal_refs`;
- activation does not rewrite a user-requested goal as internally initiated;
- a new signal may influence deliberation, but it does not silently rewrite the goal's origin;
- if the individual no longer wants the goal, it may choose not to activate it or later abandon it through a separate transition.

This is consistent with the motivation/life-engine contract that an accepted ongoing goal may remain a legitimate source for activity even after its original interest signal is no longer active.

## 7. Projection and Recovery

- Add a rebuildable activation-proposal projection (or a deliberately generic lifecycle-proposal projection if later transitions justify it).
- Append the activation decision as a CSD-authoritative event.
- Append goal version (n+1) with status `active`; update the latest-goal projection in the same transaction.
- Projection reconciliation must replay candidate creation and activation in event order and verify each expected version/status transition.
- Recovery must never call the Life Engine, a model, or an activity executor. It reconstructs the active goal only from valid events.

## 8. Safety and autonomy boundaries

- Activation is not a permission grant.
- Activation does not create an activity, schedule, or automatic retry.
- A model's explanation is a concise rationale record, not proof of subjective desire.
- The goal's origin remains immutable even when the individual later chooses to pursue it independently.
- External actions remain out of scope and ASM-governed.

## 9. Initial acceptance tests

1. A candidate remains a candidate until an explicit `activate_goal` choice is proposed and accepted by CSD.
2. A valid activation changes exactly one candidate goal to active and increments state_version once.
3. The goal version increments exactly once; original origin and source signal-version references remain unchanged.
4. Activation does not start an activity or create a capability.
5. A non-candidate, unknown, or terminal goal cannot be activated by this operation.
6. A stale state version or goal version is deferred without rebasing.
7. Identical proposal retries are idempotent; conflicting identity is rejected.
8. Multiple activation proposals for the same candidate cannot both be accepted.
9. A goal can be activated after its original motivation signal becomes inactive, without rewriting the goal's origin.
10. Projection tampering is detected; Recovery reconstructs the active goal from the event history.
11. Recovery performs no model call or activity execution.

## 10. Explicit non-goals

- No automatic activation of every candidate.
- No activation priority score or forced goal choice on every wake-up.
- No pause/resume/abandon/revise/satisfy/supersede transitions in this slice.
- No activity creation or execution.
- No ASM integration.
- No claim that `active` proves subjective commitment or consciousness.

This proposal is a separate design step. It should be reviewed before implementation; it does not freeze the wider goal lifecycle or CSD/ASM specifications.

## 11. Implementation review clarifications (2026-11-15)

The proposal was reviewed against the current CSD schema-v3 event, projection, state-version, and Recovery implementation. The following implementation constraints are required:

1. **Separate event family and projection.** Use distinct `life.goal_activation_proposed.v1` and `life.goal_activation_decided.v1` events and a rebuildable `goal_activation_proposals` projection. Do not overload candidate-batch proposal/decision events or mutate the original candidate proposal.
2. **Schema migration.** Add a schema-v3→v4 migration that creates only the activation-proposal projection. Existing v1→v3 databases must migrate forward without rewriting event history or changing existing goal versions.
3. **Proposal identity.** The activation proposal ID is immutable and proposal-scoped. Identical proposal ID/content retries are idempotent; reusing the ID with different content is an identity conflict. Each proposal receives at most one decision, including rejected/deferred outcomes.
4. **State-version semantics.** Activation proposal events do not increment shared `state_version`. An accepted activation decision increments it exactly once. Rejected/deferred decisions do not. The authoritative state-version reader, replay validation, and recovery must count accepted activation decisions in event order.
5. **Evaluation order.** First compare `based_on.state_version` with the current version; stale proposals are deferred without rebasing. Then resolve the goal at the decision's event-history prefix. An unknown goal is rejected; a non-candidate goal is rejected; an expected goal-version mismatch is deferred. A candidate can be activated only once.
6. **Exact transition.** Acceptance creates exactly one next goal version (`expected_goal_version + 1`) with status `active`. The transition event records the exact previous version, resulting version, goal ID, activation proposal/event references, and a concise rationale. It must preserve the candidate's original `origin_class`, `origin_signal_refs`, original creation proposal lineage, success/stop/review conditions, and creation timestamp.
7. **Current projection semantics.** The latest `goals` row is updated atomically with the append-only `goal_versions` row and activation-proposal decision projection. The current goal's decision/transition references identify the activation transition; original candidate-creation references remain separately preserved.
8. **Historical reconciliation.** Goal projection reconciliation must replay candidate creation and activation decisions in sequence. It must validate every prior version/status, reject duplicate or skipped versions and contradictory transitions, and compare both latest-goal and full-version projections with the event-derived result. It must not validate activation against today's latest goal when replaying an earlier event.
9. **Recovery.** Recovery rebuilds activation proposals, goal versions, and latest goals solely from verified events. It must never call the Life Engine, a model, an activity executor, or ASM. Recovery must not turn a candidate active unless a valid accepted activation decision exists.
10. **No execution side effects.** Activation remains an internal cognitive-state transition. It creates no activity, schedule, permission, capability, retry, or external action. ASM is not part of this slice.
11. **Acceptance tests.** Cover schema migration; candidate-only until explicit proposal; accepted version/state-version increments; preservation of origin and source-signal versions even after source signals become inactive or evolve; unknown/non-candidate rejection; stale state and goal-version deferral without rebasing; duplicate and conflicting proposal identity; concurrent/duplicate activation attempts; projection tampering; deterministic Recovery; and proof that activation does not create or execute an activity.
12. **Life Engine contract.** Add an explicit `activate_goal` disposition requiring a candidate goal ID and the exact goal version in the trusted snapshot. It must reject activity IDs in the same choice. `wait`, `decline`, and `no_op` leave the candidate unchanged. The CSD-facing activation sink remains separate from the candidate-batch sink until its event contract is implemented.

These clarifications are an implementation review, not a frozen CSD/ASM specification. The goal lifecycle beyond candidate→active remains out of scope.



## 12. Additional implementation review constraint — proposal snapshot chronology

A proposal's `based_on.state_version` must not claim a state version that did not yet exist when the proposal event was appended. CSD rejects a future version at append time and verifies the same invariant during projection reconciliation/Recovery. A proposal may legitimately be stale because state changed between deliberation and append; it may be recorded, but evaluation must defer it rather than silently rebasing it. This prevents a proposal submitted before a goal or source signal existed from becoming valid retroactively merely because the global state version later catches up.
