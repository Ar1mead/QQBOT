# Project Progress Ledger

> Repository: `Ar1mead/QQBOT`  
> Last updated: 2026-11-16 (UTC+08:00)  
> Active development branch: `feature/csd-cognitive-memory-slice`  
> Default branch: `main`  
> Merge policy: work remains on feature branches until reviewed; do not assume anything is merged to `main`.

This is the durable hand-off record for continuing work when conversation context is unavailable. Update this file whenever a meaningful work item is completed, its verification status changes, or a decision changes.

## 1. Project objective

Build a persistent AI individual, not merely a chat bot or a fixed workflow agent. The system should accumulate lived experience, form and revise memories and preferences, develop its own interests and goals, initiate activities without user prompts, and retain continuity across model/runtime/platform replacement.

The individual must be able to choose to act, wait, revise, stop, decline, or do nothing. One explicit capability is self-initiated writing: it may independently feel inclined to write a diary or other text, decide whether and when to do so, choose its subject and length, stop without saving, revisit old writing, or choose not to write. This must not become a daily quota or scheduled report.

The runtime, models, and platform adapters are replaceable infrastructure. CSD owns durable cognitive state; ASM governs external side effects. External platform content is untrusted and must never grant local machine permissions.

## 2. Current architectural direction

- **CSD** — authoritative durable cognitive state, append-only event history, accepted transitions, projections, snapshots, and recovery.
- **Cognitive services** — perception, interpretation, memory formation/retrieval/revision, self-model/personality, affect/drives, deliberation, and planning. They propose; CSD decides durable state changes.
- **Life Engine** — ongoing internal activity and deliberation. A wake-up is an opportunity to evaluate, not an instruction to perform a task.
- **ASM** — authorization and lifecycle for external side effects, attempts, dispatch, verification, retry, and recovery.
- **Runtime** — DSH is the initial runtime direction, not the identity or cognitive-state owner.
- **Adapters** — Bilibili, QQ, desktop presence, and future platforms. Begin with least-privilege, read-only perception.
- **Diary** — a distinct private-writing artifact/activity; do not conflate it with event logs or memory records.

Architecture documents are proposals unless explicitly marked as confirmed. CSD and ASM are not fully frozen specifications.

## 3. Completed work

### 3.1 Repository and architecture foundation

- [x] Established `Ar1mead/QQBOT` as the single project repository.
- [x] Created the initial project foundation branch `docs/project-foundation` and core architecture/specification/inventory documents.
- [x] Recorded that the repository is for the persistent AI individual project, not only a QQ bot.
- [x] Documented the replaceable-runtime / independent-cognitive-state principle.
- [x] Recorded autonomous journaling as a self-initiated optional activity, not a scheduled obligation.
- [x] Recorded SurfCore v0.8.8 as an integration candidate rather than the cognitive core; its fixed scheduling and diary coupling need redesign, and its default sandbox setting requires a permission review before enabling broad access.

### 3.2 CSD persistence reference spike

- [x] Created an isolated Python `sqlite3` persistence reference implementation on the feature branch `feature/csd-persistence-spike`.
- [x] Implemented append-only events/payloads, idempotent event ingestion, atomic event/projection writes, envelope digests, snapshot validation, tail replay, and safe Recovery behavior.
- [x] Added tests for duplicate events, identity conflicts, rollback, damaged snapshots/payloads, process interruption cases, concurrent writers, busy timeout, backup/restore, and tamper detection.
- [x] Recorded a historical isolated-environment result: 16 tests passed under Python 3.13.5 / SQLite 3.46.1.
- [ ] Run the reference spike on the user's Windows 11 / Python 3.12.14 environment.
- [ ] Validate Windows process termination, concurrent access, backup interruption, and actual power-loss behavior.
- [ ] Decide production SQLite journal/synchronous settings only after target-environment testing.

Reference files:
- `core/csd/store.py`
- `tests/test_csd_store.py`
- `docs/design/csd-minimal-persistence-proposal.md`
- `docs/reports/csd-persistence-spike-test-report-001.md`
- `docs/decisions/0002-csd-reference-implementation-language.md`

