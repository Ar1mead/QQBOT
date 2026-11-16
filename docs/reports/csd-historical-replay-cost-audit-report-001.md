# CSD historical replay cost audit report 001

Date: 2026-11-16 (UTC+08:00)

Branch reviewed: `feature/csd-cognitive-memory-slice`

Reviewed commit: `f1a16d06bd70858656433a96c49760f72e0ee6fe`

## Scope

Static code review of historical state-version validation and projection reconciliation in:

- `core/csd/cognitive.py`
- `core/csd/goals.py`
- `core/csd/motivation.py`

This is an algorithmic review, not a benchmark. No production code was changed in this audit.

## Findings

### 1. Historical state-version counting is repeatedly replayed

`CognitiveMemoryStore._authoritative_state_version()` queries decision events from the beginning of the event history (or through a supplied sequence), ordered by sequence. It then calls `get_event(..., _validate_decision_context=False)` for every matching decision and counts accepted outcomes.

This is integrity-aware and does not trust a mutable state-version projection. However, it repeats the same prefix work when called many times during one larger replay.

### 2. The repeated calls occur inside history-wide validation

The reviewed call paths include:

- `_validate_decision_event_history()`: recomputes the historical state version for each decision read.
- `_validate_goal_proposal_snapshot_version()`: recomputes the prefix state version for each goal proposal.
- `_assert_goal_projection_consistent_v2()`: walks all goal proposals and decisions in sequence order, and calls the state-version counter for each proposal/decision it validates.
- `_assert_motivation_projection_consistent()` and `_memory_projection_sources()`: read historical events through the normal `get_event()` path, which invokes decision-context validation for decision events.

Consequently, a history-wide validation can repeatedly rescan overlapping decision prefixes. With D decision events, the repeated decision-prefix work can grow quadratically in D; proposal-heavy histories can add further repeated prefix scans. The event-type/sequence queries also have no explicit composite index declared in `cognitive.py` at the reviewed commit.

### 3. This is a scaling risk, not a demonstrated correctness failure

The current 362-test suite verifies correctness on the existing fixtures, but it does not establish acceptable performance for long-lived histories. No large-history timing or query-count benchmark was found in the reviewed test/workflow files.

No claim is made here about a measured slowdown or a particular practical event-count threshold.

## Constraints for the eventual optimization

Any optimization must preserve all of the following:

1. The append-only event history remains authoritative; mutable projections cannot be used as the sole source for historical state versions.
2. Historical state versions must be calculated from accepted decisions strictly before the event being checked.
3. All relevant decision families must contribute to the shared state version exactly as they do now.
4. Payload and envelope integrity checks must still run before an event contributes to the count.
5. A history-wide replay should calculate reusable prefix information once per stable SQLite read/recovery snapshot, rather than caching it across transactions where direct database tampering or concurrent writes could make it stale.
6. Recovery must remain deterministic and must never replay external side effects.
7. Hashes remain integrity digests, not authenticated signatures.

## Recommended next implementation slice

Introduce a per-operation historical replay context that:

- scans and integrity-checks relevant decision events once in sequence order;
- records the accepted-decision prefix count at each relevant event sequence;
- supplies that count to memory, motivation, and goal historical validators during the same stable read/replay;
- avoids recursive or repeated full-prefix state-version scans;
- is discarded at the end of the operation.

Then add deterministic regression coverage for mixed decision families and history chronology, plus a query-count/scaling test that detects repeated prefix scans without relying solely on wall-clock thresholds. Consider a composite `(event_type, sequence)` index only after checking the actual SQLite query plan and migration implications.

## Verification status

- GitHub Actions run #431: both Ubuntu and Windows jobs completed successfully.
- Full unittest discovery: 362 tests passed on each hosted runner.
- Compileall and all focused workflow test steps passed.
- This audit itself changes no runtime code and has not been performance-benchmarked.
- User-local Windows 11 / Python 3.12.14 testing remains deferred by design.



## Follow-up implementation — schema v6 query index

After the audit, schema v6 added the transactional composite index `idx_events_event_type_sequence` on `events(event_type, sequence)`.

Regression coverage now verifies:

