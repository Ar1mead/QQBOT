# CSD Goal-State Integration — Design Proposal

> Status: **design proposal; not a frozen CSD/ASM specification**  
> Scope: the first durable goal-state family connected to the Life Engine  
> Related: `motivation-and-life-engine-contract.md`, `motivation-signal-csd-integration-contract.md`, `csd-minimal-persistence-proposal.md`

## 1. Purpose

The Life Engine can now read accepted CSD motivation signals through a consistent snapshot. The next missing durable state family is goals.

A goal must persist as part of CSD's one authoritative event history. It must not live only in a prompt, a scheduler queue, a plugin's private database, or an in-memory Agent plan.

This proposal deliberately separates:

- **deliberation** — a replaceable model/service may suggest one or more goals and a current choice;
- **candidate goal persistence** — CSD validates references and stores a proposed goal as a candidate;
- **activation** — a separate accepted transition makes a candidate goal active;
- **activity execution** — a later runtime/ASM path may attempt a bounded activity; goal persistence itself never executes anything.

A stored candidate is not proof of subjective desire, a promise, or an instruction to act.

## 2. Why candidate must be separate from active

The current Life Engine can propose a goal and independently choose `wait`, `decline`, or `no_op`. Therefore, accepting a goal proposal must not automatically mean that the individual has committed to pursuing it now.

Initial goal lifecycle proposal:

- `candidate` — CSD accepted the goal hypothesis as a durable candidate; no pursuit is implied.
- `active` — the individual later chose to pursue it.
- `paused` — retained but not currently pursued.
- `blocked` — pursuit is currently prevented by a missing prerequisite/capability.
- `satisfied` — its success condition has been evidenced and accepted.
- `abandoned` — intentionally discontinued.
- `superseded` — replaced by a successor goal with an explicit relation.

The first implementation should support candidate creation only. Do not implement all lifecycle transitions in one step.

## 3. Proposed event family

### 3.1 Proposal event

`life.goal_batch_proposed.v1`

One event contains the goals produced by one deliberation opportunity. This avoids partial persistence when a single deliberation proposes multiple related goals.

Conceptual payload:

- `proposal_id` — stable idempotency identity;
- `based_on.state_version` — shared CSD state version read by the Life Engine;
- `goals[]` — zero or more candidate goal hypotheses;
- `choice` — the current proposed disposition, including a valid `no_op`;
- `origin` — component and version of the deliberator/adapter;
- `contract_version` — version of this proposal shape.

Each goal entry contains:

- `goal_id` — unique proposed identity;
- `desired_condition` — what condition the individual may want to bring about;
- `origin_signal_refs[]` — exact `signal_id` and `signal_version` pairs from the CSD snapshot;
- `rationale` — concise reason summary, not hidden chain-of-thought;
- `success_condition` — observable evidence that would satisfy the goal;
- `stop_condition` — when to stop pursuing it;
- `review_condition` — when/how to reconsider it.

The proposal must not assign authoritative goal origin, accepted status, goal version, decision ID, CSD state version, capability grants, or external action payloads.

### 3.2 CSD decision event

`life.goal_batch_decided.v1`

Only CSD's internal authority path may append this event. It binds:

- proposal ID and proposal event ID;
- evaluated state version;
- policy ID/version;
- outcome (`accepted`, `rejected`, or `deferred`);
- per-goal CSD-derived origin class;
- accepted goal identity/version and initial lifecycle status;
- reason code/summary.

An accepted batch creates each goal at version 1 with status `candidate`. A rejected/deferred batch creates no goal transition. The whole batch is atomic.

## 4. Origin and evidence rules

CSD derives goal origin from the referenced accepted signal versions. The Life Engine's own `goal_origin_classes` output is explanatory only and is never trusted as authority.

For each `origin_signal_ref`, CSD verifies:

1. the signal exists and the referenced version exists in event-backed history;
2. the signal is active at the proposal's evaluated state version;
3. the signal version belongs to the same CSD state snapshot;
4. the goal references at least one source signal;
5. the signal's immutable initial origin and accumulated voluntary-encounter summary are preserved.

Derived goal origin:

