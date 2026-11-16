# CSD Goal Lifecycle — Design Proposal

> Status: **engineering proposal; not a frozen CSD/ASM specification**  
> Scope: lifecycle transitions after candidate creation and explicit activation  
> Depends on: `csd-goal-state-integration-proposal.md` and `csd-goal-activation-proposal.md`

## 1. Purpose

CSD currently persists candidate goals and a separate explicit candidate→active transition. The remaining lifecycle must preserve the distinction between:
- a durable goal hypothesis (`candidate`);
- a goal the individual chose to pursue (`active`);
- a goal temporarily not pursued by choice (`paused`);
- a goal whose progress is prevented by an evidenced external prerequisite (`blocked`);
- a goal whose success condition was accepted as met (`satisfied`);
- a goal intentionally discontinued (`abandoned`);
- a goal replaced by an explicit successor (`superseded`).

These statuses are not interchangeable. In particular, `paused` is a voluntary choice; `blocked` is a constraint; and terminal statuses must not be silently reopened.

No lifecycle transition may start an activity, grant a capability, schedule work, or dispatch an external action.

## 2. Proposed transition graph

| Current status | Proposed transition | New status | Notes |
|---|---|---|---|
| candidate | activate | active | Implemented in the separate activation event family |
| active | pause | paused | Explicit internal choice |
| paused | resume | active | Explicit internal choice |
| active | mark blocked | blocked | Requires trusted blocker evidence; not a model-only assertion |
| blocked | clear blocker | active | Requires evidence that the blocker is resolved |
| active / paused / blocked | satisfy | satisfied | Requires success-condition evidence and an accepted decision |
| active / paused / blocked | abandon | abandoned | Explicit decision; terminal |
| active / paused / blocked | supersede | superseded | Must identify an existing successor goal; atomic relation |
| candidate / active / paused / blocked | revise | same status, next version | Only when the goal identity/intent remains continuous |

The graph is intentionally conservative:
- Candidate goals remain candidates until explicit activation. A candidate is not paused because it was never active.
- `satisfied`, `abandoned`, and `superseded` are terminal in the first lifecycle version.
- Terminal goals are never silently reopened. A renewed pursuit requires a new candidate goal with explicit lineage.
- A materially different intent should be a new goal, not an in-place revision. The old goal may then be superseded by the new one.
- A candidate-dismissal operation is not yet specified. Do not overload `abandoned` until the distinction between an unchosen hypothesis and a discontinued commitment is resolved.

## 3. Transition semantics

### 3.1 Pause and resume

Pause means the individual chooses not to pursue an active goal for now, while retaining it and its history. It does not mean the goal is blocked, completed, or abandoned.

Resume means the individual explicitly chooses to pursue a paused goal again. It does not automatically resume any activity or create a schedule.

Initial implementation slice:
- `active → paused` via an explicit `pause_goal` proposal;
- `paused → active` via an explicit `resume_goal` proposal;
- both require the exact current `expected_goal_version`;
- each accepted transition creates goal version n+1 and increments shared CSD `state_version` exactly once;
- rejected/deferred proposals create no goal version and do not increment state version;
- stale state/goal versions are deferred, never rebased.

Implementation note for the first slice (hosted-tested): the event family is `life.goal_pause_resume_proposed.v1` / `life.goal_pause_resume_decided.v1`, with the rebuildable `goal_pause_resume_proposals` projection in schema v5. Its operation field is restricted to `pause` or `resume`; CSD does not accept a generic requested target status. Proposal chronology rejects a future claimed state version, and stale proposals are deferred without rebasing.

### 3.2 Blocked and unblocked

Blocked is not a synonym for pause. It records that a specific prerequisite or external constraint currently prevents progress.

A deliberator must not be able to mark a goal blocked merely because no activity option was returned. The blocker must be a structured reference to trusted state, such as an authoritative permission/prerequisite result. If the blocker is an ASM permission or attempt state, the event source and evidence contract must be designed with ASM; a model-generated explanation is not sufficient.

Clearing a blocker requires evidence that the same blocker is resolved. This transition must not grant the missing permission; it only updates goal state after the trusted source reports resolution.

### 3.3 Satisfied

Satisfied means the success condition recorded on the goal has been met and that conclusion has been accepted as a durable state transition.

A satisfaction proposal must reference existing evidence events and identify the success condition it supports. CSD can validate event identity, provenance, and contract shape, but deterministic persistence checks do not prove semantic entailment. The deliberator/reviewer judgment must remain attributable and uncertainty must not be erased.

No scheduler, elapsed time, activity completion flag, or model score may automatically satisfy a goal.

### 3.4 Abandoned

Abandonment is an explicit decision to discontinue an active, paused, or blocked goal. It is terminal in the first version. Preserve the goal's origin, source-signal versions, prior versions, and abandonment rationale. It does not delete the goal or its history.

