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