- all source signals internally initiated → `internally_initiated`;
- all source signals user-requested → `user_requested`;
- all source signals externally exposed → `externally_triggered`;
- mixed source classes → `mixed_origin`;
- a user/external-origin interest that has subsequently developed a CSD-verified emerging voluntary pattern → `mixed_origin`, never purely internal.

Do not allow a user request to become internally initiated merely because the individual later chooses to revisit the subject. The original signal origin remains immutable; later voluntary encounters add a separate lineage.

The first version should reference accepted signal versions, not copy arbitrary evidence event IDs supplied by the deliberator. CSD already owns and validates the evidence attached to each accepted signal.

## 5. Version and concurrency semantics

- The proposal's `based_on.state_version` must equal the current authoritative CSD state version at evaluation.
- Every referenced signal version must be the exact version visible in that state.
- Any intervening accepted memory, motivation, or goal transition makes the proposal stale and therefore deferred/rejected; it is never silently rebased.
- Accepted candidate creation increments the shared CSD state version exactly once for the batch.
- Rejected/deferred batches do not increment state version.
- A repeated identical proposal ID/payload is idempotent.
- Reusing a proposal ID with different immutable content is an identity conflict.
- A proposal may receive at most one CSD decision.

The state-version definition must remain aligned with the current CSD global version implementation and be reconciled before this proposal is frozen.

## 6. Projection and Recovery

Proposed rebuildable projections:

- `goal_proposals` — immutable proposal identity/digest, source event, status, decision event;
- `goals` — latest accepted goal state by goal ID;
- `goal_versions` — append-only version history keyed by goal ID/version and authoritative decision event.

The event log remains authoritative. Every projection row must be reconciled against proposal/decision events before it is trusted.

Recovery must:

- validate the event and payload digests;
- replay proposal/decision events in sequence;
- reconstruct the same candidate goals and versions;
- reject missing, duplicate, contradictory, or stale transitions;
- never call a model, re-run deliberation, activate a candidate, or execute an activity.

No separate goals database is permitted.

## 7. Snapshot contract

The CSD Life Engine snapshot should eventually contain:

- shared `state_version`;
- accepted motivation signals with exact versions;
- accepted goals with exact versions and lifecycle status;
- active activities and their current stop/permission state, from trusted state sources;
- capability-filtered activity options from a trusted runtime/permission boundary.

The current `CognitiveStoreLifeSnapshotReader` intentionally supplies only accepted motivation signals. Goals and activity options remain empty until their state families and trusted capability source exist. Do not fill these fields with model-generated guesses.

## 8. Security and privacy boundaries

- `source` and `origin.component` are provenance metadata, not adapter authentication.
- External platform content is untrusted and cannot create a goal directly.
- A model may propose a goal; it cannot grant capabilities or dispatch actions.
- Private diary content must not enter a goal proposal unless its privacy scope explicitly authorizes that use.
- Goal creation is an internal state transition, not an external side effect. Any later platform action remains ASM-governed.

## 9. Initial acceptance tests

1. A valid proposal creates candidate goals, not active goals.
2. A no-op choice can coexist with a candidate goal proposal without activating it.
3. A goal must reference at least one accepted signal ID/version.
4. Unknown or stale signal versions are rejected/deferred.
5. User-requested and externally exposed origins cannot be rewritten as internal.
6. An emerging voluntary pattern on a user/external-origin interest produces mixed lineage.
7. Multiple goals in one batch commit atomically or not at all.
8. Identical proposal retries are idempotent; conflicting proposal identity is rejected.
9. A proposal receives at most one decision.
10. Accepted goal versions and projections reconcile against event history.
11. Recovery rebuilds candidate goals without activating them or calling any model/action executor.
12. A corrupted goal projection fails closed and can be rebuilt from valid events.

## 10. Explicit non-goals for the first slice

- No automatic goal activation.
- No universal priority score or forced choice on each wake-up.
- No fixed schedule or quota for goal generation.
- No goal execution or side-effecting adapter.
- No goal conflict solver.
- No claim that a persisted candidate proves genuine subjective motivation.

This proposal is a basis for implementation review, not a frozen normative specification.
