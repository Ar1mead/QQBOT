# First Cognitive-State Vertical Slice — Test Contract

> Status: **proposed engineering test contract; not normative CSD conformance tests**  
> Source basis: CSD v0.1 semantic working baseline as summarized in [reconciliation report](../reports/csd-v0.1-architecture-reconciliation.md), plus the proposed vertical slice in [design](first-cognitive-state-vertical-slice.md). The cited baseline is not verbatim source text.

## Test fixture

All tests use synthetic data only:
- one observation event describing a fictional blue paper boat near a stone bridge;
- one candidate episodic-memory proposal referring to that observation;
- one deterministic CSD-owned test evaluation policy;
- one temporary SQLite database.

No LLM, network, platform adapter, external action, personal content, or user account is involved.

## Test cases

| case_id | contract_basis | precondition | trigger | expected | asserts | forbidden |
|---|---|---|---|---|---|---|
| COG-001 | CSD v0.1 Event Submit; vertical-slice §4.1 | Empty store | Submit valid synthetic observation event | Event accepted; no accepted memory exists | Event identity and payload reference are durable; Memory Retrieval returns empty | Observation is automatically promoted to memory |
| COG-002 | CSD authority boundary; vertical-slice §4.2 | Observation event exists | Submit valid candidate-memory proposal event | Proposal event accepted; no accepted memory exists | Proposal references existing observation; accepted-memory count remains zero | Proposal submission directly mutates accepted-memory projection |
| COG-003 | CSD sole state authority; vertical-slice §5 | Valid pending proposal exists | Invoke CSD-owned evaluation path | CSD records its own decision | Decision actor/policy provenance identifies CSD authority path | Caller-supplied accepted flag or model score decides outcome |
| COG-004 | CSD atomic state transition; vertical-slice §4.3 and §7 | Valid proposal awaiting evaluation | Evaluate with acceptance fixture | Decision and one accepted memory commit atomically | Decision references proposal/evidence; memory references decision/transition | Accepted memory exists without durable decision, or decision says accepted without matching memory transition |
| COG-005 | CSD Event Submit idempotency; vertical-slice §7 | Observation event already accepted | Resubmit same event ID and immutable content | Duplicate result; no extra event or projection update | Same sequence/result identity; counts unchanged | Duplicate event is reduced twice |
| COG-006 | CSD Event Submit idempotency; vertical-slice §7 | Proposal event already accepted | Resubmit same event ID and immutable content | Duplicate result; proposal is not evaluated or accepted twice | One proposal identity and at most one terminal decision | Duplicate proposal creates a second memory |
| COG-007 | CSD idempotency conflict; vertical-slice §7 | Event ID already bound to immutable content | Submit same event ID with changed payload | Explicit conflict; original record preserved | Original payload digest and state unchanged | Existing event is overwritten |
| COG-008 | Evidence provenance; vertical-slice §5 | Store lacks referenced evidence event | Submit/evaluate proposal referencing unknown event ID | Proposal is rejected or deferred; no accepted memory | No partial memory transition; missing reference is recorded in outcome | Missing evidence is silently fabricated or ignored |
| COG-009 | Proposal/state version boundary; vertical-slice §5 | Proposal records an older relevant state version | Change relevant state, then evaluate stale proposal | Proposal is reevaluated, deferred, or rejected | No blind application against stale state | Stale proposal overwrites newer accepted state |
| COG-010 | CSD atomicity; vertical-slice §7 and §9 | Valid proposal pending | Inject failure during decision/transition commit | Entire decision+memory transaction rolls back, or recoverable protocol completes exactly once | Reopen shows either no accepted transition or one complete accepted transition | Partial accepted memory or split-brain decision/projection |
| COG-011 | CSD Recovery; vertical-slice §7 | One accepted memory and decision committed | Close, reopen, run Recovery | Same accepted memory and provenance are reconstructed | Memory Retrieval after recovery equals pre-close result | Recovery invokes model, evaluator, adapter, or external action |
| COG-012 | CSD Memory Retrieval; vertical-slice §6 and §8 | Candidate and accepted memory both exist | Retrieve memories | Only accepted memory appears in normal Memory Retrieval | Returned record includes evidence, proposal, and decision references | Candidate is presented as accepted autobiographical memory |
| COG-013 | CSD sole state authority; vertical-slice §9 | Runtime/model/adapter test principals exist | Attempt direct accepted-memory write | Operation denied or unavailable | Only CSD authority path can commit the accepted projection | Runtime/model/adapter can bypass CSD |
| COG-014 | CSD recovery integrity; vertical-slice §7 | Decision or evidence history is corrupted | Run Recovery | Safe integrity failure; preserve database for inspection | No fabricated accepted memory; source records retained | Recovery silently repairs semantic contradictions by discarding evidence |
| COG-015 | CSD separation of event and memory; vertical-slice §3 and §6 | Several observations exist, none proposed as memory | Retrieve accepted memories | No automatic memory appears | Event history and memory projection remain distinct | Every event becomes a memory by default |
| COG-016 | CSD decision lifecycle; vertical-slice §4.3 and §9 | Proposal is validly deferred or rejected | Evaluate proposal | Decision is durable; no accepted memory is created | Decision outcome and reason are retrievable | Rejected/deferred proposal is treated as accepted or erased |

## Coverage and limits

Covered by this proposed contract:
- event versus memory separation;
- proposal persistence versus proposal acceptance;
- CSD decision authority;
- provenance links;
- idempotency and conflict behavior;
- stale proposal handling;
- atomic decision/state transition;
- accepted-memory retrieval;
- recovery without reevaluation or side effects;
- direct-write prohibition.

Not covered:
- semantic quality of a model-generated memory;
- memory importance, salience, consolidation, decay, forgetting, or contradiction resolution;
- long-term personality or preference changes;
- affect, drives, goals, commitments, or diary;
- multiple concurrent CSD evaluator workers and proposal ordering;
- production authentication, encryption, privacy, retention, or migration;
- Windows-specific durability and crash behavior;
- real platform observation.

These omissions are intentional. They should become separate test groups only after the corresponding design and state contracts exist.
