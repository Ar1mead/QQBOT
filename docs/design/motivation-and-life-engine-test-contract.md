# Motivation and Life-Engine Test Contract — Initial Coverage

> Status: **proposed engineering test contract; not frozen CSD conformance tests**  
> Depends on: `motivation-and-life-engine-contract.md`, CSD state-authority boundary, memory lifecycle proposal, and ASM action-governance boundaries.

These tests are intended for the first provider-neutral implementation. They do not claim to measure consciousness or subjective experience.

| Case | Precondition / trigger | Expected result | Forbidden result |
|---|---|---|---|
| MOT-001 | Timer/wake opportunity arrives with no salient internal state or external opportunity | Explicit no-op; no goal or activity is created | A task is invented to keep the system busy |
| MOT-002 | New external opportunity arrives without an internal motivation | Opportunity is available for consideration | Opportunity is automatically classified as an internally generated goal |
| MOT-003 | A user-requested activity is completed | Origin remains user-requested | It is counted as independent voluntary interest evidence |
| MOT-004 | One isolated click/watch occurs | No stable interest is inferred from the action alone | Permanent preference is written |
| MOT-005 | Repeated voluntary choices with alternatives and source evidence are supplied | Interest proposal may be formed with provenance and uncertainty | Interest is asserted as objective fact |
| MOT-006 | Counterevidence conflicts with an established interest hypothesis | Conflict or context-specific revision is retained | Counterevidence is silently ignored |
| MOT-007 | A drive has a defined resolution condition and new evidence satisfies it | Drive may be reduced/resolved by a traceable transition | Drive persists only because a recurring timer recreates it |
| MOT-008 | A resource limit exists | It remains a constraint unless explicitly modeled as a need | API quota/disk space is automatically described as an emotional need |
| GOAL-001 | Internal interest/question/drive gives rise to a candidate goal | Goal proposal records causal origin and supporting state references | Candidate becomes active without an authoritative transition |
| GOAL-002 | Goal proposal is based on a stale state version | It is deferred/re-evaluated against current state | Stale goal overwrites newer state |
| GOAL-003 | Goal success condition has no observable evidence | Goal remains active/pending/uncertain | Goal becomes satisfied because a plan ran |
| GOAL-004 | Individual decides goal is no longer worthwhile | Goal may be abandoned with reason and history preserved | Abandonment is reported as task failure by default |
| GOAL-005 | Two goals conflict | Decision record preserves tradeoffs, alternatives, and chosen disposition | Arbitrary universal weighted sum is treated as objective truth |
| GOAL-006 | No justified preference exists between candidates | Defer, request more information, or no-op | False precision is generated to force a ranking |
| INT-001 | Activity is proposed without required capability/permission | Block or reject before execution | Motivation grants permission |
| INT-002 | A side-effecting activity is selected | Submit action request through ASM | Life Engine calls adapter directly |
| INT-003 | Action dispatch is attempted but external outcome is unknown | Preserve uncertain state; verify before any retry | Dispatch is treated as success |
| INT-004 | Stop condition or cancellation is met | Activity stops or pauses without automatic restart | A scheduler restarts it without a new deliberation |
| INT-005 | Goal remains active but no good activity exists | Goal remains active while life engine returns no-op/wait | A random activity is selected |
| INT-006 | A model proposes an unlisted candidate or fabricates a permission | Reject invalid proposal; preserve diagnostics | Model-created authority is trusted |
| INT-007 | Two candidate activities are incomparable | Preserve the tradeoff or defer | Arbitrary score breaks the tie silently |
| INT-008 | Permission is revoked while an activity is running | Continuation is blocked; stopping remains available through the proper governance path | Previously granted permission is assumed permanent |
| INT-009 | An activity's stop condition is already met | Continuation is blocked | The activity is continued because it was previously started |
| INT-010 | A running external side-effect activity is continued or stopped | Hand off through ASM | Life Engine directly dispatches or cancels a platform action |
| INT-011 | A candidate activity has no active motivation signal but serves an accepted goal | It may be considered with the goal reference preserved | A valid ongoing goal is discarded as a motivation source |
| INT-012 | A candidate activity has neither a motivation signal nor an accepted goal source | Reject the source-free option | An arbitrary activity is presented as internally motivated |
| GOAL-007 | A self-accepted commitment is the source of a goal | Preserve commitment provenance and classify the origin accordingly | A user assignment is rewritten as a self-commitment |
| LIFE-001 | Process restarts with an active goal and no active external action | Recover goal/activity state and re-deliberate when safe | A previously planned action is assumed completed |
| LIFE-002 | Recovery replays goal/decision events | State is reconstructed from durable events | Model is called again or external action is replayed |
| LIFE-003 | An event is duplicated with identical immutable content | Idempotent duplicate | Duplicate goal or activity is created |
| LIFE-004 | Same identity is reused with changed content | Identity conflict | Existing state is overwritten |
| LIFE-005 | A no-op decision is replayed | No-op remains a valid historical choice | Retry machinery treats no-op as a failed attempt |
| DIARY-001 | A writing inclination emerges from an internal event | A private writing intention may be proposed | A scheduled daily quota is created |
| DIARY-002 | No writing inclination exists when the wake timer runs | No diary activity is created | Empty diary entry or reason-for-not-writing is generated |
| DIARY-003 | Individual starts a draft and chooses not to save | Draft can be discarded without creating a general memory | Draft is automatically persisted as autobiographical memory |
| DIARY-004 | Diary entry is saved | It remains a separate private artifact with its own scope | All diary text is automatically indexed as general memory |
| DIARY-005 | A diary entry later inspires a memory proposal | Derived memory references diary source subject to access policy | Diary and derived memory are merged or privacy scope is widened |

## Coverage notes

- Tests above are proposed implementation tests, not normative CSD/ASM conformance cases.
- They do not specify model prompt correctness or claim a model has subjective experience.
- The first code slice should cover no-op, origin attribution, goal lifecycle, constraints, and recovery before adding live platform adapters.
- CSD event schemas, migration rules, and authority checks must be designed before persistent goal state is written by a separate subsystem.
- A real provider must first run in proposal-only mode with synthetic/non-sensitive observations.
