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
- Latest implementation/test commits: `86fe9385e2497d01a396968ebd38565eab87125d` (BLOB payload type guard and malformed JSON normalization), `b02207e5b84886666c3481d748b522ec369955c6` (BLOB/deep JSON regressions), `b38452bd4529a6f06546883343e74369e61f43d2` (Recovery event-field/timestamp normalization), `292497e66619173ca3a66ce3c5227d867ac9bb05` (timestamp regression), `f8000fd3cbeddd6357f7a35eac9e50e34d0198ef` and `1bccee2da79cd8fd5b4d90746f1c1e12eee3199f` (test-fixture corrections), `3088f6610058513d6a166784d08a496beac56907` (normalize event-family projection failures during Recovery), `4e8f8d048dab661a53e12ffac6e3d4cb6146fc16` (malformed observation projection regression), `bb4a5ce825ed460b1fdcd7b5af6aff1e17b51a43` (validate prior semantic-review event schema before duplicate acknowledgement), and `dcfbc12cef7273065b07230073c83501bd68666e` (malformed prior-review duplicate regression). Documentation commits include `c44961aa2b1a0de6132c5fcef30a3713011c3e69`, `beaf0ee64682ac3c306ea7331a261d0dfdbff79e`, `8d80a44e05ba56ae9b0d0e3266d3fd3341420998`, `8753fb66c32526bbcb4a04c83b469e49386ca6dc`, `ff172d54002f6c9437b5e01bfa68e6e83885d500`, and `3910ac10c76dd0d4bfb6a4d96c28025f2c8d1149`. GitHub Actions run #336 passed 344 tests on Ubuntu and Windows; compileall passed on both.
- Branch head before this ledger refresh: `3910ac10c76dd0d4bfb6a4d96c28025f2c8d1149` (CSD README updated with duplicate semantic-review schema validation report).
- GitHub Actions run #336 passed on Ubuntu (Python 3.12.16 / SQLite 3.46.1) and Windows (Python 3.12.10 / SQLite 3.49.1).
- `python -m compileall -q core tests` passed on both runners.
- `python -m unittest discover -s tests -v` passed: 344 tests on both Linux (4.452s) and Windows (21.881s).
- Semantic-review duplicate acknowledgement now validates the prior review's event-local schema after `get_event()` verifies canonical payload and envelope integrity. This prevents a digest-consistent but schema-invalid review (for example, an unsupported outcome) from being returned as `duplicate_review`. The shape validator is independent of mutable proposal lifecycle state, preserving legitimate retries after a later terminal decision. Regression: `tests/test_csd_semantic_review.py::test_duplicate_review_rejects_prior_event_with_invalid_review_schema`. Report: `docs/reports/csd-semantic-review-duplicate-schema-validation-report-001.md`. Code commit `bb4a5ce825ed460b1fdcd7b5af6aff1e17b51a43`; test commit `dcfbc12cef7273065b07230073c83501bd68666e`; run #336 passed 344 tests on both platforms.
- Recovery now wraps expected domain/schema/projection failures raised while applying a durable event-family projection as `CognitiveIntegrityError`, while preserving already-normalized integrity failures. Regression: `tests/test_csd_semantic_review.py::test_recovery_normalizes_invalid_observation_projection` mutates a valid observation into a malformed but canonical event and recomputes both payload and envelope digests; Recovery still fails closed with the CSD integrity exception. Report: `docs/reports/csd-recovery-projection-validation-error-normalization-report-001.md`. Code commit `3088f6610058513d6a166784d08a496beac56907`; test commit `4e8f8d048dab661a53e12ffac6e3d4cb6146fc16`; run #336 passed 344 tests on both platforms.
- Recovery now rejects SQLite BLOB values stored in the event payload text column and normalizes deeply nested JSON parser/validation failures, malformed event fields, and invalid timestamps to `CognitiveIntegrityError`. Three regressions verify both `get_event()` and Recovery reject BLOB payloads and deeply nested JSON even when content references/envelope digests are recomputed, and that Recovery normalizes an invalid event timestamp. Report: `docs/reports/csd-malformed-payload-storage-recovery-report-001.md`. Implementation commits `86fe9385e2497d01a396968ebd38565eab87125d` and `b38452bd4529a6f06546883343e74369e61f43d2`; test commits `b02207e5b84886666c3481d748b522ec369955c6` and `292497e66619173ca3a66ce3c5227d867ac9bb05`; hosted CI passed in run #333 (343 tests on Ubuntu and Windows).
- `get_event()` now rejects non-canonical stored JSON payload bytes even if payload and event-envelope digests have both been recomputed, and converts canonicalization failures (including non-finite JSON numbers) into `CognitiveIntegrityError`. This closes a gap in duplicate event/review acknowledgement: a parseable but non-canonical prior event can no longer be treated as a valid duplicate. Regression: `tests/test_csd_semantic_review.py::test_duplicate_review_rejects_noncanonical_prior_payload_even_with_matching_digests`; report: `docs/reports/csd-canonical-event-payload-read-validation-test-report-001.md`. Code commits `be8eb1c` and `9f4efa3`, test commit `57e8bf0`; hosted CI passed in run #333 (343 tests on Ubuntu and Windows). This checks canonical serialization, not writer authenticity or the full event-family schema (Recovery/projection reconciliation retain those responsibilities). `get_event()` now also normalizes malformed persisted event fields and timestamps to `CognitiveIntegrityError`; regression: `tests/test_csd_semantic_review.py::test_duplicate_event_rejects_prior_event_with_invalid_timestamp_as_integrity_error`; report: `docs/reports/csd-malformed-durable-event-read-error-normalization-report-001.md`. Code commit `346ed57`; regression commits `f31f8ca` and setup correction `3193de0`; hosted CI passed in run #333 (343 tests on Ubuntu and Windows).
- Memory and motivation decision replay now validates proposal-scoped event IDs and correlation IDs against their position in the corresponding decision stream. This closes a cross-family gap: goal decision replay already enforced these bindings, but memory/motivation replay previously relied on the decision payload and envelope digest. The same checks now run in `get_event()`, so ordinary projection reads reject rebound identity metadata before Recovery is invoked. Regressions independently rebind event IDs and correlation IDs, recompute the envelope digest, and require Recovery to reject all four mutated histories. Tests: `tests/test_csd_semantic_review.py::test_recovery_rejects_memory_decision_with_rebound_wrong_correlation`, `tests/test_csd_semantic_review.py::test_recovery_rejects_memory_decision_with_rebound_wrong_event_id`, `tests/test_csd_motivation.py::test_recovery_rejects_motivation_decision_with_rebound_wrong_correlation`, and `tests/test_csd_motivation.py::test_recovery_rejects_motivation_decision_with_rebound_wrong_event_id`; report: `docs/reports/csd-authoritative-decision-event-identity-validation-report-001.md`. Commits `ca6462b`, `98ba5d2`, `20cc866`, `85785c7`, `e5f86e7`, `c88d59d`, `6c6d734`, `023934e`, `2a4bc71`; hosted CI passed in run #333 (343 tests on Ubuntu and Windows).
- Schema v5 includes durable candidate-goal, activation, and pause/resume proposal projections, goal-version history, and latest-goal state. Legacy v1→v5, v3→v5, and v4→v5 migrations are covered by tests. The fresh v0→v1 bootstrap now explicitly rolls back partial DDL on failure; failure-injection coverage passed in hosted CI run #279. Recovery now acquires its write transaction before validating and reading the event snapshot, preventing a concurrent append from being omitted during projection rebuild; run #282 passed the deterministic two-connection regression. Recovery also re-applies the common event-envelope contract and canonical-payload check to every durable event; run #287 passed a forged reserved-namespace regression. Repeated event delivery now verifies the stored event envelope before returning a duplicate acknowledgement; run #290 passed the corrupted-prior-event regression. The shared SQLite transaction context now rolls back if COMMIT itself fails and leaves the connection active; run #293 passed a deferred-foreign-key commit-failure regression. Diagnostic and Life Engine snapshots use explicit read transactions. The diagnostic snapshot regression interleaves a committed append from a second SQLite connection and verifies that the snapshot remains on its original database view. Run #296 exposed a SQLite thread-affinity failure in the test harness; the test was simplified to create, use, and close the independent writer connection on the test thread (no production-code change was needed). Run #298 passed the corrected regression and all 332 tests on Ubuntu and Windows. Semantic-review duplicate delivery now validates the prior authoritative event through `get_event` before returning `duplicate_review`; run #302 passed a corrupted-prior-review regression.
- Goal batch acceptance is atomic; accepted candidates increment shared state_version once regardless of batch size. Stale proposals defer without rebasing. Exact source signal versions are resolved at the decision event sequence.
- The Life Engine snapshot reader includes versioned goals across candidate, active, and paused states. A narrow CSD sink can persist candidate-goal, activation, and pause/resume proposals; activity options remain empty pending a trusted capability-filtered source.
- Detailed goal-state results: `docs/reports/csd-goal-state-integration-test-report-001.md`; activation results: `docs/reports/csd-goal-activation-hosted-test-report-001.md`; goal proposal chronology: `docs/reports/csd-goal-proposal-chronology-test-report-001.md`; cross-domain proposal chronology and Recovery: `docs/reports/csd-proposal-snapshot-chronology-test-report-001.md`; fresh-schema migration rollback: `docs/reports/csd-fresh-schema-migration-rollback-test-report-001.md`; Recovery event-snapshot atomicity: `docs/reports/csd-recovery-event-snapshot-atomicity-test-report-001.md`; durable event-envelope validation: `docs/reports/csd-durable-event-envelope-validation-test-report-001.md`; duplicate delivery integrity: `docs/reports/csd-duplicate-delivery-integrity-test-report-001.md`; SQLite commit-failure rollback: `docs/reports/csd-transaction-commit-failure-rollback-test-report-001.md`; transactional read snapshot: `docs/reports/csd-transactional-read-snapshot-test-report-001.md`; semantic-review duplicate integrity: `docs/reports/csd-semantic-review-duplicate-integrity-test-report-001.md`; canonical event payload read validation: `docs/reports/csd-canonical-event-payload-read-validation-test-report-001.md`; pause/resume lifecycle: `docs/reports/csd-goal-pause-resume-hosted-test-report-001.md`. Motivation integration history: `docs/reports/csd-motivation-integration-test-report-001.md`.
- The user's local machine has not cloned this repository; Windows-local verification remains pending. `scripts/verify_windows.ps1` now runs environment reporting, compileall, and full unittest discovery in one step.
- Hosted tests do not establish adapter authenticity, semantic truth, subjective desire, or autonomous cognition.