### 3.3 Cognitive memory slice

- [x] Added a separate `CognitiveMemoryStore` prototype with observation events, memory proposals, CSD-owned decisions, accepted-memory projection, and Recovery.
- [x] Added provider-neutral proposal submission; provider output remains pending until CSD evaluation.
- [x] Added grounded-memory v2 proposal representation with explicit quote/span and claim/evidence provenance.
- [x] Added semantic-review events and a provider-neutral review pipeline. Review opinions are attributed inputs, not authority to mutate CSD state.
- [x] Added deterministic accepted-memory retrieval filters and pagination.
- [x] Recorded known semantic limits: deterministic checks do not prove source truth or semantic entailment; no real proposal/reviewer model provider is connected.
- [x] Verify the complete cognitive-memory test suite in hosted Linux and Windows CI; [ ] verify on the user's own Windows 11 environment.

### 3.4 Life Engine and motivation proposal layer

- [x] Added provider-neutral motivational signal and goal proposal structures.
- [x] Added deliberation outcomes including an explicit `no_op`.
- [x] Added permission/prerequisite gates and ASM handoff classification; the Life Engine reference slice does not dispatch external actions.
- [x] Added evidence-grounded motivation proposal validation distinguishing user-requested actions, platform exposure/autoplay, and independently selected activities.
- [x] Added origin references, evidence non-reuse, signal versioning, and explicit contextualization rather than silently rewriting a signal.
- [x] Added tests for the Life Engine and motivation proposal validator in the repository.
- [x] Connect the Life Engine to the integrity-checked CSD snapshot reader and narrow candidate/activation proposal sink; no real deliberator/provider is connected.
- [x] Add persistent candidate/active goal state and explicit candidate→active activation; [ ] add commitment/affect state and learning/update reducers.
- [ ] Connect no real model provider yet; autonomous deliberation and goal formation remain unimplemented.


### 3.6 CSD goal activation

- [x] Reviewed `docs/design/csd-goal-activation-proposal.md` and recorded implementation constraints in Section 11.
- [x] Added schema v3→v4 migration and the rebuildable `goal_activation_proposals` projection.
- [x] Added separate activation proposal/decision event types and a CSD-authoritative candidate→active transition.
- [x] Enforced exact shared state-version and expected goal-version checks; stale proposals defer without rebasing, and non-candidate/unknown goals are rejected.
- [x] Accepted activation appends goal version n+1, preserves original goal origin and source signal-version lineage, and increments shared state_version exactly once.
- [x] Extended event-order goal reconciliation, projection consistency reporting, and deterministic Recovery to include activation history.
- [x] Added Life Engine `activate_goal` validation with expected goal version and a narrow CSD proposal sink for candidate/activation proposals. The sink does not execute activities.
- [x] Added migration, idempotency, identity-conflict, stale-version, duplicate-activation, source-signal-paused lineage, projection-tampering, Recovery, and Life Engine sink tests.
- [x] Hosted CI run #235 passed on Ubuntu and Windows: 301 total tests on each runner, including compileall. See `docs/reports/csd-goal-activation-hosted-test-report-001.md`.
- [x] Added an append-time and replay-time guard rejecting candidate/activation proposals whose `based_on.state_version` is greater than the authoritative version that existed when the proposal event was appended; two regression tests passed in hosted CI run #238 (303 tests on each platform). See `docs/reports/csd-goal-proposal-chronology-test-report-001.md`.
- [ ] Run the exact suite on the user's own Windows 11 / Python 3.12.14 environment; hosted Windows CI is not a substitute.
- [ ] Real deliberator/model provider is not connected. Goal activation is a persisted choice transition, not proof of subjective desire or autonomous motivation.
- [ ] Remaining goal lifecycle transitions and activity execution remain out of scope.


### 3.7 Remaining goal lifecycle design

