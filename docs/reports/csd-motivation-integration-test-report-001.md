# CSD Motivation Integration Test Report 001

## Result

**Result: PASS — hosted CI completed successfully.**

- Repository: `Ar1mead/QQBOT`
- Branch: `feature/csd-cognitive-memory-slice`
- Verified commit: `5484fa66880767452b6a81cff617f5f42daf8679`
- Workflow run: [CSD cognitive slice tests #186](https://github.com/Ar1mead/QQBOT/actions/runs/43669847907)
- Linux runner: GitHub-hosted Ubuntu 26.04.1 — Python 3.12.16 / SQLite 3.46.1
- Windows runner: GitHub-hosted `windows-latest` — Python 3.12.10 / SQLite 3.49.1

Both operating-system jobs passed `python -m compileall -q core tests` and the full `python -m unittest discover -s tests -v` run (266 tests each; Linux 2.029s, Windows 11.539s). The Windows runner is a useful platform-compatibility check, but it is not the user's own Windows 11 / Python 3.12.14 machine.

## Exact commands

```bash
python -m compileall -q core tests
python -m unittest discover -s tests -v
```

Both commands completed successfully. Full test discovery reported:

```text
Ran 266 tests in 2.029s on Linux; the Windows runner completed the same 266-test suite in 11.539s.
OK
```

The workflow also ran the individual cognitive, motivation, proposal-pipeline, grounded-memory, retrieval, semantic-review, persistence, and Life Engine test modules. Every step passed.

## Migration coverage

The earlier migration test was invalid: it first created v2 motivation decisions and projections, then removed the v2 projection tables while relabelling the database as schema v1. That combination cannot represent a legitimate v1 database because motivation events/projections were introduced in v2.

The corrected migration test now:
1. Creates legacy observation and memory-proposal events.
2. Accepts a memory and records the legacy event/projection state.
3. Removes only the v2 motivation tables and sets the schema marker to v1.
4. Reopens the database and verifies migration to v2 while preserving legacy events, accepted-memory state, and proposal data.

A separate failure-path test deliberately creates a table-name collision partway through migration. It verifies that the migration transaction rolls back partial DDL and leaves `user_version` at 1.

## Projection reconciliation hardening

The first consistency check compared the latest motivation projection with its version-history table. That could miss coordinated corruption if both tables were changed to the same incorrect value. The check now reconciles:
- every motivation proposal projection row against its immutable proposal event, including terminal decision status and decision-event identity;
- every accepted signal version against the signal object embedded in its authoritative decision event;
- each latest-signal projection against the highest event-backed signal version.

Tests deliberately corrupt both signal projection tables identically and separately alter a proposal's projected status. Both cases are detected; Recovery rebuilds the correct projections from the event history.

The accepted-memory side received the same event-backed integrity treatment. Proposal rows are checked against proposal/decision events, and accepted-memory JSON plus its relational identity fields are reconstructed and compared with the authoritative decision and proposal events. Tests corrupt memory content and proposal status; reads detect the inconsistency and Recovery restores the event-derived state.

A further idempotency test submits a second event for an existing immutable motivation proposal with a forged source component. The duplicate is rejected and the attempted event is rolled back; valid duplicate submissions remain idempotent.

External motivation origins are now tied to the kind of earlier observation they claim to reference: `user_request` must reference a `user_message` observation, and `platform_recommendation` must reference a `platform_recommendation` observation. This checks event semantics, not adapter authenticity; adapter metadata remains caller-supplied and untrusted.

Lifecycle coverage now includes create, reinforce, weaken, contextualize, pause, and resolve transitions. In this prototype, weakening is represented by appending counter-evidence; there is not yet a continuous strength/confidence or affect-dynamics model.

## Follow-up adversarial review after the verified run

The verified code commit includes the follow-up return-visit rule. A return visit is itself a current voluntary selection (internal origin, meaningful alternatives, selected item in the current choice set), and it must reference an earlier interaction for the same subject and selected item, with a distinct encounter and later occurrence time. The earlier interaction need not itself have been voluntary: an independently chosen return can follow passive platform exposure or a user-requested encounter.

Review runs #136–#141 exposed two incorrect assumptions and were intentionally not counted as passing verification: encounter IDs are not globally unique because an encounter may contain multiple events; and a return visit need not follow a prior voluntary selection. Both assumptions were removed. The final test grounds passive exposure in a platform-recommendation observation and verifies that a later voluntary return is accepted.

The corrected implementation and test pass in CI run #142 on both Linux and Windows, with 249 tests each.

A read-integrity check validates the payload and envelope digests for every motivation proposal/decision event and every interaction event referenced by an accepted signal. It also checks that accepted signal evidence belongs to the same subject, precedes the decision, and is correctly classified as supporting or counterevidence. A tampering test disables the immutable-payload trigger, alters an evidence payload without updating its content hash, and verifies that signal reads and Recovery fail closed. This passed in CI run #144 with 250 tests on both operating systems.

The global state-version read path validates the event and payload digests of every memory/motivation decision before counting accepted transitions. A tampering test changes a persisted decision payload without updating its hash and verifies that `get_state_snapshot()` fails closed rather than returning a misleading state version. This passed in CI run #146 with 251 tests on both operating systems.

Pending motivation proposals are also checked before they are returned: each supporting/counterevidence reference must resolve to a prior interaction event for the same subject, with the correct evidence classification and intact payload/envelope digests. A test tampers with evidence while the proposal is still pending and verifies that proposal retrieval fails closed. This passed in CI run #148 with 252 tests on both operating systems.

Cross-module consistency review found that Life Engine initially derived a signal's origin from counterevidence as well as supporting evidence. It now derives the immutable origin class from supporting evidence only, matching CSD. The Life Engine pre-validator also rejects pause proposals with evidence and contextual-stage requests outside contextualize. CSD itself rejects requested maturity metadata on pause/weaken/resolve; the regression suite covers these constraints. This passed in CI run #156 with 256 tests on both operating systems.

The Life Engine snapshot contract now consumes CSD-derived origin classes, interest maturity, scope, and voluntary-encounter lineage rather than re-deriving a raw origin from a single source token. When a user/external-origin interest later reaches an emerging voluntary pattern, a goal derived from it is marked mixed-origin; the signal's initial origin remains unchanged. The test suite verifies this and rejects encounter summaries that do not reference supporting evidence. This passed in CI run #161 with 258 tests on both operating systems.

The Life Engine snapshot validator also requires voluntary-encounter timestamps to be valid timezone-aware ISO-8601 values. This passed in CI run #163 with 259 tests on both operating systems.

The Life Engine signal snapshot now carries the CSD subject reference and separates supporting evidence from counterevidence instead of flattening them into one list. This preserves the evidence polarity and subject identity needed for future goal proposals and activity choices. The updated contract and tests passed in CI run #166 with 259 tests on both operating systems.

A further adversarial check found that both CSD maturity derivation and the Life Engine validator compared timestamp strings rather than actual instants. Two events at `10:00Z` and `11:00+01:00` could therefore be counted as two distinct voluntary encounters even though they occurred at the same instant. Both layers now normalize timezone-aware timestamps to UTC before counting distinct encounters. Regression tests prove equivalent offset spellings do not mature an interest; run #171 passed with 261 tests on both Linux and Windows.

A pure CSD projection mapper now converts accepted motivation-signal records into Life Engine inputs while preserving signal version, subject, origin class, active status, support/counterevidence polarity, interest maturity, and voluntary-encounter lineage. It rejects missing/invalid fields, duplicate signal identities, and encounter references not present in supporting evidence. This is deliberately only a mapping boundary: it does not open the database, perform the CSD integrity read, authenticate the caller, or submit goal/choice proposals. The mapper and its regression tests passed in run #178 with 265 tests on both operating systems. A cross-module test now feeds a real accepted CSD signal, including its accumulated voluntary encounters, through the mapper and asserts that the Life Engine receives the same version, subject, origin, maturity, and encounter lineage. This integration assertion passed in run #179 with 265 tests on both operating systems.

CSD now exposes `get_life_signal_snapshot()`, which opens one SQLite read transaction, verifies the shared authoritative state version and both memory/motivation projections against event history, and returns the accepted motivation-signal records from that same read snapshot. `CognitiveStoreLifeSnapshotReader` maps that result into a Life Engine `LifeSnapshot`. Goals and activity options are deliberately empty because durable goal/commitment state and trusted capability-option sourcing are not implemented yet. A cross-module test verifies a real CSD lifecycle with two voluntary encounters flows through the atomic reader and into the Life Engine snapshot. This passed in run #186 with 266 tests on both operating systems.

## Scope and limitations

This is hosted Linux and Windows verification. It does **not** establish that the code has been tested on the user's own Windows 11 / Python 3.12.14 environment.

The tests verify deterministic prototype behavior, persistence, migration, projections, Recovery invariants, observation-origin matching, return-visit linkage (including return after passive exposure), stable origin classification, and integrity checks for referenced evidence payloads. They do not prove:
- that caller-supplied adapter metadata authenticates an adapter;
- that platform/user provenance claims are truthful;
- that evidence semantically proves a real interest, need, feeling, or desire;
- that this deterministic rules layer constitutes autonomous cognition;
- Windows-specific locking, process termination, backup interruption, or power-loss behavior.

The motivation decision path remains deterministic CSD scaffolding. No model/provider, platform adapter, or external action executor is connected by this slice. The `weaken` operation records counter-evidence but does not yet calculate a numeric decrease in motivation strength.