**Resume from section 4: continue adversarial review of the shared event append/replay integrity boundary, with emphasis on event identity, duplicate delivery, projection rebuild atomicity, and malformed durable history. The 2026-11-16 follow-up added BLOB-payload type rejection, deep-JSON error normalization, and Recovery event-field/timestamp error normalization; its three regression tests are included in the 343-test suite, which passed on both Ubuntu and Windows in run #333.** The future-snapshot-version chronology guard, explicit pause/resume lifecycle slice, fresh-schema migration rollback, Recovery event-snapshot atomicity, durable event-envelope validation, duplicate-delivery integrity, SQLite commit-failure rollback, transactional read snapshot isolation, and semantic-review duplicate integrity are implemented and passed hosted CI (333 tests on Ubuntu and Windows). Canonical payload validation, malformed durable-event error normalization, proposal-scoped decision identity validation, and Recovery projection-error normalization are covered by regressions; run #333 passed 343 tests on Ubuntu and Windows. The user's own Windows 11 / Python 3.12.14 verification, process-interruption, backup/recovery, and durability checks remain open. Keep blocked/unblocked, satisfied, abandoned, superseded, and revise separate until their evidence and authority contracts are reviewed. Do not connect a real deliberator or implement external activity execution until local validation and ASM/OS-isolation boundaries are addressed.**


### 2026-11-16 follow-up — same-event-ID duplicate schema validation

- Found a gap in the shared event-ID duplicate branch: it verified the stored payload hash, canonical JSON, timestamps, and envelope digest through `get_event()`, but did not re-run the event family's own schema contract before returning `status="duplicate"`. This was distinct from the previously closed semantic-review duplicate path that uses a different event ID but the same `review_id`.
- Added `_validate_duplicate_event_shape()` and invoke it against the stored event at its original sequence before acknowledging a same-event-ID retry. Covered observation, memory proposal, grounded-memory proposal, semantic review, interaction, motivation proposal, goal batch proposal, goal activation proposal, and goal pause/resume proposal.
- Added regression `tests/test_csd_semantic_review.py::test_same_event_id_duplicate_rejects_prior_event_with_invalid_review_schema`. It mutates a stored review outcome, recomputes both payload reference and envelope digest, then retries with the original event ID; the expected result is `CognitiveIntegrityError`.
- Implementation commit: `32915b190d888aee36d584dd2987b0a4d51e953d`; regression-test commit: `6ca4e4a479d560569e8855dc646767fa0b7d6cba`.
- GitHub Actions run #339 passed on Ubuntu and Windows: **345 tests** passed on each platform; compileall and all workflow test steps passed. Report: `docs/reports/csd-same-event-id-duplicate-schema-validation-report-001.md`.
- Remaining: audit internal decision-event retry validation, cross-family event ordering, and coordinated projection/event-history corruption. User-local Windows 11 / Python 3.12.14 verification remains pending; no real model provider or external action execution is connected.


### 2026-11-16 follow-up — internal decision retry compatibility and final verification