### 3.5 Superseded

Superseding a goal must identify a distinct, already persisted successor goal. The successor may be candidate or active; superseding does not activate it. CSD must validate both expected goal versions and commit the old-goal transition and successor relation atomically. Reject self-reference and cycles. Preserve the original goal's provenance and full version history.

### 3.6 Revision

A revision updates the desired condition and/or success, stop, and review conditions while preserving the same goal identity and source lineage. It increments the goal version and preserves the current lifecycle status. The proposal must include the exact prior goal version and a concise revision rationale.

Revision must not silently rewrite:
- origin class;
- source signal-version references;
- creation proposal/event IDs;
- creation time;
- prior goal versions.

If the intended outcome is materially different, create a new candidate and use a separate supersession transition rather than mutating the old goal's identity.

## 4. Proposal and decision contracts

Use a CSD-owned proposal/decision boundary. A shared envelope may be used for the first lifecycle operations, but every operation must have a strict, operation-specific payload schema and reducer. Do not expose a generic `set_goal_status(goal_id, status)` API.

Common proposal fields:
- stable `proposal_id`;
- exact `based_on.state_version`;
- target `goal_id`;
- exact `expected_goal_version`;
- typed operation and operation-specific fields;
- concise rationale;
- proposer component/version and contract version.

Operation-specific fields:
- pause/resume: no additional state assertion;
- blocked/unblocked: blocker references and resolution evidence;
- satisfied: success-condition reference and supporting evidence event IDs;
- abandoned: concise reason;
- superseded: successor goal ID and expected successor version;
- revise: replacement goal text/conditions and revision rationale.

CSD alone creates the decision event. It recomputes the expected transition from authoritative history, verifies the proposal and exact versions, and persists the new goal version plus proposal decision projection in one transaction.

Proposal chronology follows the existing invariant: a proposal may be stale at append time and later defer, but it cannot claim a state version that did not exist when its event was appended. A future claimed version is rejected; an older version is never silently rebased.

## 5. Versioning, atomicity, and Recovery

For every accepted single-goal transition:
- goal version increments exactly once;
- shared state_version increments exactly once;
- the new version references the authoritative decision event and a deterministic transition identity;
- immutable origin and creation lineage are preserved;
- prior goal versions remain append-only.

For a multi-goal operation such as supersession:
- all affected goal versions and relations commit atomically;
- each affected goal version increments once;
- shared state_version increments once for the accepted transition event, not once per goal.

Rejected/deferred decisions:
- do not change goal versions;
- do not change shared state_version;
- remain proposal-scoped and idempotent.

Projection reconciliation and Recovery must replay lifecycle proposals/decisions in event order, validate exact expected versions and transition legality, rebuild all goal/version/latest-state projections, and fail closed on missing, duplicate, contradictory, or impossible transitions. Recovery must not call a model, runtime, ASM executor, or platform adapter.

## 6. Life Engine and ASM boundaries

Life Engine may propose internal choices such as pause, resume, or abandon. CSD decides whether the proposed transition is admissible and durable.

Activity start/continue/stop remains a separate decision. An active goal does not require constant progress; a paused goal must not be offered as a normal activity target; a blocked goal must not be treated as actionable until its blocker is resolved.

Blocked-state evidence that depends on capabilities, external attempts, or permissions must come from a trusted ASM/runtime boundary. Goal state cannot grant, widen, or renew those permissions.

## 7. Initial implementation order

1. [x] Implemented pause/resume as the first low-risk lifecycle slice: explicit proposal, CSD-authoritative decision, exact version checks, atomic goal version update, projection reconciliation, Recovery, and Life Engine choice/sink support. Hosted CI run #264 passed 322 tests on Ubuntu and Windows.
2. [x] Review the initial pause/resume slice on hosted Linux and Windows; continue adversarial review and run the user's local Windows validation when available.
3. Design blocker evidence with ASM before implementing blocked/unblocked.
4. Design satisfaction evidence and semantic-review attribution before implementing satisfied.
5. Implement abandonment, supersession, and revision only after their terminality, lineage, and multi-goal atomicity rules are reviewed.

## 8. Open decisions

- Whether candidate goals need a distinct `dismissed`/withdrawn status.
- Whether `blocked` is stored as goal state or derived from authoritative ASM blockers, and which component may originate the event.
- What minimum evidence/review is required to accept `satisfied`.
- Whether supersession may point to a candidate successor or must require an active successor.
- How to distinguish a same-intent revision from a materially new goal.
- Whether multiple active goals require ordering/priority metadata. No universal priority score is assumed here.

This document is an implementation proposal, not a frozen CSD/ASM contract. The first implementation target is pause/resume only; the remaining transitions stay unimplemented until their operation-specific authority and evidence requirements are settled.
