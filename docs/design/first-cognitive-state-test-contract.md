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

| COG-017 | Proposal identity distinct from event identity; storage decision analysis §5 | One proposal_id already exists | Submit a second event_id with identical immutable proposal content | Event identity remains distinct but proposal resolves to the existing aggregate | Exactly one proposal lifecycle and at most one accepted memory | Second event creates a second proposal decision or accepted memory |
| COG-018 | Proposal identity immutability; storage decision analysis §5 | One proposal_id already exists | Submit a second event_id with changed immutable proposal content | Proposal-identity conflict; original proposal remains unchanged | Original proposal digest and decision state are preserved | Same proposal_id silently changes meaning |
| COG-019 | CSD-owned decision authority; storage decision analysis §4 and §6 | Public Event Submit is available | Submit a reserved CSD decision event through the public path | Submission is rejected | No decision event or accepted-memory transition is committed | Runtime, model, or adapter forges a CSD decision |
| COG-020 | CSD Recovery; storage decision analysis §7 | Proposal is persisted but not yet evaluated | Close, reopen, run Recovery | Proposal remains pending | No decision event or accepted memory is synthesized | Recovery evaluates or auto-accepts a pending proposal |

| COG-021 | Event history is authoritative; implementation decision §3 and §6 | Accepted decision exists but accepted-memory projection is incomplete | Attempt to evaluate another proposal before Recovery | Evaluation stops with an integrity error; after Recovery the projection is rebuilt and evaluation can proceed | Event-derived state version remains stable; projection consistency becomes true after Recovery | Damaged projection silently lowers state version or allows stale proposal acceptance |

| COG-022 | Proposal generation is not state acceptance; provider contract §4 | Observation and provider are available | Provider returns a candidate | Candidate event is persisted as pending; accepted-memory retrieval remains empty | Provider result is represented only as an untrusted proposal | Provider output directly creates accepted memory |
| COG-023 | Provider execution outside CSD transaction; provider contract §4 | Provider is configured | Generate a candidate or simulate provider failure | Provider runs outside write transaction; failure leaves CSD unchanged | Transaction state is false during provider call; event/projection counts unchanged after failure | Model/provider call runs while CSD write lock is held |
| COG-024 | Strict proposal schema; provider contract §3 and implementation decision §5 | Proposal event is submitted | Include unsupported authority-like fields | Event submission is rejected atomically | Event count and accepted memory remain unchanged | Candidate can smuggle accepted status, transition ID, or executable fields |

| COG-025 | Grounded-memory v2 §5.1 | One valid observation and a grounded proposal with exact source span | Evaluate proposal | CSD accepts one source_assertion claim with source locator preserved | Claim text equals quote and stored observation slice equals quote | Proposal is accepted when the source span differs |
| COG-026 | Grounded-memory v2 §5.1 and §6 | One observation and a proposal whose quote does not match its locator | Evaluate proposal | Proposal is durably rejected; no accepted memory is created | Rejection reason identifies quote/source mismatch | CSD silently rewrites quote or accepts unsupported text |
| COG-027 | Grounded-memory v2 §5.1 and §6 | One observation and a proposal with an out-of-bounds end offset | Evaluate proposal | Proposal is rejected without partial accepted state | No memory transition is committed | Out-of-bounds offsets are truncated or clamped silently |
| COG-028 | Grounded-memory v2 §6 | Proposal references an observation event not yet available | Evaluate proposal | Outcome is needs_more_evidence; no memory is created | Missing evidence reference remains explicit | Recovery fabricates or auto-accepts the missing source |
| COG-029 | Grounded-memory v2 §5.2 | Proposal contains inference with missing source claim or inference-to-inference reference | Evaluate proposal | Proposal is rejected | Every inference must resolve directly to source_assertion claim IDs | Inference chain is upgraded to directly observed fact |
| COG-030 | Grounded-memory v2 §5.1; implementation | Source text contains a supplementary-plane character before the quoted span | Evaluate with Unicode code-point locator | Valid span is accepted | Python code-point slice exactly matches quote | UTF-16 or byte offsets are silently interpreted as code-point offsets |
| COG-031 | Grounded-memory v2 §2 and §5 | Proposal contains source claims tied to more than one observation event | Submit grounded proposal | Schema rejects the proposal in the first v2 scope | No proposal event or partial projection is committed | Multiple observations are silently merged as a single-source v2 proposal |
| COG-032 | Grounded-memory v2 §7 and §8 | Accepted memory contains source and inference claims | Close, reopen, run Recovery | Same claims, epistemic labels, evidence IDs, and locators are restored | Retrieved claims equal the pre-close accepted memory | Recovery reruns model generation or changes claim classifications |
| COG-033 | Provider contract §4; grounded-memory provider pipeline | Provider returns a typed grounded candidate for an observation | Generate candidate | Pipeline persists a pending v2 proposal and binds source event/provider/state provenance | Provider runs outside transaction; no accepted memory appears until separate CSD evaluation | Provider chooses arbitrary evidence event or accepts its own proposal |
| COG-034 | Provider contract §4; grounded-memory provider pipeline | Provider returns invalid offset types, multiple candidates, or raises an error | Run proposal pipeline | Invalid output is rejected and provider failure leaves CSD unchanged | Event and projection counts are unchanged | Partially persisted batch or provider call while CSD write transaction is held |

| COG-035 | Memory Retrieval contract §2.1 and §3 | Accepted v1/v2 memories exist with another pending proposal | Call get_memories with no filter | Only accepted memories are returned, including legacy and grounded records | Pending proposal is absent; accepted provenance is intact | Pending proposal is represented as an accepted memory |
| COG-036 | Memory Retrieval contract §2.1 and §5 | Accepted memories contain different text | Call get_memories with query | Case-insensitive substring matches legacy content or grounded claim text | Query result contains only records with matching text | Substring query is described as semantic similarity |
| COG-037 | Memory Retrieval contract §2.1 and §3 | Grounded memories contain source and inference claims | Filter by epistemic_type | Only memories containing that claim type are returned | Source assertions and inferences remain distinguishable | Legacy free-form memory is silently classified as source_assertion |
| COG-038 | Memory Retrieval contract §2.1 | Accepted memories have distinct evidence IDs and memory kinds | Filter by evidence_event_id and memory_kind | Only records matching both filters are returned | Filters combine with logical AND | Evidence references are dropped or guessed |
| COG-039 | Memory Retrieval contract §2.1 and §5 | Several accepted memories exist | Retrieve with limit and offset | Stable insertion-order page is returned | Repeated query over unchanged data yields the same page | Retrieval arbitrarily reorders results |
| COG-040 | Memory Retrieval contract §2.2 | One accepted memory has a stable memory_id | Call get_memory(memory_id) | Full accepted record and provenance are returned; unknown ID is not found | Returned record matches list retrieval | A pending proposal is accessible through accepted-memory lookup |
| COG-041 | Memory Retrieval contract §4 | Accepted memories and event history exist | Call get_memories/get_memory with filters | Read operations do not mutate CSD | Event count and authoritative state snapshot remain unchanged | Retrieval creates events, changes state, or triggers external actions |
| COG-042 | Memory Retrieval contract §2.1 and §5 | Retrieval filter arguments are supplied | Pass an unsupported or non-string epistemic_type | Filter is rejected with ValueError | No query side effect or state mutation occurs | Invalid filter types are coerced or silently ignored |

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