- The duplicate-schema helper now also preserves legitimate internal decision-event retries. Before a duplicate acknowledgement it checks the decision authority source, supported outcome, and proposal-scoped event ID/correlation ID; memory and motivation decision sequence identity is additionally checked by `get_event()`.
- Added `tests/test_csd_semantic_review.py::test_same_event_id_internal_decision_retry_remains_idempotent`. The first version of this test did not satisfy the grounded-proposal review gate and therefore did not create a decision event; run #341 exposed the fixture issue. The test was corrected to submit a supported review before evaluation (commit `1b37d53061b0dd397792f7b06d353338e88f46d9`).
- Decision retry implementation commit: `6492fa8e94c8e8cb487ee163b8e8d1380537aa52`. Corrected regression-test commit: `1b37d53061b0dd397792f7b06d353338e88f46d9`.
- GitHub Actions run #342 passed on Ubuntu and Windows: **346 tests** passed on each platform, including compileall and full test discovery.
- Updated report: `docs/reports/csd-same-event-id-duplicate-schema-validation-report-001.md`.
- Remaining audit: decision payload field schemas and cross-family event ordering; coordinated corruption of projections versus event history. User-local Windows 11 / Python 3.12.14 verification remains pending.


### 2026-11-16 follow-up — strict decision event payload schemas

- Extended the duplicate-event audit to internal decision events. The duplicate validator now checks the exact payload field set for memory, motivation, goal-batch, goal-activation, and goal-pause/resume decisions, in addition to authority source, outcome, event identity, and correlation identity.
- Strengthened `_apply_decision()` so Recovery rejects missing or unsupported memory-decision fields; the other decision reducers already enforce exact field sets.
- Added `tests/test_csd_semantic_review.py::test_same_event_id_duplicate_rejects_decision_with_extra_payload_field`, which tampers with an otherwise correctly hashed and enveloped decision event and verifies that a same-ID retry is rejected as an integrity failure.
- Implementation commit: `2c48338ac9ed46e868f059f8fcf8d265fe3c1fcf`; corrected regression test commit: `2c967b49ee766a52e27423ffbba02728c9f20292`.
- Run #344 exposed only an overly specific test assertion (it expected the inner validation message rather than the normalized integrity error); the assertion was corrected. GitHub Actions run #345 passed on Ubuntu and Windows: **347 tests** passed on each platform, including compileall and full discovery.
- Report: `docs/reports/csd-same-event-id-duplicate-schema-validation-report-001.md`.
- Remaining: continue auditing deeper decision semantic/context validation, cross-family event chronology, and coordinated projection/event-history corruption. User-local Windows 11 / Python 3.12.14 verification remains pending.


### 2026-11-16 follow-up — decision event read integrity

- Extended `get_event()` to validate all five decision families: memory, motivation, goal batch, goal activation, and goal pause/resume. Reads now check exact payload field sets, authority source, proposal-scoped event ID, and correlation ID. This also protects authoritative state-version reads, which consume decision events through `get_event()`.
- Added `tests/test_csd_goals.py::test_get_event_rejects_goal_decision_with_rebound_event_id_and_valid_digest`. The test changes a goal decision event ID, recomputes the envelope digest, and verifies that a normal event read rejects the forged identity.
- Implementation commit: `83b1927d2a08991f4c31e05146f0b21fad6a7a14`; final error-contract/test assertion commits: `1dfb7d28d7eed4775a2253f019010d07b5a2fd91`, `31c77293acd2d33cd71312bad252e57cf67ef638`, `53c479cc6ec8b1f70fc0b1b2290f825d2e1001e7`.
- Runs #346–#349 exposed assertion-message mismatches after decision integrity checks moved earlier into `get_event()`; the tests were updated to the new earlier failure point. Run #350 passed on Ubuntu and Windows: **348 tests** passed on each platform, including compileall and full test discovery.
- Report: `docs/reports/csd-same-event-id-duplicate-schema-validation-report-001.md`.
- Remaining: continue deeper decision semantic/context checks, cross-family event ordering, and coordinated projection/event-history corruption. User-local Windows 11 / Python 3.12.14 verification remains pending.


### 2026-11-16 follow-up — event-family schema validation on direct reads

- Audit found that `get_event()` verified payload/envelope integrity and decision-event identity, but did not consistently rerun the event-family schema validator for ordinary observations, proposals, semantic reviews, interactions, motivation proposals, and goal proposals.
- `get_event()` now invokes the shared event-local validator used by duplicate delivery and Recovery. Applicable references are validated against earlier event sequence numbers; later lifecycle state does not invalidate historical events.
- Added `tests/test_csd_semantic_review.py::test_get_event_rejects_schema_invalid_observation_with_valid_digests`, which changes a valid observation's schema field and recomputes both payload and envelope digests before requiring direct read to fail with `CognitiveIntegrityError`.
- Implementation commits: `68956b4092742fb8aa9c2c31e37204c01134b63c`, `aa5c13fca447bf7cd64669c8df98890fe9932122`, and `c61677c04980cdafb0d51b34efd60588f3fa825d`; regression test commits: `12c059db63443bb9a848fcd0df4f1c70555cf187` and `f7698e1e0726375211a1dcd73fe99f96007a6edf`.
- Hosted CI is pending. User-local Windows 11 / Python 3.12.14 verification remains pending.
- Integrity boundary: hashes are not authenticated signatures. Rewriting an entire history into a different internally valid history and recomputing all dependent hashes cannot be detected without an independently protected checkpoint or signing key. Do not claim protection against that threat without a separate anchor design.

- Follow-up chronology audit found that event-local schema checks alone did not re-evaluate proposal `based_on.state_version` at the proposal's original position in history. The shared read validator now checks the claimed version against authoritative decisions through sequence-1; later events cannot retroactively change that historical value.
- Added `tests/test_csd_semantic_review.py::test_get_event_rejects_proposal_claiming_future_state_with_valid_digests`, which changes a proposal snapshot to a future state version and recomputes payload/envelope digests before requiring rejection.
- Chronology implementation commit: `dbfa9af2a703283249c440efa4efc6a84e322c77`; regression commit: `559494e1433257bb6501f84db26a9299ea966c5b`.
- CI remains unverified for these latest commits. Run #350 passed before this follow-up; do not extend that result to the new tests.

- Current branch comparison against `e7f47d52c3eeaa015e01cb461bb342d700f61807`: 18 commits ahead, 0 behind; no merge to `main` has been performed.
- The GitHub connector reports no workflow run or commit status for the latest follow-up commits. Run #350 remains the last verified cross-platform baseline (348 tests per OS), not verification of these additions.
- Next audit target: direct-read semantic validation of decision events, especially whether `evaluated_state_version` and `proposal_event_id` are validated against the exact earlier event history, not only field shape and proposal-scoped event identity. Design this without recursive state-version reads or trusting mutable projections.
**Resume:** verify the new direct-read regression and full cross-platform CI. Then continue cross-family chronology and projection/event-history coordinated-corruption review, keeping the distinction between detectable inconsistency and fully coherent unauthenticated history rewrite explicit.


### 2026-11-16 follow-up — decision provenance on direct reads

