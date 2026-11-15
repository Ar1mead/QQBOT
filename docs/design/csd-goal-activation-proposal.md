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