- successful v5→v6 migration;
- rollback when the target index name already exists with a conflicting definition;
- use of the new index by the shared event-type/prefix query, through `EXPLAIN QUERY PLAN);
- migration from v3 and v4 fixtures through the later schema versions.

Hosted verification for commit `7fb4922423af318622e804bdc0225fb6c50cddc7`, GitHub Actions run #438: Ubuntu and Windows both passed; full discovery reported **364 tests per platform**. This is hosted verification only.

The index reduces the cost of each event-family/prefix query, but it does not remove the repeated-prefix algorithm identified above. The per-operation replay context remains the next work item.


Final branch-head confirmation: commit `8f52c3e43f133b62b210e36fac4cc9951097aea0`, PR-triggered GitHub Actions run #444 passed on Ubuntu and Windows with **364 tests per platform**. Run #444 is the latest verified PR workflow for this report's implementation state.


## Follow-up implementation — transaction-scoped decision replay context

The per-operation replay-context design has now been implemented in the CSD reference slice.

### Implementation

- Added immutable `_DecisionReplayContext`, containing the sequence numbers of accepted durable decisions.
- Added one transaction-scoped builder that selects all five durable decision families in event order and reads each decision through the existing `get_event` integrity path with only recursive decision-context validation disabled.
- State-version lookups now use `bisect_right` over the accepted-decision sequence list rather than re-querying and recounting the entire decision prefix each time.
- Memory, motivation, and goal projection validation now run inside a stable read transaction when they are not already inside a read/write transaction. Existing write and Recovery transactions share the same context.
- The context is reset when a transaction begins/ends and invalidated immediately after each event append. It is not persisted or reused across transactions.
- Event payload/envelope integrity and event-local schema checks remain active for every decision. The context is an optimization of prefix aggregation, not a shortcut around event validation.

### Regression coverage

A mixed-family test creates valid accepted decisions for memory, motivation, goal batch, activation, and pause/resume. It verifies:
- all five decision families contribute to the shared state version;
- combined memory/motivation/goal read validation executes one decision-family prefix selection in one read transaction;
- Recovery executes one prefix selection for the full event replay;
- the context is cleared after both operations;
- state version remains unchanged after Recovery.

The test counts the specific SQL prefix-selection query rather than relying only on elapsed time. This detects repeated prefix selection deterministically. A separate long-history timing benchmark is still pending.

### Hosted verification

The implementation and mixed-family read-transaction regression were verified by PR workflow run #456: Ubuntu and Windows each passed **365 tests**, including compileall and all focused suites.

The additional Recovery query-count assertion is in commit `e0d1a374784e6e9aaf66b956a1b96718001cb4fb`. PR workflow run #458 completed successfully on both Ubuntu and Windows: **365 tests per platform**, including compileall and focused suites. User-local Windows 11 / Python 3.12.14 verification remains deferred until project handoff.


## Second-round follow-up — decision-family ordinals and accepted counts

Date: 2026-11-16 (UTC+08:00)

### Additional issue addressed

The first replay-context pass removed repeated accepted-decision prefix aggregation for state-version lookups, but the follow-up review identified more decision-history prefix work:

- Memory decision ordinal allocation.
- Motivation decision ordinal allocation.
- Accepted motivation transition counts used while validating historical motivation projections.

These operations now reuse the same transaction-scoped verified context. It stores ordered decision sequences by event family and accepted sequences by family. Ordinals are derived from the family's verified sequence index; accepted transition counts use binary-search prefix lookups over accepted sequences.

### Regression coverage and result

The mixed-family regression now creates and accepts a second memory proposal and a second motivation proposal, verifies both family ordinals advance to `:2`, and creates a second goal-batch decision. The second motivation proposal is genuinely created and evaluated by the test helper before the test reads its projected decision ID.

The test asserts:

- No decision-family `SELECT COUNT(*)` prefix query occurs during decision creation.
- Combined memory/goal projection validation performs one shared five-family decision-prefix selection.
- Recovery performs one shared five-family decision-prefix selection.
- Neither combined reads nor Recovery issue repeated decision-family prefix counts.
- The context is cleared after each transaction.
- Recovery preserves the expected state version (8).

Latest branch head at review: `20ef3c5f021c2ff1d6010d993a18be024947ef5c`. PR workflow run #481 passed on Ubuntu and Windows; full unittest discovery reported **365 tests per platform**, and compileall plus all focused suites passed. Run #480's push-triggered result was not independently retrievable through the available workflow-run lookup and is therefore not claimed as verified. This remains hosted CI, not user-local Windows 11 / Python 3.12.14 verification.

### Updated assessment and limits

The identified repeated decision-family prefix counts and accepted-transition recounts are now covered by deterministic query-count regression assertions and routed through the per-transaction context. Other `COUNT(*)` queries used for projection row totals/diagnostics are not the same decision-history prefix operation and remain ordinary integrity/diagnostic checks.

This is not a long-history wall-clock benchmark. It does not prove that every cross-projection scan, event validator, or future replay path scales linearly. Continue static review and add targeted tests where a repeated full-history scan is found before making a broader performance claim.