- Added two regression tests that rewrite a memory decision's `evaluated_state_version` or `proposal_event_id`, then recompute the payload reference and event digest. Direct `get_event()` reads must reject both histories.
- `get_event()` now validates decision provenance against earlier authoritative events: the evaluated version must equal the state version immediately before the decision; the referenced proposal must be the unique earlier proposal event for that proposal ID and must belong to the matching proposal family.
- Decision history validation reads the referenced proposal from the event log, not mutable proposal projections.
- Avoided recursive state-version validation by adding a private internal read mode used only by `_authoritative_state_version()`: it still validates decision envelope, exact schema, authority and identity, but skips the outer contextual decision check while counting prior decisions.
- Historical proposal matching uses SQLite JSON functions against stored event payloads; malformed JSON is guarded by a `CASE` expression. Runtime compatibility and full test behavior still require CI verification.
- Regression tests: `test_get_event_rejects_decision_with_rewritten_evaluated_state_version` and `test_get_event_rejects_decision_referencing_another_proposal_event`.
- Implementation commits: `44b295b170ca32b5f7f4b9b4e1055bf6c6280645` and `cc3a2ae8035aac68b61ad02fbc6e4804a2ebee4e`; test commits: `6a52756d9e1186f1950a71c504dbec0af487a971` and `6ca959bdab7d36a77c1bdcc996befa8ddbf96c8e`.
- CI and local Windows verification: pending. The last verified hosted baseline remains Run #350 (348 tests per OS), which predates these changes.
- Next: verify the new regressions and full suite, then audit remaining decision families, evidence/review reference chronology, and cross-projection/event-history corruption.


### 2026-11-16 follow-up — semantic-review history validation on direct reads

- Found that direct `get_event()` reads checked semantic-review field shape but did not independently bind `proposal_event_id` to the unique earlier grounded proposal in event history.
- Added event-history validation: resolve the unique earlier grounded proposal by `proposal_id`, read and validate it from the event log, then verify proposal digest, inference claim identity/digest, and supporting-claim lineage.
- Added regression `tests/test_csd_semantic_review.py::test_get_event_rejects_semantic_review_referencing_another_proposal_event`; it rebinds a review to another real proposal event and recomputes payload/envelope digests before requiring `CognitiveIntegrityError`.
- Implementation commits: `64222e020b7dde086c0befe98e878ec4a7053acf`, `7db787634f58b142b5b1027954fd3355fa67f9c0`; test commit: `333cae330f51e8cfc7a7dd665e960c616ef9e071`; documentation commits: `d7444f4a0de9fd749d9b4a94397f3f4a5071cd39`, `d5012d6dd9cc0cbfcf927417cb3f7fb987bb509c`.
- Verification: not yet run. Latest new regression and full suite require hosted CI; user-local Windows verification remains deferred until the project is ready to clone, per user preference.
- Next: continue adversarial review of evidence-event references in grounded proposals and interaction/motivation provenance, while confirming the full hosted workflow actually runs on the branch/PR.


### 2026-11-16 follow-up — hosted verification and historical motivation-read correction

- The first hosted runs after adding decision provenance checks exposed a real historical-read defect: `_validate_motivation_proposal()` compared old proposal events against the current `motivation_signals` projection. Later signal updates therefore made earlier valid proposals fail direct reads and decision provenance validation.
- Separated event-shape/evidence validation from current-projection checks. Append-time validation retains the live-state checks; historical direct reads validate immutable payload shape and earlier interaction evidence without judging the proposal against today's signal state.
- Two older test assertions still expected obsolete error text after the shared read validator standardized errors to `invalid durable event schema`; updated those assertions.
- Hosted GitHub Actions run #385 passed on Ubuntu and Windows: compileall passed, every focused workflow step passed, and full discovery passed **353 tests on each platform**. Run #385 is the first successful full hosted verification of the recent decision-provenance and semantic-review provenance slices.
- Earlier failed runs #369, #373, #379, #381, and #383 were investigated; failures were caused by the newly introduced historical validation coupling, a misplaced optional parameter during correction, and stale error-message assertions. These were corrected before #385.
- Semantic-review direct reads now bind the review to the unique earlier grounded proposal, verify proposal and inference-claim digests, and check supporting-claim lineage. Regression: `test_get_event_rejects_semantic_review_referencing_another_proposal_event`.
- User-local Windows 11 / Python 3.12.14 testing remains intentionally deferred until the project is ready to clone, per user preference. Hosted Windows is not a substitute.
- Next: continue reviewing grounded proposal evidence references, semantic-review chronology, and motivation interaction provenance; also verify that the decision-event validation path remains bounded for long event histories.


### 2026-11-16 follow-up — grounded-memory evidence chronology and source reads

- Direct reads and Recovery now revalidate grounded-memory evidence references against the original event sequence. If a referenced event exists, it must precede the grounded proposal; a later observation cannot be retroactively used as evidence after recomputing payload and envelope digests.
- Existing observation evidence is loaded through the normal `get_event()` integrity path, so malformed observation schemas/envelopes are rejected when a grounded proposal is read.
- Missing evidence remains a valid pending-candidate condition and is reported by evaluation as `needs_more_evidence`. Structurally durable but semantically invalid candidates (wrong source event family, mismatched quote, out-of-range text locator) remain available for deterministic rejection rather than being mistaken for corrupt history.
- Regressions: `tests/test_csd_grounded_memory.py::test_get_event_rejects_grounded_proposal_referencing_later_observation` and `test_get_event_validates_existing_grounded_source_observation`. The future-reference regression recomputes both content and envelope digests.
- Implementation commit: `03e202ce0d4c5f367cc4d2b84b02aa43dc373a1a`; test commit: `b3f08b6c0704c3d8fd0bfddd2e9c95468144ffc8`.
- GitHub Actions run #393 passed on Ubuntu and Windows: compileall, all focused workflow test groups, and complete unittest discovery all passed; **355 tests per platform**.
- User-local Windows 11 / Python 3.12.14 verification remains deferred until the project is ready to clone. Hosted Windows is not a substitute.
- Next: audit legacy memory proposal `evidence_event_ids` for the same history-order guarantee, then review cross-projection reconstruction and Recovery consistency for both legacy and grounded memory paths.


### 2026-11-16 follow-up — legacy memory evidence chronology

- Extended the evidence-history guard to legacy `memory.proposed.v1` records using `evidence_event_ids`, not just grounded-memory v2 claim evidence.
- An existing evidence event must precede the proposal. Existing observation sources are loaded through `get_event()` to verify their canonical payload, envelope digest, and observation schema. Missing references remain pending; non-observation sources remain deterministic evaluation rejections.
- Added regression `tests/test_csd_semantic_review.py::test_get_event_rejects_legacy_memory_proposal_referencing_later_observation`, which rewrites a stored proposal to cite a later observation and recomputes both payload and envelope digests.
- Implementation commit: `95e43fcda22f84bbbca1100c477434dabe6a8935`; test commit: `ce26413e331e3f8910004b403a0774d5361b6ffe`.
- GitHub Actions run #400 passed on Ubuntu and Windows: compileall, every focused workflow test group, and complete unittest discovery all passed; **356 tests per platform**.
- User-local Windows 11 / Python 3.12.14 verification remains deferred until the project is ready to clone.
- Next: audit direct decision reads for consistency between decision evidence IDs and the historical proposal's evidence set; then continue projection/Recovery checks.