- [x] Drafted `docs/design/csd-goal-lifecycle-proposal.md` to distinguish pause from blocked, define terminal states, preserve goal/source lineage, and specify version/Recovery invariants.
- [x] Selected pause/resume as the first low-risk follow-on slice in the proposal; blocked/unblocked remains dependent on trusted ASM/prerequisite evidence, while satisfied/superseded/revise require their own evidence and atomicity review.
- [x] Implemented CSD-authoritative pause/resume proposal and decision events, exact state/goal version checks, atomic goal version updates, reconciliation, Recovery, and Life Engine sink support; hosted CI run #272 passed 326 tests on Ubuntu and Windows. See `docs/reports/csd-goal-pause-resume-hosted-test-report-001.md`.
- [ ] Keep blocked, satisfied, abandoned, superseded, and revise unimplemented until their operation-specific evidence and authority contracts are reviewed.

## 4. Current work in progress — CSD motivation integration

Branch: `feature/csd-cognitive-memory-slice`

The current work connects motivation signals and goal lifecycle state to the same CSD event stream as cognitive memories. Hosted Linux and Windows CI passed the current 325-test baseline, including cross-domain proposal snapshot chronology checks in run #270.

- [x] Added `core/csd/motivation.py` with interaction provenance validation, motivation proposal validation, CSD-side deterministic decision preparation, signal lifecycle projection, retrieval, and projection consistency checks.
- [x] Added interaction events, motivation proposal events, and CSD-authoritative motivation decision events to the CSD event model.
- [x] Added a SQLite schema migration from cognitive-store schema v1 to v2 for motivation proposal/signal projections.
- [x] Added schema v2 to v3 migration for durable goal proposals, goal versions, and latest-goal projections.
- [x] Changed global `state_version` to count accepted memory and motivation state transitions, while validating the memory and motivation projections independently.
- [x] Added Recovery rebuilding for motivation proposals and signal projections from the shared event history; Recovery does not call a model/provider or execute external actions.
- [x] Added `tests/test_csd_motivation.py` with migration, provenance, idempotency, origin preservation, signal lifecycle, global version, transaction rollback, and Recovery scenarios.
- [x] Updated the workflow path filters and test step so `test_csd_motivation.py` is included for both pushes and pull requests.
- [x] Run `python -m compileall -q core tests` against the exact branch checkout (GitHub Actions, Linux and Windows runners).
- [x] Run `python -m unittest discover -s tests -v` against the exact branch checkout (325 tests passed in hosted CI run #270 after adding cross-domain future-snapshot-version regression tests).
- [x] Verify legacy v1→v3 migration and the schema v2→v3 goal-table migration.
- [x] Confirm a successful GitHub Actions run for the goal-state implementation: run #205, code/test commit `6f1ff70026c7234ae452581e1d2f01cc5416c73d`.
- [x] Review v1→v2 migration against a legacy-schema fixture and verify rollback after an injected partial-DDL failure.
- [~] Continue adversarial reconciliation of motivation, accepted-memory, candidate-goal, activated-goal, and pause/resume projections against authoritative events. Tampering and Recovery tests pass. The future-snapshot chronology gap is now closed across memory, grounded-memory, motivation, and all goal proposal families; run #270 passed 325 tests on both platforms. Broader event-schema, replay, idempotency, and migration review remains ongoing. Duplicate motivation-proposal source-validation bypass is closed; user/platform origin references are checked against observation kinds; return-visit semantics are covered by run #142; event/payload digest checks cover motivation proposals, decisions, referenced interaction evidence, and authoritative state-version reads (runs #144 and #146). Pending proposal evidence is validated before retrieval; run #148 passed. Life Engine origin derivation now uses supporting evidence only, matching CSD; pause evidence and contextual-stage restrictions also align; run #152 passed. CSD now rejects maturity requests on pause/weaken/resolve proposals. Runs #153–#155 exposed two test-fixture defects; both were corrected and run #156 passed. Life Engine/CSD origin derivation and pause/contextual-stage validation are aligned. Lifecycle tests cover create/reinforce/weaken/contextualize/pause/resolve. Broader event-schema, replay, and idempotency adversarial coverage remains. A new Life Engine snapshot-contract change now carries CSD origin_class, interest_stage, and voluntary-encounter lineage so evolved user-origin interests are not misrepresented as purely internal; regression tests passed in run #161. Runs #157–#160 exposed remaining legacy test constructors that still used raw origin strings; these have been converted to CSD origin classes. Timezone-aware voluntary-encounter timestamp validation passed in run #163. Subject identity and support/counterevidence separation passed in run #166. A follow-up adversarial check found that CSD and Life Engine compared ISO-8601 timestamp strings rather than normalized instants; equivalent instants written with different offsets could falsely count as two voluntary encounters. Both layers now normalize timestamps to UTC before maturity checks, with regression tests passed in CI run #171. The pure CSD signal mapper and real-signal mapping passed runs #178/#179; the atomic CSD signal snapshot read and Life Engine reader passed run #186; exact goal source-version lineage passed run #189; and candidate/active/terminal goal lifecycle validation passed run #192.
- [x] Run the full suite on GitHub-hosted Windows and Ubuntu runners (301 tests each; Windows Python 3.12.10 / SQLite 3.49.1 in 29.157s, Ubuntu Python 3.12.16 / SQLite 3.46.1 in 2.416s); this is not the user's own Windows 11 environment.
- [ ] Run the tests on the user's Windows environment when the repository is cloned locally.

Important implementation boundary: the current CSD motivation decision path is deterministic scaffolding. It does not yet infer authentic human-like interests, feelings, needs, or desires; it does not authenticate adapter identity; and it does not establish that the evidence source is truthful. A caller-supplied adapter string is provenance metadata, not a security credential. Do not describe this slice as autonomous motivation or a complete cognitive system.

### 3.5 CSD goal-state integration

- [x] Reviewed `docs/design/csd-goal-state-integration-proposal.md` against the actual CSD event append, state-version, projection, and Recovery paths. Implementation clarifications are recorded in Section 11; the broader proposal remains unfrozen.
- [x] Implemented the first durable CSD goal-state slice on schema v3: `life.goal_batch_proposed.v1` and CSD-reserved `life.goal_batch_decided.v1`; proposal identity/digest checks; exact historical source signal-version resolution; CSD-derived origin; atomic multi-goal candidate creation; proposal-scoped one-decision identity; shared state_version update once per accepted batch; stale deferral without rebasing; event-backed proposal/goal/version projections; deterministic Recovery; and Life Engine snapshot mapping for persisted goals.
- [x] Added `tests/test_csd_goals.py` for candidate persistence, no-op coexistence, stale deferral, missing source rejection, identity conflicts, CSD decision-path protection, user/mixed origin derivation, multi-goal atomicity, and Recovery.
- [x] Added schema v2→v3 goal projection migration and extended the v1 legacy migration test through v3.
- [x] Verified the exact implementation on GitHub-hosted Linux and Windows in Actions run #205: 281 tests passed on each platform; compileall and all individual test steps passed. Added regression checks for historical signal-version lineage after later signal revision and goal-version projection corruption/Recovery. See `docs/reports/csd-goal-state-integration-test-report-001.md`.
- [ ] Verify the project on the user's own Windows 11 / Python 3.12.14 environment when the repository is ready and cloned.
- [x] Candidate persistence and explicit candidate→active activation are implemented. [ ] Remaining lifecycle transitions, priorities, commitments, and activity execution remain out of scope.
- [x] Implemented the separate candidate→active transition from `docs/design/csd-goal-activation-proposal.md`; activation does not start an activity or grant capability and preserves original goal provenance when source signals later change. The broader proposal remains unfrozen.


## 5. Specification status and constraints

- [x] ASM-5.3 semantic working baseline was previously confirmed in conversation; preserve its distinctions and do not silently broaden retry authority.
- [ ] ASM-5.4 working interpretation U-1…U-8 has not been confirmed/frozen by the user. Treat it as provisional.
- [ ] CSD v0.1 is a working contract, not frozen.
- [ ] No comprehensive CSD/ASM test matrix has been declared complete.
- [ ] Do not turn reconstructed/non-verbatim specification text into claimed verbatim source.
- [ ] Separate normative clauses, confirmed consensus, proposed patches, engineering assumptions, and unresolved questions.

## 6. Safety, privacy, and deployment constraints

- [x] Target is local Windows 11; API inference is primary and local models are limited to lightweight supporting tasks where practical.
- [x] Avoid destructive changes to existing local installations without explicit approval.
- [x] Keep external platform content untrusted.
- [ ] Define and implement least-privilege capability boundaries and OS-level isolation before enabling file, shell, or broad network access.
- [ ] Define privacy, retention, encryption, and diary isolation. The current append-only plaintext prototype cannot claim secure erasure.
- [ ] Keep external side effects behind ASM; Recovery must never replay them.
- [ ] Bilibili understanding is incomplete until audio perception/transcription and grounded multimodal evaluation exist.

## 7. Next work queue

1. **Continue adversarial review of event schemas, replay determinism, idempotency, and projection integrity.** Memory, grounded-memory, motivation, and goal proposal families now share the append-time/replay chronology guard; continue looking for coordinated projection corruption, invalid event order, and migration/recovery edge cases.
2. **Run the exact suite on the user's Windows 11 / Python 3.12.14 machine.** A one-command script is ready at `scripts/verify_windows.ps1`; execution remains pending until the repository is cloned locally.
3. **Design blocked/unblocked only against trusted ASM/prerequisite evidence.** Pause/resume is implemented and hosted-tested. Keep satisfied, abandoned, superseded, and revise separate until their evidence, authority, and atomicity contracts are reviewed.
4. **Connect a real deliberator/provider in pending or shadow mode only after local Windows verification and further adversarial review.** The Life Engine has a CSD sink for candidate creation, activation, and pause/resume; no real model provider is connected. Keep empty `no_op` deliberations cheap and avoid manufacturing goals to satisfy a scheduler.
5. **Develop self-initiated activity and diary behavior.** No daily quota, no forced wake-up task, no requirement to save every draft.
6. **Define ASM handoff and permission model before any side-effecting platform action.**
7. **Only then build the first read-only Bilibili adapter and evaluate actual video/audio comprehension.**

## 8. Handoff rules for future sessions

1. Read this file first, then read the linked design/decision documents relevant to the current task.
2. Check the actual GitHub branch head and working files before editing; never assume the last chat's code is still current.
3. Work on the active feature branch unless the user explicitly changes that instruction. Do not merge to `main` without review/authorization.
4. After each completed work item, update this file in the same branch with:
   - status marker;
   - files/commit affected;
   - exact verification performed;
   - remaining limitations.
5. Use these status markers consistently:
   - `[x]` completed and verified to the stated scope;
   - `[~]` implemented or written, but verification incomplete;
   - `[ ]` not started or still pending;
   - `[!]` blocked, failed, or needs a decision.
6. Never mark implementation complete merely because a file was committed. Tests, hosted CI, and Windows-local verification are separate states.
7. Do not ask the user for permission at every step. Continue autonomously; ask only when a decision, local action, credential, or risk genuinely requires the user.
8. If local action is needed, explain its purpose, impact, and whether it changes files; then give one step at a time.
9. Preserve the user's preference for concise, objective technical reporting. Clearly distinguish verified facts, assumptions, and recommendations.

## 9. Current checkpoint

At the time of this update:
- Latest code/test commits: `86fe9385e2497d01a396968ebd38565eab87125d` (reject non-text durable payload storage and normalize malformed JSON failures in Recovery) and `b02207e5b84886666c3481d748b522ec369955c6` (two regressions for BLOB payloads and deeply nested JSON), building on `06c08da8a6e8ab9ad35734685a66105b137b3896` and the earlier event-identity/canonical-payload hardening commits. The hosted CI result for the accumulated pending changes is not yet verified; the previous verified baseline remains workflow run #302 (333 tests passed on Ubuntu and Windows).
- Branch head before this ledger refresh: `06c08da8a6e8ab9ad35734685a66105b137b3896` (README update documenting identity validation on durable reads).
- Hosted CI passed on Ubuntu (Python 3.12.16 / SQLite 3.46.1) and Windows (Python 3.12.10 / SQLite 3.49.1).
- `python -m compileall -q core tests` passed on both runners.
- `python -m unittest discover -s tests -v` passed: 333 tests on both Linux and Windows (Linux 2.070s; Windows 35.767s).
- Recovery now rejects SQLite BLOB values stored in the event payload text column and normalizes deeply nested JSON parser/validation failures to `CognitiveIntegrityError`. Two regressions verify both `get_event()` and Recovery reject BLOB payloads and deeply nested JSON even when the content reference and event-envelope digest are recomputed. Report: `docs/reports/csd-malformed-payload-storage-recovery-report-001.md`. Implementation commit `86fe9385e2497d01a396968ebd38565eab87125d`; test commit `b02207e5b84886666c3481d748b522ec369955c6`; hosted CI pending.
- `get_event()` now rejects non-canonical stored JSON payload bytes even if payload and event-envelope digests have both been recomputed, and converts canonicalization failures (including non-finite JSON numbers) into `CognitiveIntegrityError`. This closes a gap in duplicate event/review acknowledgement: a parseable but non-canonical prior event can no longer be treated as a valid duplicate. Regression: `tests/test_csd_semantic_review.py::test_duplicate_review_rejects_noncanonical_prior_payload_even_with_matching_digests`; report: `docs/reports/csd-canonical-event-payload-read-validation-test-report-001.md`. Code commits `be8eb1c` and `9f4efa3`, test commit `57e8bf0`; hosted CI pending. This checks canonical serialization, not writer authenticity or the full event-family schema (Recovery/projection reconciliation retain those responsibilities). `get_event()` now also normalizes malformed persisted event fields and timestamps to `CognitiveIntegrityError`; regression: `tests/test_csd_semantic_review.py::test_duplicate_event_rejects_prior_event_with_invalid_timestamp_as_integrity_error`; report: `docs/reports/csd-malformed-durable-event-read-error-normalization-report-001.md`. Code commit `346ed57`; regression commits `f31f8ca` and setup correction `3193de0`; hosted CI pending.
- Memory and motivation decision replay now validates proposal-scoped event IDs and correlation IDs against their position in the corresponding decision stream. This closes a cross-family gap: goal decision replay already enforced these bindings, but memory/motivation replay previously relied on the decision payload and envelope digest. The same checks now run in `get_event()`, so ordinary projection reads reject rebound identity metadata before Recovery is invoked. Regressions independently rebind event IDs and correlation IDs, recompute the envelope digest, and require Recovery to reject all four mutated histories. Tests: `tests/test_csd_semantic_review.py::test_recovery_rejects_memory_decision_with_rebound_wrong_correlation`, `tests/test_csd_semantic_review.py::test_recovery_rejects_memory_decision_with_rebound_wrong_event_id`, `tests/test_csd_motivation.py::test_recovery_rejects_motivation_decision_with_rebound_wrong_correlation`, and `tests/test_csd_motivation.py::test_recovery_rejects_motivation_decision_with_rebound_wrong_event_id`; report: `docs/reports/csd-authoritative-decision-event-identity-validation-report-001.md`. Commits `ca6462b`, `98ba5d2`, `20cc866`, `85785c7`, `e5f86e7`, `c88d59d`, `6c6d734`, `023934e`, `2a4bc71`; hosted CI pending.
- Schema v5 includes durable candidate-goal, activation, and pause/resume proposal projections, goal-version history, and latest-goal state. Legacy v1→v5, v3→v5, and v4→v5 migrations are covered by tests. The fresh v0→v1 bootstrap now explicitly rolls back partial DDL on failure; failure-injection coverage passed in hosted CI run #279. Recovery now acquires its write transaction before validating and reading the event snapshot, preventing a concurrent append from being omitted during projection rebuild; run #282 passed the deterministic two-connection regression. Recovery also re-applies the common event-envelope contract and canonical-payload check to every durable event; run #287 passed a forged reserved-namespace regression. Repeated event delivery now verifies the stored event envelope before returning a duplicate acknowledgement; run #290 passed the corrupted-prior-event regression. The shared SQLite transaction context now rolls back if COMMIT itself fails and leaves the connection active; run #293 passed a deferred-foreign-key commit-failure regression. Diagnostic and Life Engine snapshots use explicit read transactions. The diagnostic snapshot regression interleaves a committed append from a second SQLite connection and verifies that the snapshot remains on its original database view. Run #296 exposed a SQLite thread-affinity failure in the test harness; the test was simplified to create, use, and close the independent writer connection on the test thread (no production-code change was needed). Run #298 passed the corrected regression and all 332 tests on Ubuntu and Windows. Semantic-review duplicate delivery now validates the prior authoritative event through `get_event` before returning `duplicate_review`; run #302 passed a corrupted-prior-review regression.
- Goal batch acceptance is atomic; accepted candidates increment shared state_version once regardless of batch size. Stale proposals defer without rebasing. Exact source signal versions are resolved at the decision event sequence.
- The Life Engine snapshot reader includes versioned goals across candidate, active, and paused states. A narrow CSD sink can persist candidate-goal, activation, and pause/resume proposals; activity options remain empty pending a trusted capability-filtered source.
- Detailed goal-state results: `docs/reports/csd-goal-state-integration-test-report-001.md`; activation results: `docs/reports/csd-goal-activation-hosted-test-report-001.md`; goal proposal chronology: `docs/reports/csd-goal-proposal-chronology-test-report-001.md`; cross-domain proposal chronology and Recovery: `docs/reports/csd-proposal-snapshot-chronology-test-report-001.md`; fresh-schema migration rollback: `docs/reports/csd-fresh-schema-migration-rollback-test-report-001.md`; Recovery event-snapshot atomicity: `docs/reports/csd-recovery-event-snapshot-atomicity-test-report-001.md`; durable event-envelope validation: `docs/reports/csd-durable-event-envelope-validation-test-report-001.md`; duplicate delivery integrity: `docs/reports/csd-duplicate-delivery-integrity-test-report-001.md`; SQLite commit-failure rollback: `docs/reports/csd-transaction-commit-failure-rollback-test-report-001.md`; transactional read snapshot: `docs/reports/csd-transactional-read-snapshot-test-report-001.md`; semantic-review duplicate integrity: `docs/reports/csd-semantic-review-duplicate-integrity-test-report-001.md`; canonical event payload read validation: `docs/reports/csd-canonical-event-payload-read-validation-test-report-001.md`; pause/resume lifecycle: `docs/reports/csd-goal-pause-resume-hosted-test-report-001.md`. Motivation integration history: `docs/reports/csd-motivation-integration-test-report-001.md`.
- The user's local machine has not cloned this repository; Windows-local verification remains pending. `scripts/verify_windows.ps1` now runs environment reporting, compileall, and full unittest discovery in one step.
- Hosted tests do not establish adapter authenticity, semantic truth, subjective desire, or autonomous cognition.

**Resume from section 4: continue adversarial review of the shared event append/replay integrity boundary, with emphasis on event identity, duplicate delivery, projection rebuild atomicity, and malformed durable history. The 2026-11-16 follow-up added BLOB-payload type rejection and deep-JSON error normalization; its two regression tests are included in the pending 341-test expected suite.** The future-snapshot-version chronology guard, explicit pause/resume lifecycle slice, fresh-schema migration rollback, Recovery event-snapshot atomicity, durable event-envelope validation, duplicate-delivery integrity, SQLite commit-failure rollback, transactional read snapshot isolation, and semantic-review duplicate integrity are implemented and passed hosted CI (333 tests on Ubuntu and Windows). Canonical payload validation, malformed durable-event error normalization, and proposal-scoped decision identity validation have new regressions; hosted CI is pending (eight additional regressions beyond the 333-test baseline; expected total 341, including the two new malformed-payload regressions). The user's own Windows 11 / Python 3.12.14 verification, process-interruption, backup/recovery, and durability checks remain open. Keep blocked/unblocked, satisfied, abandoned, superseded, and revise separate until their evidence and authority contracts are reviewed. Do not connect a real deliberator or implement external activity execution until local validation and ASM/OS-isolation boundaries are addressed.**