### 2026-11-16 follow-up — memory decision evidence provenance on direct reads

- Direct `get_event()` reads of memory decision events now bind `evidence_event_ids` to the exact evidence set in the uniquely referenced earlier proposal. Legacy proposals use their persisted evidence list; grounded-memory v2 proposals derive the ordered unique evidence list from source-assertion claims.
- Direct reads now also apply evidence availability/type/chronology rules: missing evidence is compatible only with `needs_more_evidence` or `rejected`; existing evidence must precede the decision; non-observation sources are compatible only with a rejected outcome.
- Added regression `tests/test_csd_semantic_review.py::test_get_event_rejects_memory_decision_with_rebound_evidence_ids`; it tampers with an accepted decision's evidence list and recomputes payload and envelope digests.
- Implementation commit: `ef043337c610603e6065a7bfdf48acb2944c919e`; test commit: `bdb52b9f794776efc7bee9fbba7911fd06ea2e68`.
- GitHub Actions run #405 passed on Ubuntu and Windows: compileall, each focused test group, and full unittest discovery passed; **356 tests per platform**.
- User-local Windows 11 / Python 3.12.14 validation remains deferred until the project is ready to clone.
- Next: audit semantic-review references recorded on memory decision events against the review history visible before the decision, then check the remaining event-family evidence links.


### 2026-11-16 follow-up — decision and semantic-review history binding

- Direct memory-decision reads using grounded review policy v0.2 now recompute the semantic-review summary from immutable review events strictly before the decision's sequence. `semantic_review_event_ids`, `semantic_review_status`, policy ID/version, and `semantic_review_applied` must agree with this history.
- Direct validation also rechecks allowed review-status/outcome combinations and prevents accepting inference claims without supported review evidence. Reviews appended after a decision cannot be used retroactively.
- The review summary reads each review through the direct event validator, which independently binds it to the unique earlier grounded proposal, proposal digest, inference claim digest, and declared supporting-source lineage.
- Added regression `tests/test_csd_semantic_review.py::test_get_event_rejects_memory_decision_with_rebound_semantic_review_ids`; it removes the review reference from an accepted decision and recomputes payload/envelope digests.
- Implementation commit: `312a204a7cf0bd04719cac58e15ccbd83d77aa9a`; test commit: `b3b450cc01df62a3df6f3bcd8acfbf7720df5043`.
- GitHub Actions run #411 passed on Ubuntu and Windows: compileall, every focused suite, and full unittest discovery passed; **357 tests per platform**.
- User-local Windows 11 / Python 3.12.14 verification remains deferred until project handoff.
- Next: review remaining motivation/goal decision evidence fields and cross-projection Recovery consistency; keep all new direct-read checks sequence-bounded.


### 2026-11-16 follow-up — motivation decision evidence provenance

- Direct reads of `motivation.decided.v1` now require `evidence_event_ids` to exactly match the historical proposal's ordered `supporting_event_ids + counter_evidence_event_ids`.
- The proposal is read through the common historical event validator; referenced interaction events are checked for prior sequence, event family, schema, subject consistency, and origin constraints.
- Added regression `tests/test_csd_motivation.py::test_get_event_rejects_motivation_decision_with_rebound_evidence_ids`, which tampers with an accepted decision's evidence list and recomputes both payload and envelope digests.
- Implementation commit: `f4617e1757cfc43cfe5082fca3b916f30cbc2f5d`; test commit: `1197c1b0ae3cdbfbd560e1e8016b7fb6f1261a68`.
- GitHub Actions run #419 passed on Ubuntu and Windows: compileall, all focused test groups, and complete unittest discovery passed; **359 tests per platform**.
- User-local Windows 11 / Python 3.12.14 testing remains deferred until the project is ready to clone.
- Next: inspect goal proposal/decision history for equivalent direct-read gaps, then review coordinated projection corruption and Recovery determinism. Keep every historical check bounded by the event's original sequence.


### 2026-11-16 follow-up — goal decision history replay on direct reads

- Direct reads of goal batch, candidate activation, and pause/resume decisions now invoke the goal subsystem's sequence-ordered replay and projection reconciliation. Each decision is checked against the unique earlier proposal and the goal state/version available before the decision's original sequence.
- The replay internally reads event rows with only the recursive decision-context callback suppressed; envelope, canonical payload, event-family shape, proposal chronology, and the full deterministic goal replay remain active.
- Added three adversarial regressions: `test_get_event_rejects_goal_batch_decision_with_rewritten_transition`, `test_get_event_rejects_activation_decision_with_rewritten_goal_version`, and `test_get_event_rejects_pause_resume_decision_with_rewritten_operation`. All recompute payload and envelope digests after tampering.
- Implementation commits: `7d8220d97c390b66ec2b0a446a882301172c237d`, `e7a012e6c423caa7fc4d6db27ad35bfbe5be2d0d`; test commit: `197e7c9cd1303549268a6f45ae652f5a336417cf`.
- GitHub Actions run #428 passed on Ubuntu and Windows: compileall, every focused suite, and full unittest discovery passed; **362 tests per platform**.
- User-local Windows 11 / Python 3.12.14 testing remains deferred until the project is ready to clone.
- Next: inspect event-log replay cost and SQLite query behavior as history grows, then continue coordinated projection tampering and crash/recovery tests.


### 2026-11-16 follow-up — historical replay cost audit

- Reviewed the current historical state-version and projection-reconciliation paths in `core/csd/cognitive.py`, `core/csd/goals.py`, and `core/csd/motivation.py`.
- Found a scaling risk: history-wide validation repeatedly calls `_authoritative_state_version()`, which scans and integrity-reads accepted decision prefixes. Goal replay repeats this for each proposal/decision; memory and motivation projection reconciliation also invoke decision-context checks through ordinary `get_event()` reads. The repeated prefix work can grow quadratically with the number of decision events.
- This is a code-structure finding, not a measured performance failure. The existing suite has no large-history benchmark establishing a practical slowdown threshold.
- No runtime code changed in this audit. The full hosted GitHub Actions run #431 passed on Ubuntu and Windows; complete unittest discovery reported 362 tests passed on each platform, and compileall/focused steps passed.
- Report: `docs/reports/csd-historical-replay-cost-audit-report-001.md`.
- Next: design and implement a per-operation, sequence-ordered historical replay context that computes verified accepted-decision prefix versions once per stable SQLite snapshot. Preserve event-history authority, all five decision families, payload/envelope validation, and deterministic Recovery. Add mixed-family chronology and query-count/scaling regressions before considering any index changes.
- User-local Windows 11 / Python 3.12.14 verification remains deferred until project handoff.


### 2026-11-16 follow-up — event-history query index

- Added schema v6 with transactional migration from v5, creating composite index `idx_events_event_type_sequence` on `events(event_type, sequence)`.
- Added migration success and rollback tests, updated older v3/v4 migration fixtures to accurately remove the later-schema index, and added an `EXPLAIN QUERY PLAN` regression confirming the shared event-family/prefix query uses the index.
- Hosted GitHub Actions run #438 passed on Ubuntu and Windows. Full unittest discovery reported **364 tests per platform**; all focused steps and compileall passed. This is hosted CI, not the user's local Windows test.
- Updated `core/csd/README.md` and the historical replay cost audit report. The index improves each event-family/prefix lookup but does not solve repeated prefix aggregation; no long-history performance claim is made.
- Next: implement a per-operation, sequence-ordered historical replay context to calculate verified accepted-decision prefix versions once per stable SQLite snapshot. Preserve all five decision families and the existing direct-read/Recovery integrity checks.


- Final branch-head verification after test-name/documentation cleanup: commit `8f52c3e43f133b62b210e36fac4cc9951097aea0`; PR-triggered GitHub Actions run #444 passed on Ubuntu and Windows, with **364 tests per platform**. Run #444 is the latest verified PR workflow for this branch head.


### 2026-11-16 follow-up — runtime and platform adapter boundaries

- Added `docs/architecture/platform-and-runtime-adapter-contract.md` and indexed it from the repository README.
- Chosen direction: define stable adapter contracts now, but defer real platform connections until the corresponding core permissions and event contracts are ready. This avoids coupling CSD/identity to any one runtime, plugin, account, or SDK.
- Explicitly separated the DSH runtime adapter, SurfCore capability wrappers, model-provider adapters, and environment adapters (Bilibili, QQ, web, desktop). They are related but not interchangeable.
- The first platform stage remains **read-only Bilibili perception**. QQ starts with receive-only message ingestion; sending messages and Bilibili interactions are later, individually ASM-governed actions. Web starts read-only; desktop starts with selected observation before any local actions.
- Previously discussed `dsh-bili-watch`, `dsh-bili-whale`, MXC, and `feltstate` are recorded as research candidates only, not approved dependencies or verified security boundaries. Their source, maintenance, licence, permissions, and compatibility must be checked when their stage begins.
- The adapter document is an architecture proposal, not a frozen API or an installation instruction. No local application, platform account, credentials, or permissions were changed.
- Current CSD status remains unchanged: schema v6/index optimization is hosted-tested; repeated decision-prefix scanning remains unresolved and is the next runtime engineering task. PR #1 remains open, draft, and unmerged. The latest PR run #445 succeeded on Ubuntu and Windows; it validates the existing 364-test code state, not the new documentation's runtime behavior.
- Next: implement operation-scoped, sequence-ordered decision replay context without weakening payload/envelope validation or changing Recovery's no-external-replay rule; then add mixed-family chronology and query-count regressions. After that, add fake adapter contract tests before selecting a real Bilibili connector.


### 2026-11-16 follow-up — transaction-scoped historical replay

- Replaced repeated accepted-decision prefix scans with an immutable `_DecisionReplayContext` scoped to one SQLite transaction. It selects the five durable decision families in sequence order, verifies each event through the existing payload/envelope/local-schema read path, and stores accepted decision sequence numbers for binary-search prefix lookups.
- Memory, motivation, goal, direct-event, and Recovery validation share the context while they remain in the same read/write transaction. Standalone projection reads establish a read transaction; Recovery retains its existing writer transaction. The context is cleared on transaction exit and invalidated after every append. It is never reused across snapshots.
- Historical integrity checks were not removed. The inner scan suppresses only recursive decision-context validation; payload hashes, canonical serialization, envelope digests, local event schema, and source/identity checks remain active. Goal/motivation semantic replay and projection reconciliation remain in place.
- Added `test_mixed_decision_history_uses_one_verified_prefix_scan_per_read_transaction`. It creates accepted memory, motivation, goal-batch, activation, and pause/resume decisions, verifies the shared state version, counts one decision-family prefix selection for combined read projection validation and one for Recovery, and verifies that the context is cleared after both operations.
- Implementation commits: `3941c5f4712c148a6eaaec66ff2ddc17d9614896` (context builder and transaction cache), `d4c20fc8fe809ff31c574743a8a6d59deabd4b25` (motivation read snapshot), `8d44f4c3ab62a6242742d70fdf0086824f30e480` (goal read snapshot), `388d34d102a6d5c363f9131387e3204e64f5d432` (mixed-family regression), `e0d1a374784e6e9aaf66b956a1b96718001cb4fb` (Recovery query-count and cache-scope assertions).
- PR workflow run #458 passed on Ubuntu and Windows: **365 tests per platform**. `python -m compileall -q core tests`, focused suites, and full unittest discovery passed. This is hosted CI; owner-local Windows 11 / Python 3.12.14 verification remains deferred.
- Report: `docs/reports/csd-historical-replay-cost-audit-report-001.md`.
- The one-query-per-operation regression does not replace a long-history timing benchmark or prove all CSD replay paths are now linear. Further profiling must check other event validators and projection builders before making broader scaling claims.

### Platform integration plan established

- Added `docs/architecture/platform-and-runtime-adapter-contract.md` and linked it from the root README.
- The selected approach is to define contracts now and defer real platform integration until the relevant core permissions and event schemas are ready.
- DSH runtime integration, SurfCore capability wrappers, model-provider adapters, and environment adapters are explicitly separate layers.
- First external integration remains read-only Bilibili perception. QQ begins receive-only; sends and account mutations are later ASM-governed actions. Web begins read-only; desktop begins with selected observation before narrowly scoped local actions.
- Previously discussed Bilibili tools and desktop/security candidates are research candidates only. No plugin was newly installed, no local application/account was modified, and no credentials or permissions were changed.
- Next: inspect whether remaining replay and cross-projection paths still perform repeated scans; strengthen long-history and Recovery/concurrency tests; then build contract/fake-adapter tests before choosing and pinning a real Bilibili connector. Do not expand to real platform actions yet.


### 2026-11-16 second-round CSD optimization — decision ordinals and accepted-prefix indexes

- Extended the transaction-scoped `_DecisionReplayContext` beyond shared state-version prefixes. It now indexes all durable decision sequence numbers by event family and accepted decision sequences by family.
- Memory and motivation decision IDs are allocated from the verified per-family sequence index. Motivation accepted-transition counts now use the accepted-sequence index rather than re-counting decision prefixes.
- Expanded `test_mixed_decision_history_uses_one_verified_prefix_scan_per_read_transaction`: it now creates and accepts a second memory proposal and a second motivation proposal, verifies both family ordinals advance to `:2`, and exercises a second goal-batch decision. The second motivation proposal is created and evaluated by `add_internal_signal("replay-context-two")` before its projection is queried.
- The regression asserts no decision-family `SELECT COUNT(*)` prefix query during decision creation, combined projection reads, or Recovery; exactly one shared five-family prefix selection during the combined read operation and one during Recovery; transaction-context cleanup; and state version 8 after replay.
- Latest branch head checked through GitHub: `20ef3c5f021c2ff1d6010d993a18be024947ef5c`. PR workflow run #481 completed successfully on Ubuntu and Windows; full unittest discovery reported **365 tests passed on each platform**, and all compile/focused test steps passed.
- Run #480 (push-triggered) was not independently exposed by the available GitHub workflow-run lookup, so it is not recorded as verified here. Run #479 is an older intermediate result and is not used as evidence for the latest head.
- This is hosted CI only. User-local Windows 11 / Python 3.12.14 testing remains deferred until the project is ready to clone.
- Remaining limits: query-count regression is not a long-history wall-clock benchmark and does not prove every CSD projection or validator has linear scaling. Continue auditing cross-projection scans and Recovery behavior before declaring CSD stable.



### Additional projection-scan audit note

- Static call-path review found no additional decision-family SQL prefix COUNT path beyond the ones covered by the second-round query-count regression.
- A separate, non-prefix duplication remains: the goal projection validator calls the motivation projection validator, while some callers (including the state-snapshot path and goal proposal/decision paths) validate motivation immediately before invoking goal validation. This can repeat a full motivation projection scan inside one transaction.
- This is not a decision-history ordinal/state-version bug and does not invalidate the second-round result. Track it as a separate projection-validation deduplication candidate; preserve all independent integrity checks and add transaction-scoped regression coverage before changing call paths.


### 2026-11-16 platform source-review checkpoint

- Re-checked the official DSH upstream: current main metadata is `0.2.2-rc.3` with Node `>=24.9.0`. The exact DSH Desktop version installed locally is still unconfirmed; a previously inspected Node runtime was 24.21.0, but that alone is not a runtime compatibility test.
- Re-checked SurfCore upstream: current main is `0.8.9` at `0ce8580048d3dddb21860114edb8b115d5d79d1e`. Its README targets DSH 0.2.1-rc.2+ but says rc.3 is installable without full feature regression. The existing source assessment remains specifically pinned to SurfCore 0.8.8; do not silently generalize it to 0.8.9.
- Reviewed `Sacredbluedragon/dsh-bili-watch` main package/source: 0.4.12, MIT, Node >=22, declared DSH peer range >=0.2.0-rc.2 <0.3.0-0. Its read endpoints are promising, but its raw plugin surface also includes login/credential writes, cache cleanup, local file processing, mark-seen/output writes, and a generic URL/yt-dlp path without internal-address filtering. It is only a provisional CLI extraction-engine candidate behind a project-owned strict allowlist; do not install the raw plugin.
- Rejected `Alterssss/dsh-bili-whale` for the first stage: its README describes autonomous scheduled behavior and public/private message writes, and asks for `danger-full-access`.
- Found a CSD schema gap before real ingestion: current observation v1 is a small fixture-oriented payload and cannot preserve rich media provenance/coverage. Design backward-compatible observation v2 before connecting Bilibili.
- No plugins were installed, no account credentials were entered, and no local DSH/SurfCore settings or files were modified.
- Next: implement Stage 0 observation/capability contracts and fake-adapter tests; then define CSD observation v2 and strict Bilibili CLI wrapper tests. Keep all real network/account access disabled until those gates pass.

### Latest hosted verification refresh — 2026-11-16

- Rechecked the documented branch head `59376a2abc4ced6be3398804900956493e0398b4` through the open PR record and fetched commit metadata. PR workflow run #485 completed successfully; both `ubuntu-latest` and `windows-latest` jobs passed, including compileall, all focused test groups, and full unittest discovery. This run validates the documentation-updated branch head; the runtime/test implementation remains the code/test commit `20ef3c5f021c2ff1d6010d993a18be024947ef5c`.
- Run #480 remains unverified and is not used as evidence. Run #481 verified the code/test commit on both platforms with 365 tests each; run #485 independently confirms the later documentation-updated head.
- No user-local Windows test has been performed. The project remains un-cloned locally by the user; hosted Windows CI is not a substitute.
- PR #1 remains Draft, open, and unmerged.

### 2026-11-16 follow-up — motivation/goal projection validation deduplication

- Removed redundant standalone motivation projection checks from goal batch, activation, and pause/resume decision paths. Goal reconciliation still performs the complete motivation event/projection validation exactly once before replaying goal history.
- `get_life_signal_snapshot()` now relies on the goal validator's required motivation check rather than performing the same scan first. `get_state_snapshot()` preserves separate motivation/goal status reporting: after motivation validates successfully in the same read transaction, goal validation reuses that completed check; if motivation validation fails, goal consistency is also reported false as before.
- The reuse flag is accepted only inside an already active SQLite transaction. An out-of-transaction attempt to claim prior validation raises `RuntimeError`, preventing an unchecked standalone goal read.
- Added `test_goal_validation_reuses_motivation_projection_scan_per_transaction` covering goal decision evaluation, life snapshot, state snapshot, and rejection of out-of-transaction validation reuse.
- First regression attempt used a brittle SQLite trace-string matcher and failed on both hosted platforms in run #503; this exposed a test-instrumentation assumption, not a CSD integrity failure. The regression now counts calls to the motivation validator directly. The latest branch head at this update is `571be0ed206a5466edcba2f42bfaa088f394ed34`; no passing workflow result for this head is currently visible, so the change remains **CI pending**.
- Updated `.github/workflows/csd-cognitive-slice.yml`: added the missing `tests/test_csd_goals.py` PR path, included `adapters/**` and the two Stage 0 test files in push/PR path filters, and added dedicated adapter-contract/Bilibili-target test steps. The workflow-file change is intended to trigger a fresh hosted run.
- No user-local test has been performed. PR #1 remains Draft, open, and unmerged.

### Stage 0 adapter contract — initial code checkpoint

- Added platform-neutral dataclasses/protocols in `adapters/contracts/observation.py` for capability modes, adapter manifests, observation requests, modality coverage, untrusted evidence, and observation results.
- Added strict Bilibili target parsing in `adapters/platforms/bilibili/target.py`; the first-stage target accepts only a canonical-shaped BV identifier and rejects arbitrary URLs, short links, and local paths before extraction.
- Added focused tests in `tests/test_adapter_observation_contract.py` and `tests/test_bilibili_target.py`; the CSD workflow now includes both suites on Ubuntu and Windows.
- This is an initial contract slice, not a completed Stage 0 adapter: no real Bilibili network access, account login, DSH plugin, or external side effect is enabled. A deterministic fake adapter, adapter-to-CSD mapping, richer provenance/claim distinction, and Observation v2 event integration remain to be designed and tested.

### 2026-11-16 Stage 0 contract hardening and CI coverage

- `ObservationEvidence` now verifies that `content_digest` equals the SHA-256 digest of the UTF-8 bytes of the content field, not merely that the field has the right textual shape. Added a mismatch regression and corrected the fixture to use the real digest.
- The hosted workflow now compiles `adapters`, `core`, and `tests`; it runs the observation-contract and Bilibili target allowlist suites on both operating systems. The PR path filter now includes `tests/test_csd_goals.py`, which had been omitted, as well as the Stage 0 adapter files/tests.
- Latest code/test head before this documentation entry: `5ae72133d46833a6d6b161c5c001d9fa913d81fa`. The available PR-workflow lookup has not returned a run for the new head. Do not claim the new regression or Stage 0 suites have passed hosted CI yet. The earlier run #503 failed on the first, SQL-trace-based regression implementation; that test was replaced with a direct validator-call counter.
- PR #1 remains Draft, open, and unmerged. No user-local tests, real Bilibili network access, account login, or plugin installation occurred.

### Deterministic adapter fake and digest verification

- Added reusable in-memory `FakeObservationAdapter` under `adapters/testing/`; it records requests and returns a configured immutable observation result without network, filesystem, account, or external side effects.
- Adapter contract tests now exercise the fake adapter and verify repeated calls return the configured result while preserving untrusted evidence.
- Observation content digests are checked against SHA-256 of UTF-8 bytes of the content field; a correctly shaped but incorrect digest is rejected.
- Latest code/test head at this checkpoint: `d3d4dfc772859e1604607e8b9f9c83bbe2fd5797`. The available PR-workflow lookup still shows no run for the new head; the CSD and Stage 0 changes remain unverified by a fresh hosted run.

### Additional life-snapshot replay deduplication

- A deeper call-path check found that `get_life_signal_snapshot()` validated goal history, then called `get_goals()`, which validated the same goal history a second time. It now reads the goal projection rows directly inside the same already-validated read transaction.
- The projection-deduplication regression now counts both motivation-validator and goal-validator invocations. Goal batch evaluation, life snapshot, and state snapshot must each perform exactly one goal replay and one motivation validation. The out-of-transaction reuse guard remains covered.
- Code/test head for this change: `3efa72823f82eb0db79dcff34445484c3271aa0b`. No fresh passing hosted workflow result is visible through the available PR-run lookup; run #503 remains a failure for the earlier trace-based test and is not evidence for this revision.

### 2026-11-16 — CSD Observation v2 and adapter-to-CSD mapping

- Added `experience.observation_recorded.v2` while retaining the original v1 event and payload unchanged. Direct event reads, proposal evidence chronology, grounded-memory text evaluation, and Recovery now recognize both versions.
- V2 records adapter ID/version, platform, optional opaque account reference, external object reference, content origin (`source_provided` or `adapter_extracted`), modality, source/artifact references, source-observed and local-received timestamps, extraction method, exact UTF-8 content SHA-256, and explicit completeness/time-range/missing-range coverage.
- Both source-provided and adapter-extracted material remain untrusted. The origin field describes provenance only; it does not assert that a platform claim, caption, ASR transcript, or OCR result is true.
- Added `adapters/csd_mapping.py` to convert validated adapter evidence into deterministic CSD v2 events. The event identity is stable per adapter/observation ID; receipt time is used for the event envelope while source time remains separate in the payload.
- Grounded-memory proposal generation can now consume v2 text observations. Exact quoted spans remain mandatory; non-text observations are not passed into the text-grounded provider path.
- Added CSD v2 integration tests for mapping, stable identity, identical-delivery idempotency, conflicting-identity rejection, tamper rejection, trust flag enforcement, coverage consistency, v1/v2 Recovery, and grounded-memory use of v2 text evidence. Adapter tests also cover content-origin, extraction-method consistency, v2 manifest declaration, and rejection of unordered/overlapping missing coverage ranges.
- The CSD workflow now includes the new integration suite and path filters on Ubuntu/Windows. Hosted CI for this new revision is pending; do not claim it has passed until the corresponding Actions run is green.
- Coverage validation also rejects missing ranges outside the declared interval and rejects out-of-order or overlapping gaps at both the adapter-contract and CSD event-validation layers. A recovery-tamper regression recomputes the durable payload and envelope digests after flipping the v2 trust flag, then verifies Recovery still rejects the semantically invalid event.
- This is still a contract/mapping slice. No real Bilibili network access, account login, DSH plugin, local runtime changes, or external action was performed. V2 stores text plus source/artifact references, not raw media bytes.


### Observation v2 verification checkpoint

- The v2 integration suite now also exercises Recovery against a deliberately tampered v2 event whose payload and envelope digests have both been recomputed. Recovery must still reject the event because external evidence cannot be changed to trusted.
- Adapter and CSD coverage validators both enforce sorted, non-overlapping missing ranges contained within any declared observation interval.
- The workflow's push and pull-request path filters both include the v2 integration test; the focused suite and full unittest discovery both run in the Ubuntu/Windows matrix.
- Latest code checkpoint: `378cafdb917a388b8ea602785708aa4079909071`. Hosted verification of this latest revision is pending confirmation. The GitHub run lookup available here does not expose the push-triggered run shown in the Actions UI; no green result for this checkpoint is claimed.


### 2026-11-16 — Observation v2 CI failure analysis and compatibility fix

- Inspected Actions run #545 on both Ubuntu and Windows. The adapter contract tests passed; the focused CSD observation v2 suite exposed three compatibility defects.
- Added v2 to the legacy memory-decision evidence allowlist at proposal evaluation, decision projection, and historical decision chronology validation. This preserves the same observation-only evidence restriction; it does not admit arbitrary event types.
- Added v2 to Recovery's durable event allowlist so accepted v2 events can be replayed.
- Corrected the tamper test to assert the actual public integrity error category (`invalid durable event envelope`). The underlying trust invariant remains strict: a recomputed digest cannot make external evidence trusted.
- Fix commits: `8ee0fbdba4e0ccdfedd83edc1377e365ef0c4ce8` and `902141f1f926c59d6e83b8a3dd48d33ff61dba73`.
- The new commits trigger fresh hosted runs. Their results must be checked before claiming the v2 slice passes.


### 2026-11-18 — Bilibili read-only capability boundary (first slice)

- Confirmed from the user's Actions screenshot that Run #547 completed successfully with two matrix jobs; this is the hosted Ubuntu/Windows success signal for the v2 compatibility fix.
- Added a generic adapter policy gate, `require_observation_only`, which rejects manifests declaring presentation or side-effect capabilities.
- Added a minimal Bilibili manifest that declares only canonical video-target validation as an observation-stage capability. Its description explicitly says it does not fetch platform data.
- Added tests for the Bilibili manifest and rejection of both presentation and side-effect capability declarations. Existing target parsing continues to reject URLs, short links, local paths, and arbitrary hosts.
- Important limitation: this is a capability-declaration gate, not an operating-system sandbox. It does not by itself prevent a buggy or dishonest adapter implementation from opening a network connection. No live Bilibili client, HTTP transport, cookie/session handling, account access, download, comment/like/follow, or other external action has been implemented.
- The existing workflow already includes `adapters/**` and the Bilibili target test in its push and pull-request paths; hosted verification of this new policy slice is pending.
- PR #1 remains Draft, Open, and Unmerged.
