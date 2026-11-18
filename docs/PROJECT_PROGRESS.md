# Project Progress Ledger

> Repository: `Ar1mead/QQBOT`  
> Last updated: 2026-11-18 (UTC+08:00)  
> Active development branch: `feature/csd-cognitive-memory-slice`  
> Default branch: `main`  
> Merge policy: work remains on feature branches until reviewed; do not assume anything is merged to `main`.

This is the durable hand-off record for continuing work when conversation context is unavailable. Update this file whenever a meaningful work item is completed, its verification status changes, or a decision changes.

## Current status snapshot — 2026-11-18 19:13 UTC+08:00

- Current branch: `feature/csd-cognitive-memory-slice`; last code/test checkpoint: `d36c346ae0b4cc10cbed55814eadde74d74386a7` (Run #643 passed). Subsequent progress-ledger/design updates are documentation-only.
- Latest verified code/test commit: `d36c346ae0b4cc10cbed55814eadde74d74386a7`; Run #643 completed successfully on Ubuntu and Windows (38 steps per matrix job).
- Windows backend now contains AppContainer profile/capability helpers, handle-based runtime/temp ACL and Low Integrity label helpers, explicit environment block, Job Object limits, STARTUPINFOEX handle allowlist, suspended process launch, anonymous pipes, and bounded concurrent stdio/timeout termination.
- Windows process tests now execute both copied `cmd.exe` and copied CPython 3.12. Verified cases include runtime read-only/temp writable, host/CSD marker read denial, loopback/private-interface denial, host-positive link-local metadata and public TCP denial, child-process limit, timeout, output overflow, and Job Object kill-on-close.
- No production `WindowsAppContainerWorkerExecutor` exists; low-level launcher/stdio modules are not yet composed into the existing `WorkerExecutor` interface. No Linux Bubblewrap backend, live SurfCore ingress, or local Windows/DSH test exists.
- Python runtime verification is now complete on hosted Windows: copied CPython 3.12 launched with `-I -S -B`, standard-library/native-extension imports passed, `sys.path` stayed inside the copied runtime, parent-only secret was absent, runtime writes were denied, and the explicit plus AppContainer-managed per-profile temp paths behaved as expected.
- PR #1 remains Draft/Open/Unmerged.

---

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

> Priority reset on 2026-11-18: the older CSD/Life Engine backlog below is not the active execution order. The current security-critical path is OS-level Worker isolation before any live third-party platform ingestion.

1. **Implement the Windows AppContainer Worker backend** using audited `ctypes` declarations, narrow runtime/temp ACLs plus the temp directory's Low Integrity label, an empty AppContainer capability list, explicit inherited pipe handles, and a Job Object assigned before process resume.
2. **Add adversarial Windows tests** proving file/secret/CSD denial, network denial, child-process denial, bounded memory/output, timeout process-tree termination, and valid positive-control execution. Fail closed; no ordinary subprocess fallback.
3. **Run the Windows backend tests in GitHub Actions** and inspect both matrix job logs. Hosted CI is the available development verification path; do not ask the user to clone the repository or perform repetitive local tests. Hosted CI alone does not authorize enabling live platform ingestion.
4. **Implement Linux Bubblewrap parity** with namespaces, read-only mounts, no network, bounded temp storage, no-new-privileges/seccomp where supported, and enforceable cgroup limits; fail closed if any required control is unavailable.
5. **Run full protocol/host/CSD regressions on Ubuntu and Windows.** Only after both OS backends pass their adversarial suites may a real read-only adapter be considered.
6. **Return to SurfCore integration:** separately review the disabled-by-default upstream QQ journal patch, then its narrow read-only endpoint and CSD client; Bilibili follows with structured read-only data. Do not expose SurfCore credentials to workers or modify SurfCore upstream without a separate authorization/review.
7. Keep the remaining CSD/Life Engine work (event replay audits, blocked/unblocked lifecycle, real deliberator/provider, self-initiated diary behavior, and ASM side-effect policy) queued behind the current isolation milestone; do not represent any of it as complete.

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


### 2026-11-18 — Explicit observation adapter registry and dispatch gate

- Added `adapters/registry.py` with an explicit, host-populated adapter allowlist. There is no plugin discovery, auto-import, or automatic registration.
- Registration requires an adapter manifest and callable observation method, rejects any PRESENT/SIDE_EFFECT capability, and rejects duplicate adapter IDs.
- Dispatch is denied for unregistered IDs. Each requested modality must be explicitly declared as an `observe:<modality>` capability. The manifest is pinned at registration time so later mutation of an adapter's exposed manifest does not silently widen its admitted identity or scope.
- Returned evidence is checked against the pinned adapter ID/version/platform, requested modalities, and mandatory `untrusted=true` boundary before being returned to the caller.
- Added `tests/test_adapter_registry.py` for unregistered dispatch denial, modality scope enforcement, non-observation registration denial, duplicate IDs, manifest pinning, and evidence identity checks. The workflow now runs this focused suite and includes its path in push/PR filters.
- Security limit: this is a core-controlled application dispatch gate for trusted, host-loaded code. It is **not** a Python sandbox and cannot prevent in-process adapter code from importing sockets, opening files, or bypassing the registry. Untrusted third-party code must not be loaded into this process; actual isolation requires a separate process/container plus OS/network policy, which remains a later design task.
- Latest code/test commits for this slice: `e96b6e2b16aefe0506f969f9f88c96d490d0b412`, `2fb8a769c31894c5c01b093277438d2462dd2b0b`, `8917dc4b2b24e75b131d6d94fa231485b5d8199c`, and `761322e92ced476a9d4c18c449ab701f96438c22`. Hosted CI is pending; no local tests are claimed.


### 2026-11-18 — Adapter worker isolation threat model

- Added `docs/design/adapter-worker-isolation.md` to define the requirements for eventually running third-party adapters outside the authoritative core process.
- The draft covers secret separation, no CSD database access, typed bounded IPC, default-deny egress (including loopback/private/link-local/metadata destinations), filesystem isolation, resource/time limits, malformed output handling, and Windows/Linux verification gates.
- This is a design document only. No worker launcher or OS sandbox is claimed to exist. Until that work is implemented and tested, the in-process registry may only host trusted project-owned code.
- Registry test run #554 completed successfully on Ubuntu and Windows. The later request-type guard is included in run #555, which has now also completed successfully on both Ubuntu and Windows. Run #555 validates code/test head `761322e92ced476a9d4c18c449ab701f96438c22`; subsequent commits only updated documentation and PR text.


### 2026-11-18 — Adapter worker protocol v1 (transport envelope only)

- Added `adapters/worker_protocol.py` with distinct versioned observation request/response envelopes.
- Protocol parsing rejects unknown fields, duplicate JSON keys, invalid UTF-8, non-standard JSON constants, unsupported versions, oversized messages, out-of-bounds identifiers/targets/counts, malformed status/evidence shapes, and mismatched request/adapter identities.
- Added `tests/test_adapter_worker_protocol.py` covering deterministic round trips, unknown fields/message types, duplicate keys, unsupported versions, duplicate modalities, size bounds, response identity binding, status shapes, and non-standard JSON constants.
- Wired the focused protocol suite into the hosted Ubuntu/Windows workflow and added both registry/protocol test paths to the pull-request filter.
- Important limitation: this is only a bounded transport-envelope layer. It does not launch/authenticate a worker, provide a secure channel, semantically reconstruct/validate evidence objects, or enforce OS filesystem/network/resource restrictions. Valid JSON is not trusted evidence; host-side ObservationEvidence validation remains mandatory before CSD mapping.
- CI for this new protocol slice is pending. No local test execution is claimed.


### 2026-11-18 — Worker response evidence reconstruction

- Extended protocol handling with `response_to_observation_result`: it reconstructs wire evidence into the existing immutable observation dataclasses rather than passing arbitrary JSON dictionaries deeper into the core.
- The decoder enforces exact evidence/coverage fields, enum values, timestamp format/timezone, content SHA-256, coverage consistency, and mandatory `untrusted=true` through the observation contract constructors.
- It additionally binds each evidence item's adapter ID/version to the pinned request and rejects modalities that were not requested.
- Added tests for valid reconstruction, tampered digest, attempted trusted evidence, spoofed adapter identity, and unrequested modality.
- CI for the latest protocol/evidence changes is pending. No local test execution is claimed.


### 2026-11-18 — Fail-closed worker host orchestration

- Added `adapters/worker_host.py`: a host orchestration layer that creates typed requests, invokes an explicitly injected `WorkerExecutor`, enforces configured timeout/response-size bounds, decodes the response, and reconstructs validated observation evidence.
- Added `WorkerBackedObservationAdapter` to bridge the worker host into the existing observation-adapter contract; it additionally checks evidence platform against the registered manifest and external target against the request.
- The host rejects missing executors and has no in-process plugin fallback. Timeout, backend errors, oversized or malformed responses, and platform/target mismatches fail closed.
- Added `tests/test_adapter_worker_host.py` and wired the focused suite into the Ubuntu/Windows CI workflow. Also tightened protocol version validation to reject boolean values (Python treats `True == 1`) and added a regression test.
- Security boundary: `WorkerExecutor` is only an interface. Tests use an in-memory fake; no real subprocess launcher or OS sandbox is implemented. Production use remains blocked until a host-owned executor proves filesystem, network, secret, process, and resource restrictions on Windows and Linux.
- Hosted CI for the new host/orchestration code is pending. No local test execution is claimed.


- Executor contract clarification: a real backend must kill the worker on timeout and cap output while streaming, not merely after buffering. The host's post-return byte check cannot undo memory already allocated by an executor that ignored the cap.


- CI follow-up: run #571 exposed a transient import failure because the adapter class rename and test rename landed in separate sequential commits; the test commit briefly referenced the new symbol before the implementation commit existed. The subsequent run #572 passed Ubuntu with the renamed implementation/tests. Run #573 (latest executor-contract docstring change) has Ubuntu passed and Windows still running at the latest check. Do not treat the full two-platform gate as complete until Windows finishes.


### 2026-11-18 — SurfCore ↔ CSD integration route corrected

- Corrected the platform integration direction after rechecking the user's existing SurfCore selection: SurfCore is already the QQ/Bilibili connectivity layer; this project should not build duplicate QQ or Bilibili connectors.
- Source-reviewed the user's previously audited SurfCore v0.8.8 source at pinned commit `0deb8261afe4c31b3127759ee4de36a1439cf422`. The QQ bridge is a separate Node process consuming OneBot v11 WebSocket events and DSH event-mux output. The Bilibili toolchain has a mixture of read and write commands; some read commands still emit human-oriented console output and/or write local cache artifacts.
- Identified the integration gap: the pinned source does not yet provide a verified dedicated, read-only, versioned machine-readable feed for CSD. The bridge's broad console token is not an acceptable observation credential; private SurfCore state files are not a stable API; the public QQ feed is group-only; Bilibili CLI output is not a stable normalized event contract.
- Reviewed `plugins/surfcore/lib/platforms.js`: its capability model includes memory writes/actions and its local extension loader imports code into the DSH process. Neither is equivalent to this project's read-only observation contract or a security sandbox.
- Added `docs/design/surfcore-csd-adapter-integration.md` with the source findings, required read-only QQ cursor feed, structured Bilibili observation API, dedicated scoped credential, transport limits, implementation sequence, and acceptance gates.
- Decision: reuse SurfCore for platform connectivity; build a narrow SurfCore→Observation v2→CSD adapter. Keep QQ observation receive-only and Bilibili observation-only. All account mutations remain unavailable until individually authorized through ASM.
- Security blocker remains: current WorkerHost is orchestration/protocol plus fake executors only; no production subprocess launcher or OS sandbox exists. Do not execute untrusted plugin code through it.
- Verification: GitHub Actions run #573 (run ID `44265570787`) is now confirmed completed successfully on both Ubuntu and Windows, validating the worker-host/protocol test slice at commit `b5140f8726dcf6454f92c80e25ae31784f579bbe`. This does **not** validate a real worker sandbox or SurfCore integration.
- No local SurfCore/DSH files, settings, accounts, credentials, or plugins were modified. No live QQ/Bilibili connection was tested.
- Next implementation step: add fake SurfCore observation DTO fixtures and a deterministic mapper into the existing Observation v2/CSD path; test QQ cursor/idempotency and Bilibili provenance/coverage. Do not add live transport until the scoped read-only SurfCore interface and real worker isolation gates exist.
- PR #1 remains Draft, Open, and Unmerged; no user-local tests are claimed.


### 2026-11-18 — SurfCore DTO mapper (fake-input Stage 0 slice)

- Added `adapters/platforms/surfcore/mapping.py` and package exports. This is a pure mapper only: it accepts already-normalized, versioned SurfCore observation DTOs and converts them into the existing immutable `ObservationEvidence` contract and deterministic CSD Observation v2 events.
- Added separate receive-only/read-only manifests for QQ and Bilibili. Both expose only `observe:text`; no presentation or side-effect capability is declared.
- DTO validation is fail-closed: exact schema version and field set, platform-specific observation-kind allowlist, text-only first slice, content-size bound, source/receipt timestamps, coverage shape, and optional opaque account/artifact references. Unknown fields (including accidental credential fields) are rejected. The mapper computes the content digest and forces `untrusted=true`.
- Stable observation identity is derived from platform + SurfCore record ID. Re-delivery maps to the same CSD event identity; CSD remains responsible for durable idempotency/conflict detection.
- Added `tests/test_surfcore_observation_mapping.py` for QQ incoming/historical messages, Bilibili subtitle partial coverage, observation-only manifests, schema/kind/modality rejection, unknown-field rejection, and stable CSD event mapping.
- Updated the Ubuntu/Windows workflow path filters and added a dedicated focused test step for the SurfCore mapper. Hosted CI is pending for this new code; do not claim it passes until the new run completes.
- This does **not** connect to a running SurfCore instance, open a socket, read private SurfCore files, use credentials, or perform QQ/Bilibili actions. The fake DTO boundary is implemented; the actual scoped read-only transport is not.
- Next: use hosted CI to validate the mapper, then extend the fake DTO contract with explicit cursor replay/duplicate-conflict cases and add the eventual SurfCore read-only feed only after its separate credential and process-isolation requirements are met.


### SurfCore mapper CI status — 2026-11-18

- Workflow run #577: [GitHub Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44267016747). Ubuntu completed successfully, including the dedicated SurfCore mapper suite and full test discovery. Windows was still running at the time of this ledger update; the two-platform gate is therefore **not yet complete**.
- Run #577 checks code/workflow commit `1c0eb4d8f8caacec07597898733ad7ab15c8c93f`. Later commits in this sequence only refreshed this progress ledger; no later runtime code change is claimed.


### 2026-11-18 — QQ cursor-page validation and replay semantics

- Extended the SurfCore DTO mapper with a bounded QQ batch envelope (`schema_version`, `after_cursor`, `next_cursor`, `records`) and per-record non-negative integer cursors. Bilibili DTOs cannot carry QQ cursors.
- Added strict ordering and page-bound checks: records must be strictly increasing after the supplied checkpoint, no record may exceed `next_cursor`, duplicate record IDs are rejected, and a page is capped at 500 records. Empty pages may advance across filtered feed entries.
- Added `SurfCoreQQBatch` and `map_surfcore_qq_batch()`. They return CSD events plus a **proposed** checkpoint only; this adapter does not persist cursor state. The caller must first durably submit every event to CSD and only then persist the proposed cursor. If interrupted before checkpoint persistence, replay produces the same event IDs/payloads and CSD idempotency handles redelivery.
- Observation identity now includes platform + opaque account reference + source record ID, avoiding accidental cross-account collisions while remaining stable across replay.
- Added tests for valid ordered pages, repeated-page replay, out-of-order and duplicate cursors, duplicate record IDs, cursor regression, records beyond the page bound, foreign-platform records, invalid cursor types, and empty-page advancement.
- Hosted CI runs #578–#580 were triggered by the sequential commits; run #580 targets the complete mapper + test changes. Results are pending at the time of this update. No passing result is claimed yet.
- Still no live SurfCore connection, cursor persistence/checkpoint transaction, transport implementation, or local user test. This slice defines and tests the boundary semantics only.


### CI follow-up — QQ cursor mapper

- Run #578 and #579 failed on intermediate commits because the mapper had begun requiring QQ cursors before the matching fixture update landed. The logs show only the four QQ fixture tests missing the new cursor field; this was a sequencing failure between separate commits, not an uninvestigated runtime failure. The complete follow-up commit corrected those fixtures.
- Run #580 ([Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44267399986)) completed successfully on both Ubuntu and Windows, including the cursor batch suite and full test discovery.
- After adding two additional identity tests (account-scoped source identity and same-ID/changed-payload conflict behavior), run #581 ([Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44267521699)) has Ubuntu completed successfully; Windows is still running at this ledger update.


### 2026-11-18 — SurfCore v0.8.8 ingress contract review

- Confirmed Run #581 ([Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44267521699)) completed successfully on both Ubuntu and Windows. It includes the additional account-scoped identity and same-source-ID/changed-payload conflict tests, plus complete test discovery.
- Re-inspected the pinned SurfCore bridge source at `0deb8261afe4c31b3127759ee4de36a1439cf422`. The existing `state/qq-public-feed.jsonl` is explicitly group-only, only appends selected non-command plain-text messages after bridge policy gates, redacts/truncates content, and contains no stable source message ID/cursor or historical marker. It is not a complete QQ observation API and must not be scraped as one.
- Confirmed the bridge's normalized QQ event path already has candidate source fields: `message_id` / `msg_id` / `message_seq`, `time`, `user_id`, optional `group_id`, `sender`, and `message` segments. These can support a dedicated projection without exposing raw platform credentials.
- Confirmed the existing local console is a broad management API protected by `consoleToken`; it includes privileged send/config/session routes. The CSD adapter must not receive or reuse that credential.
- Added `docs/design/surfcore-readonly-ingress-contract-v1.md`: proposed loopback-only, dedicated-credential, GET-only interface; QQ cursor feed with private/group separation and explicit private opt-in; opaque account/conversation/sender references; source vs receipt timestamps; historical/backfill marker; Bilibili canonical-BV structured read results; explicit coverage; and privacy/security acceptance tests.
- Linked the detailed contract from `docs/design/surfcore-csd-adapter-integration.md`.
- Important alignment item: the current Python mapper is still an earlier DTO draft and does not yet carry all conversation/sender/history provenance required by the new contract. The next code step is to extend the generic ObservationEvidence/CSD payload and SurfCore DTO mapper/tests to preserve those fields before any transport implementation.
- No SurfCore source was modified, no endpoint was implemented, no private message was exported, and no live account/connection was tested. No local user files or credentials were touched.
- PR #1 remains Draft, Open, and Unmerged.


### 2026-11-18 — Preserve QQ conversation, sender, and history provenance

- Extended the platform-neutral `ObservationEvidence` contract with optional `context_kind`, `context_ref`, `actor_ref`, `source_sequence`, and `historical` fields, including type/pair/range validation.
- Extended CSD Observation v2 mapping to persist those provenance fields as structured payload properties, never concatenated into free-form message content.
- Tightened the SurfCore QQ DTO: it now requires an opaque `account_ref`, a `private|group` conversation kind, opaque conversation and sender references, a non-negative cursor, and an explicit boolean historical/backfill marker. Bilibili DTOs reject QQ-only fields.
- Added tests that verify private/group and historical provenance survives into the CSD event, and reject missing/invalid QQ provenance and QQ-specific fields on Bilibili records.
- This aligns the Python fake-input mapper with the newly documented SurfCore ingress proposal. It does not yet add the proposed `stream_ref` envelope or a transport client/server; those remain separate integration work.
- Hosted CI for these latest contract/mapper changes has been triggered by the code commits and is pending. No pass is claimed until the latest run completes on both OSes.
- Run #581 is confirmed completed successfully on Ubuntu and Windows before these new provenance-field changes.


### CI reconciliation — provenance contract changes (2026-11-18)

- Run #581 is confirmed fully successful on both platforms.
- Runs #583–#585 exposed a compatibility gap: the CSD v2 validator had an exact fixed payload-key set and did not yet permit the new optional provenance fields. This was fixed by allowing only the five explicitly named optional fields while preserving the original required v2 envelope and validating each optional value. Existing v2 payloads remain valid.
- Run #586 then caught an intermediate commit ordering issue: the mapper required QQ provenance before the matching fixture update landed. Run #587 caught two outdated assertion-message expectations after the validation became stricter. The fixtures/assertions have now been corrected.
- The latest complete mapper/test state is commit `d50a631f3916647a6e67cfe99f88df58f23f968e`, with Run #590 queued at the time of this update. Runs #588/#589 are older intermediate commits and should not be used as final verification. Await #590 for the authoritative result.
- The QQ batch now carries `stream_ref`; every record's opaque `account_ref` must match it. This prevents records from another QQ account/feed being accidentally mixed into a page. Added tests for missing/blank stream references and cross-stream records.


### Latest CI update — 2026-11-18

- Run #590 ([Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44268497654)) is the first run containing the corrected CSD validator, strict QQ provenance fixtures, and QQ stream/account binding. Ubuntu has passed; Windows is still running through the complete suite.
- Run #591 ([Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44268590651)) includes the final test refinement that a historical QQ event must set both the historical event kind and `historical=true`. Both platform jobs are running. Use #591 as the authoritative latest verification once complete.


### 2026-11-18 — Bilibili observation provenance

- Confirmed Run #591 (44268590651) completed successfully on both Ubuntu and Windows for the preceding QQ provenance implementation.
- Extended platform-neutral `ObservationEvidence` and CSD Observation v2 payloads with `actor_role`, `parent_ref`, and `content_language`, retaining structured provenance instead of flattening it into content.
- SurfCore Bilibili mapper now requires every record to identify its containing video (`context_kind=video`, `context_ref=external_ref`) and a record-kind-specific actor role: uploader, subtitle contributor, comment author, or danmaku sender. `actor_ref` remains optional when the platform does not expose a stable identity; no identity is invented from display names.
- Subtitle records may carry a BCP 47 `content_language`; comment records may carry an opaque `parent_ref`; those fields are rejected on unrelated record kinds. QQ records now explicitly identify `actor_role=sender`.
- Added tests for subtitle contributor/language preservation, comment author/thread relationships, danmaku sender role without fabricated identity, mismatched video references, wrong actor roles, invalid language tags, and CSD persistence/validation.
- Updated the read-only ingress contract with the Bilibili provenance schema and privacy rule.
- Latest changes are triggering hosted CI. No test result is claimed for these new changes until the latest run completes on both Ubuntu and Windows.
- No SurfCore runtime endpoint or platform transport was implemented; this remains DTO/CSD mapping and contract work only.


### CI reconciliation — Bilibili provenance changes (2026-11-18)

- The first Bilibili provenance runs exposed several integration gaps in intermediate commits: new DTO provenance fields had not yet been admitted by the exact-key allowlist; QQ fixtures/assertion expectations had not all been updated to require `actor_role=sender`; and CSD's new language-tag check needed a module-level `re` import.
- These were corrected in follow-up commits. The invalid-language CSD test now mutates a valid event payload so it reaches the CSD validator (rather than failing earlier in the Evidence constructor).
- Current intended field rules: Bilibili records require video context and a matching BV reference plus a kind-specific actor role; actor identity may be absent if the platform does not expose it. Parent references are comment-only; language tags are subtitle-only. All values remain untrusted source provenance.
- The newest code/test correction is commit `88c1f5ccae97d3a09a3ca86f0f1ed1c31348a53d`. The latest CI run must be checked before treating the Bilibili slice as verified; earlier failed runs are intermediate states and are not evidence of the corrected final commit.


### Additional mapper allowlist correction — 2026-11-18

- Run #603 caught one remaining schema omission: the Bilibili `context_kind` and `context_ref` fields were defined as required by the Bilibili contract but were not yet included in the exact optional-field allowlist used before platform-specific validation. They are now explicitly admitted; unknown fields remain fail-closed.
- The CSD language-tag import and invalid-language test construction were also corrected in follow-up commits. Run #603's failure is an intermediate commit state; the next run containing commit `d975b93f4ed565a932f8f389ee9250b13d7009c4` is required to verify the allowlist fix.
- Added `actor_role=sender` to the QQ contract example to match the mapper's strict DTO.


### Current verification checkpoint — Run #604

- Run #604 ([Actions](https://github.com/Ar1mead/QQBOT/actions/runs/44269594358)) is testing the mapper allowlist fix at commit `d975b93f4ed565a932f8f389ee9250b13d7009c4`. Ubuntu completed successfully; Windows reached complete test discovery with 24 prior steps successful and no failures at the last check.
- Documentation-only commits after that code commit update the integration assessment and detailed ingress contract; they do not alter the tested code.
- Do not claim the Bilibili provenance slice is fully verified until the Windows job completes successfully.


### Verification complete — Run #604

- Run #604 completed successfully on both Ubuntu and Windows, 28 steps each, with no failed steps: https://github.com/Ar1mead/QQBOT/actions/runs/44269594358
- This verifies the Bilibili context allowlist correction together with the QQ/Bilibili provenance mapping and CSD validation present at tested commit `d975b93f4ed565a932f8f389ee9250b13d7009c4`.
- The latest PR head is documentation-only commit `14edeaf05583fe093f69454f3c7a12b242909daa`; it preserves the tested code. PR #1 remains Draft / Open / Unmerged.


### 2026-11-18 — SurfCore source-path audit for real ingress

- Re-reviewed the pinned SurfCore v0.8.8 source (0deb8261afe4c31b3127759ee4de36a1439cf422) at the concrete QQ receive callbacks and Bilibili command implementations.
- QQ capture point is now grounded: src/bridge.js registers separate bot.onPrivateMessage and bot.onGroupMessage callbacks on the existing SnowLuma OneBot v11 client. Each callback filters self-authored bot messages and calls handleIncoming with the original event. That handler performs SurfCore mode/deny gates, segment-to-text conversion, message-reference extraction, and then its own memory/wake/reply processing.
- Recommended QQ design is a separate journal tap in those callbacks after self-message filtering, not a second call to handleIncoming. The tap must have independent private-message opt-in and conversation allowlisting; it must not trigger wake/reply, mutate SurfCore sessions, mark messages read, or reuse the broad console token.
- Source message_seq is a source reference, not a proven globally monotonic feed checkpoint. The feed should allocate its own durable per-stream cursor while preserving source message ID/sequence separately.
- Bilibili source review confirms candidate read commands but also concrete side effects/format problems: video-content prints human text and can fetch a GitHub README inferred from video description; subtitles writes local artifacts and prunes cache; feed --json still reads local preference/history state and writes selected picks; search prints human text. Do not parse CLI stdout or expose generic command dispatch.
- Updated docs/design/surfcore-csd-adapter-integration.md with exact source-path findings and a staged implementation decision: QQ journal/feed first, narrow Bilibili JSON read service second, then isolated host transport only after real OS worker isolation.
- No upstream SurfCore source, user-local files, credentials, accounts, or settings were modified. No live platform connection was tested.
- Existing adapter DTO mapper and cursor/replay validation remain fake-input-only. No HTTP client was added because no matching SurfCore endpoint exists yet.
- PR #1 was rechecked: Draft=true, state=open, merged=false. Latest PR head at the time of audit was 4be2882c3c3a40c423ebb376fe5d905e26d08dc0. Run #604 remains the verified two-platform code checkpoint for commit d975b93f4ed565a932f8f389ee9250b13d7009c4; subsequent changes recorded here are documentation-only. Hosted CI is not local Windows/DSH/SurfCore validation.
- Next: prepare a concrete SurfCore-side QQ observation journal specification against the two callback hooks, including private opt-in, event schema, durable cursor assignment, crash/replay semantics, and independent credential handling. Do not modify upstream SurfCore without a separate review/authorization step.


- Follow-up documentation commit `d9ccd17a092ea2c93f8771187f4745408ba8df58` adds the exact pinned-source QQ callback placement and Bilibili CLI side-effect cautions to `docs/design/surfcore-readonly-ingress-contract-v1.md`. It clarifies that the QQ feed cursor must be allocated by the new journal, not copied from OneBot message_seq, and that Bilibili CLI commands must not be exposed or parsed as a generic transport.


### 2026-11-18 — QQ observation journal implementation specification

- Added `docs/design/surfcore-qq-observation-journal-v1.md`, grounded in the pinned SurfCore v0.8.8 source commit.
- Identified the exact private/group OneBot callback insertion point, after self-message filtering and before the unchanged `handleIncoming` call. The capture path is independent of DSH mode/wake/reply processing; capture failure must not block normal chat.
- Explicitly rejected reusing `qq-public-feed.jsonl`: its group-only filtering and capped rotation/truncation semantics cannot provide the required CSD feed guarantees.
- Specified independent opt-in policy (all disabled by default; private and group allowlists separate), HMAC-derived opaque account/conversation/sender/message references, text-only v1, live-only events, single-writer durable JSONL, cursor recovery, duplicate replay identity, retention-floor/410 handling, and a dedicated loopback GET-only service with its own credential.
- Specified append+sync before capture success, startup integrity checks, no silent corruption skipping, no acknowledgement endpoint, and consumer ordering: durable CSD events first, checkpoint second.
- Corrected the success response envelope to exactly match the current Python mapper's strict batch schema; retention-floor metadata belongs only in a separate 410 error response.
- This is a design document only. No upstream SurfCore files, user-local files, credentials, accounts, or settings were modified. No live QQ connection or local runtime test occurred. No transport client was added because the upstream endpoint does not yet exist.
- Next gate: prepare a separately reviewed, narrowly scoped upstream SurfCore implementation patch for the journal module and callback tap (disabled by default), with unit tests. Only after that implementation exists should its HTTP listener and the CSD-side client be developed.

- Linked the new QQ journal specification from `docs/design/surfcore-csd-adapter-integration.md` (documentation commit `786c465e01f5dfd9ed6342fd8810137fed48b4d2`).

## SurfCore QQ journal patch blueprint — 2026-11-18

- Rechecked the pinned SurfCore v0.8.8 source at `0deb8261afe4c31b3127759ee4de36a1439cf422`.
- Verified the actual Node project conventions from its `package.json`: ESM, Node `>=22.13.0`, and standalone `scripts/test-*.mjs` test programs.
- Rechecked the precise private/group callback placement in `src/bridge.js`: after each self-message guard and before the existing `handleIncoming` call.
- Reviewed `src/owner-audit.js` as a local JSONL precedent and explicitly rejected reusing it as-is because its read/rotation semantics do not satisfy the journal's corruption and cursor guarantees.
- Added `docs/design/surfcore-qq-journal-patch-blueprint.md`, a file-level plan for a pure observation policy module, a dedicated durable journal module, minimal bridge callback taps, isolated config defaults, and focused Node regression scripts.
- The first patch is deliberately limited to policy + journal + callback capture. No HTTP listener, CSD client, Bilibili path, or account mutation is included.
- First-patch storage uses a hard byte ceiling and fails closed when full; it does not prune or truncate prior records. Segmented retention and explicit cursor-expired behavior are deferred to a separately tested follow-up rather than implemented unsafely.
- This is still a blueprint, not code. No SurfCore upstream files were changed; no QQ/DSH live connection or user-local test was performed.
- PR #1 remains Draft, Open, and Unmerged. Keep that state unchanged.

## SurfCore QQ journal executable reference slice — 2026-11-18

- Added an isolated Node ESM reference implementation under `integrations/surfcore-qq-journal/`; this is in the individual-AI repository, not in the SurfCore upstream repository.
- `observation-policy.mjs`: defaults off; private/group allowlists are independent; empty allowlists deny; explicit deny lists override; OneBot event type must be `message`; only text segments are extracted, with unsupported segments recorded as partial coverage.
- `observation-journal.mjs`: requires an injected 32-byte HMAC key and host-provided ACL hardening callback; derives domain-separated opaque refs; serializes capture and page reads; syncs each append before advancing the cursor; rebuilds cursor from the journal; repairs only an incomplete final tail; rejects corrupt complete lines; never prunes/truncates prior records when full.
- `observation-journal.test.mjs`: synthetic Node built-in test suite covers default-deny policy, private/group separation, deny overrides, self-message filtering, partial text extraction, opaque identifiers, cursor ordering, duplicate source identity, recovery, corruption, and capacity behavior.
- Added `.github/workflows/surfcore-qq-journal-reference.yml` for Node 22 on Ubuntu and Windows. The latest code/test commit is `a69e50bd6782dfe87dce6fe17dfe367b576a1fa7`; the available combined-status lookup returned no status entries, so the new workflow is **not yet verified**. Do not claim these tests passed.
- Cross-checked the record and page envelope against the exact-key Python mapper. The record fields include the mapper's required QQ provenance; `account_ref` matches `stream_ref`; the successful batch envelope is exact.
- Important limits: the reference code is not connected to SurfCore; it does not provision/store its HMAC key; the ACL callback is injected and has only a no-op test fixture; no HTTP listener, CSD HTTP client, production worker, QQ account, or DSH connection exists.
- No SurfCore upstream source was modified. No real QQ or local Windows test was performed. PR #1 remains open and must remain Draft/unmerged.

### Reference journal hardening checkpoint

- Tightened the reference policy to require explicit OneBot `post_type=message` and matching `message_type`; unsafe numeric identifiers in allow/deny lists are rejected.
- Serialized page reads through the same queue as appends to prevent a reader from observing a partially written record.
- Changed appends to use the file handle's full `writeFile` operation followed by `sync()`; cursor advancement remains after sync only.
- Recovery now uses fatal UTF-8 decoding, rejects non-canonical JSON (including duplicate-key lines), validates opaque HMAC reference shape and source-reference binding, and accepts only canonical UTC ISO timestamps.
- Capacity exhaustion is distinct from journal corruption: new capture stops, existing records remain readable, and no data is pruned.
- Latest reference code/test commit: `21ad837c240fbc524d3614a51ab6260771701ed6`. The GitHub combined-status lookup still returned no check entries; cross-platform Node 22 CI remains pending/unverified.
- These are reference files only. No SurfCore upstream patch, key provisioning, production ACL implementation, HTTP route, or real QQ connection exists.

### CI wiring and Windows fixture cleanup

- The Node 22 journal reference test was added to the existing Ubuntu/Windows CSD matrix, and both push/PR path filters now include `integrations/surfcore-qq-journal/**`.
- Removed the separate standalone journal workflow to avoid duplicate CI runs.
- Updated test fixture cleanup to close open file handles before deleting temporary directories, avoiding Windows file-lock failures.
- Latest journal test commit: `17b4cb803350a9cbb5b6fd40f70d32bddebbceb1`; CI workflow wiring commit: `8682db9375caa007123af4dda01ae9ea8dc8713d`. No check results are visible from the available status lookup yet; do not claim a pass.

### Final reference-slice review — 2026-11-18

- Source identifiers are now restricted to strings or safe integers; malformed objects/unsafe numeric values are rejected.
- Text truncation operates on Unicode code points, avoiding a cut between UTF-16 surrogate halves.
- Journal recovery now rejects invalid UTF-8 and non-canonical JSON, including duplicate-key records; opaque references and the derived source reference are validated.
- Reads and appends share one serialized queue; Windows test cleanup closes journal handles before removing temporary directories.
- Latest policy/journal/test commits: `b9192c8a53cb0084af99e118bfc28c6727e29957`, `86eaa378083499099513b1e727083cbf093c77a9`, and `5ab9a2618326ed3e6ea85058f2f1d136f268d9d8`.
- The Node 22 test step is wired into the existing Ubuntu/Windows CSD workflow. GitHub status and PR-run lookups still return no check entries for this commit. The reference suite remains **unverified**; no pass is claimed.
- PR #1 remains open and titled Draft. It has not been marked ready or merged.

## 2026-11-18 — Priority reset: OS worker isolation before live SurfCore ingress

- Reconstructed the earlier project sequence: worker protocol v1, host orchestration, and fake-executor tests were completed first; actual Windows/Linux process isolation was explicitly left as a security blocker. SurfCore DTO mapping, cursor/idempotency validation, and the QQ journal design/reference work followed, but no live transport was enabled.
- Decision: return to the missing OS-isolation foundation before enabling live platform data in CSD. Keep the SurfCore QQ journal as an independent reference artifact; do not expand it into a live upstream connection until the worker boundary is verified.
- Added `docs/design/adapter-worker-isolation-implementation-plan.md` with a Windows-first plan (AppContainer + explicit ACLs + Job Object + bounded anonymous pipes), followed by Linux parity (bubblewrap namespaces + filesystem allowlist + resource controls).
- The first worker is intentionally offline: trusted host supplies bounded DTO bytes over an anonymous pipe; the worker gets no network, no SurfCore bearer credential, no CSD store, and no inherited parent environment. A future network adapter must use a separately reviewed host-owned egress broker, not broad worker network access.
- Added an adversarial acceptance matrix for secret/CSD file visibility, filesystem writes, loopback/private/public network, child process creation, memory/CPU/process limits, timeout, output overflow, malformed responses, and crash handling.
- At the initial planning checkpoint, no Windows AppContainer launcher, Linux bubblewrap executor, ACL policy, Job Object policy, or adversarial sandbox test had been implemented. Subsequent Windows profile, empty-capability, and directory-ACL descriptor slices are recorded below; they are not a production launcher or a verified sandbox.
- Recommended next implementation slice: Windows backend prototype using Python `ctypes`, with all policy setup fail-closed; test AppContainer launch, narrow runtime/temp ACLs, Job Object assignment before resume, bounded pipes, and kill-on-timeout before attempting Linux parity.
- No SurfCore upstream code, local user files, credentials, accounts, or runtime settings were changed. PR #1 remains Draft/Open/Unmerged.

## Windows AppContainer backend — first code slice (2026-11-18)

- Added `adapters/worker_backends/` and `windows_appcontainer.py` with explicit Win64 ctypes declarations for AppContainer security capabilities, STARTUPINFOEX, process information, security attributes, Job Object limits, and CPU-rate controls.
- Added an explicit empty-capability representation and constants for suspended process creation, explicit inherited-handle lists, AppContainer security attributes, kill-on-close, active-process limit, and memory limits. No breakaway flag is provided.
- Added `tests/test_worker_windows_appcontainer_layout.py` to check Win64 structure sizes, the empty-capability default, required Job Object constants, and non-Windows fail-closed platform guard.
- Wired the layout test into the existing Ubuntu/Windows matrix. The change is expected to trigger hosted CI through the existing `adapters/**` path filter; results must be retrieved before marking it verified.
- **Strict limitation at this checkpoint:** this was the initial ABI/declaration slice. Later sections record profile SID provisioning, the empty-capability descriptor, and directory ACL helpers. Pipes, process launch, Job Object assignment, timeout/output bounds, and actual isolation remain unimplemented. No production `WorkerExecutor` exists and third-party adapter execution remains prohibited.
- Latest implementation commits: `40bfb4a272bcde3b577bcf1dd655ba6f58afafc4`, `a919dd4459ca65464aa5d748f5a28dea5da58051`, `15f15d38258f432596e4e2c75fc56bda40542c54`; workflow wiring: `eea3ca94e6dda3b67c1280747290ae987fccb534`.
- Next: retrieve the new Ubuntu/Windows CI results; then implement AppContainer SID/profile lifecycle and ACL/SACL helpers, including Low Integrity labeling only on the per-run temp directory. Do not treat this ABI slice as a sandbox.

## AppContainer profile provisioning — 2026-11-18

- Extended `adapters/worker_backends/windows_appcontainer.py` with `ensure_appcontainer_profile_sid()`: validates the documented AppContainer profile-name character/length constraints, calls `CreateAppContainerProfile` with an empty capability list, handles only the documented already-exists HRESULT by deriving the existing profile SID, converts the SID to a canonical string, and releases native SID/string allocations.
- The profile is intentionally persistent. The helper never deletes a profile, including one that may have existed before this process. A derived SID alone is not treated as proof that profile storage exists.
- Added a Windows-only CI integration test to create/reuse the dedicated test profile and verify stable SID derivation; added platform-independent profile-name validation tests.
- The helper does not yet create process tokens, configure filesystem ACLs/SACLs, assign the SID to a process, or launch a worker. It is profile provisioning only.
- Relevant Microsoft API references: `CreateAppContainerProfile`, `DeriveAppContainerSidFromAppContainerName`, `ConvertSidToStringSidW`, and `FreeSid`.
- Latest code commits: `25c4d8e4f2d81a685c6f865aa40ece05be48fdf1`, `8957bfd5e3d13ec58ad73838261c08b7047121c3`, `083cc0293123fb861ada32a922ad704731f7e259`.
- Hosted workflow/status lookup for the new commits returned no run/check entries at this refresh. **No test pass is claimed.**
- Next: implement and test ACL/SACL operations using handle-based security APIs, preserve existing ACL entries, verify the per-run directory's Low Integrity label, then construct the empty-capability `SECURITY_CAPABILITIES` for suspended process creation.

## Empty-capability AppContainer launch descriptor — 2026-11-18

- Added `EmptyAppContainerCapabilities`, a scoped owner for the native package SID and `SECURITY_CAPABILITIES` structure used with `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`.
- It converts only a canonical AppContainer package SID, explicitly sets `Capabilities = NULL` and `CapabilityCount = 0`, keeps the SID allocation alive for the native call, and releases it through `LocalFree` on context exit.
- Extended the Windows-only profile integration test to verify the zero-capability descriptor and its lifetime/closed-state behavior.
- This does **not** create a process or prove network denial. Empty capabilities are a required launch input, not a substitute for in-worker socket denial tests. Process attribute-list setup, DACL/SACL, Job Object, pipes, and launcher remain incomplete.
- Latest implementation commits: `b5918b743520020b4891ab37b137b7c07f332f96`, `584939394a694c48d458afb14f3487b7805fc0fd`.
- Workflow/status lookup remains empty at this refresh; no hosted test result is claimed.
- Next: handle-based DACL/SACL helpers and positive/negative access verification, followed by STARTUPINFOEX attribute-list construction and Job Object setup.


## Windows AppContainer directory ACL foundation — 2026-11-18

- Added `adapters/worker_backends/windows_acl.py` with handle-based directory security operations. It opens directory handles with `FILE_FLAG_OPEN_REPARSE_POINT`, checks directory/non-reparse attributes, and requests only the access rights needed for the specific DACL or label operation.
- Runtime package grant: AppContainer package SID receives inheritable file read/execute access. Per-run scratch grant: package SID receives inheritable read/write access without an execute grant.
- DACL update uses `GetSecurityInfo` + `SetEntriesInAclW` + `SetSecurityInfo(DACL_SECURITY_INFORMATION)`; unrelated existing ACEs are merged rather than replacing the whole DACL. Null DACLs are rejected. The resulting package-SID grant and inheritance flags are read back and verified.
- Temp directory Low Integrity setup uses `SetSecurityInfo(LABEL_SECURITY_INFORMATION)` with a Low Integrity SID and `SYSTEM_MANDATORY_LABEL_NO_WRITE_UP`, inheritable to child files/directories. The helper reads the label back and verifies SID, policy, and inheritance. It does not request wholesale SACL replacement or `SE_SECURITY_NAME`; it does require `WRITE_OWNER`, and any failure is fatal.
- Added Win64 layout checks for ACL-related ctypes structures and `tests/test_worker_windows_appcontainer_acl.py`; wired the test into the existing Ubuntu/Windows workflow.
- Important limits: these are directory-descriptor helpers, not a launcher or proof of effective AppContainer access. The integration test is Windows-hosted descriptor setup/read-back only. Protected descendant ACLs, ancestor reparse points, process-token access, filesystem denial from inside a worker, network denial, Job Object, pipes, and cleanup are still unverified/unimplemented.
- Hosted workflow status for this change has not yet been checked. No CI pass or local Windows test is claimed. PR #1 remains Draft, Open, and Unmerged.


## CI #618 syntax failure triage — 2026-11-18

- The first ACL commit triggered Run #618 on Ubuntu and Windows. Both jobs passed checkout, Python setup, and `compileall`, then stopped before all Python tests because the pre-existing SurfCore QQ journal test file had a malformed JavaScript string literal at line 170 (`bytes.includes("\\"101\\"")`).
- Corrected the assertion to use a single-quoted JavaScript string containing the quoted numeric ID. This is a test-source syntax repair only; it does not change journal runtime behavior or the Windows ACL implementation.
- Runs #618 and #619 are **failed** before the ACL test step because both checked out the earlier malformed JavaScript test literal. Run #620, on the syntax-fixed head, subsequently completed successfully on both Ubuntu and Windows.


## Windows AppContainer ACL descriptor hosted verification — Run #620

- Run #620 for head `b7af0afa39ee6d807df9015cbbf76f84318b3a87` completed with **Success** on both `ubuntu-latest` and `windows-latest`.
- Both jobs completed all 33 steps successfully, including Python compileall, the SurfCore QQ journal reference tests, Win64 structure-layout tests, Windows AppContainer ACL descriptor tests, focused CSD/adapter suites, and complete unittest discovery.
- The Windows ACL integration test successfully created/reused the dedicated AppContainer profile, granted the package SID read/execute on a runtime directory and read/write on a scratch directory, applied the Low Integrity no-write-up label, and passed the helper's read-back checks.
- This verifies hosted Windows directory-descriptor setup/read-back only. It does **not** prove that a launched AppContainer worker can or cannot access particular files; there is still no process launcher, no inside-worker adversarial filesystem/network test, no Job Object, and no production WorkerExecutor.
- The corrected journal assertion in the same tested head is a test syntax repair; it does not change the journal implementation.
- Hosted CI is not owner-local Windows/DSH verification. PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows Job Object resource policy — implementation slice

- Added `adapters/worker_backends/windows_job.py` with an unnamed Job Object, kill-on-close, active-process limit 1, finite per-process and job memory limits, and a CPU hard cap.
- The API requires explicit memory and CPU limits, validates them before native calls, applies the extended-limit and CPU-rate information classes, then queries the Job Object back and verifies every required flag/value. No breakaway option exists.
- Added `tests/test_worker_windows_job.py` for configuration validation, no-breakaway constants, native read-back on Windows, and non-Windows fail-closed behavior. Wired the test into the existing Ubuntu/Windows workflow.
- **Not yet a process sandbox:** no process is created or assigned to this Job Object yet. Kill-on-close has not yet been proven against a real worker; timeout supervision, suspended launch, pipe handles, and output bounds remain next.
- Hosted CI for this Job Object slice is pending. The preceding directory ACL slice passed Run #620 on both Ubuntu and Windows; see the verification section above. PR #1 remains Draft/Open/Unmerged.


## Windows Job Object policy hosted verification — Run #621

- Run #621 for code/test head `b6ce37cbbb35e8ba733af727002238eaa45cfd6a` completed with **Success** on both `ubuntu-latest` and `windows-latest`.
- Both matrix jobs completed all 34 steps successfully, including the Job Object policy test, the previously verified AppContainer ACL descriptor suite, focused CSD/adapter suites, and complete unittest discovery.
- Windows CI successfully created an unnamed Job Object, applied kill-on-close, active-process limit 1, matching finite process/job memory limits, and the requested CPU hard cap, then queried the settings back and verified them.
- This verifies Job Object configuration only. No process has yet been assigned; kill-on-close, timeout, and whole-worker termination have not yet been exercised against a real process.
- Hosted CI is not local Windows/DSH verification. PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows STARTUPINFOEX attribute-list construction — implementation slice

- Added `adapters/worker_backends/windows_startup.py` to construct the extended startup attribute list with exactly two attributes: explicit inheritable-handle allowlist and empty-capability AppContainer security descriptor.
- The helper uses the documented size-probe pattern and requires `ERROR_INSUFFICIENT_BUFFER`; it validates one to three unique valid handles and verifies each has `HANDLE_FLAG_INHERIT`. It keeps the handle array, native attribute-list buffer, and AppContainer capability lease alive.
- `STARTUPINFOEX.StartupInfo.cb` is set to the full extended structure size. The capability lease must remain open through the eventual `CreateProcessW` call.
- Added `tests/test_worker_windows_startup.py` for Windows attribute-list creation using inheritable event handles, rejection of non-inheritable/duplicate handles, invalid handle-list shapes, and non-Windows fail-closed behavior. Wired into the existing workflow.
- This slice does **not** call `CreateProcessW`, create the worker pipes, construct a minimal environment block, assign a process to the Job Object, or resume a suspended thread. No child process has been started by these tests.
- Hosted CI for this new attribute-list slice is pending. The previous Job Object slice passed Run #621 on Ubuntu and Windows; see the verification section above. PR #1 remains Draft/Open/Unmerged.


## Windows STARTUPINFOEX attribute-list hosted verification — Run #622

- Run #622 for tested code/test head `1deb39b561c9415804dda395b7c6942546ebba4d` completed with **Success** on both `ubuntu-latest` and `windows-latest`.
- Both matrix jobs completed all 35 steps successfully, including the focused STARTUPINFOEX attribute-list test and complete unittest discovery.
- The test verifies attribute-list construction, handle inheritance checks, empty-capability binding, and native buffer lifetime. No CreateProcessW call or child process is part of this test.
- The documentation-only checkpoint after the tested code is recorded in the branch history; hosted CI does not replace local Windows/DSH verification.


## STARTUPINFOEX attribute-list hosted verification result — Run #622

- Run #622 completed successfully on Ubuntu and Windows. Both jobs passed all 35 steps, including compileall, the full focused suite sequence, the new startup attribute-list tests, and complete unittest discovery.
- Verified code/test head: `1deb39b561c9415804dda395b7c6942546ebba4d`. A later docs-only commit records the result.
- PR #1 is still **Draft**, **Open**, and **Unmerged**.
- Next implementation slice: construct bounded anonymous pipes and an explicit environment block, then call `CreateProcessW` suspended with the two verified startup attributes, assign the process to the configured Job Object, and only then resume it. Any setup/assignment/resume failure must terminate and close the process/job fail-closed.
- No real process launch, worker I/O, timeout, output cap, or adversarial sandbox behavior is verified yet.


## Windows worker pipe and explicit environment preparation — implementation slice

- Added `adapters/worker_backends/windows_pipes.py`: three anonymous pipes for stdin/stdout/stderr, requested pipe buffer bounded to 4 KiB–1 MiB, parent and child endpoint roles explicit, only the three child endpoints inheritable, and all inheritance flags read back before returning.
- Added `adapters/worker_backends/windows_environment.py`: sorted double-NUL Unicode environment block, strict key allowlist, required absolute Windows system/temp paths, no ambient host environment copy, no NULs/case-colliding keys/oversize blocks, and mandatory Python safe-path/no-user-site/no-bytecode flags.
- Added focused tests for environment block shape and rejection cases, plus Windows-only pipe endpoint inheritance and cleanup tests. Both test files are wired into the existing Ubuntu/Windows CI workflow.
- These modules do **not** call `CreateProcessW`; they do not read/write pipe data, cap streamed output, supervise timeouts, assign a process to a Job Object, or resume a thread. They are preparation components, not a functioning sandbox.
- Hosted CI for these two new test suites is pending. PR #1 remains Draft/Open/Unmerged.


## Windows pipe/environment CI checkpoint — Run #623 and validation-order correction

- Run #623 reached both new focused suites on both operating systems. Windows completed the pipe-handle and environment-block tests successfully.
- Ubuntu failed the pipe helper's invalid-buffer test because `WorkerPipes.create()` performed the Windows-platform guard before validating the buffer argument. This was a testability/validation-order defect; no native pipe API was called on Ubuntu.
- Corrected the order so invalid arguments are rejected consistently before the platform guard. Valid arguments still fail closed on non-Windows.
- A new CI run is required for this correction. Do not mark Run #623 green: its Ubuntu job failed, and the Windows full job was still running at the time this checkpoint was written.


## Windows pipe/environment hosted verification — Run #624

- Run #624 for correction head `ed2239345e72ee6faa6d2af52ddbfbba99589b86` completed successfully on both Ubuntu and Windows; both jobs passed all 37 steps.
- The new pipe and environment suites passed on both platforms. Windows exercised native anonymous pipe creation and verified only the three child ends were inheritable; Ubuntu verified argument rejection occurs before the platform guard. Both platforms passed environment block validation and complete unittest discovery.
- Run #623 is not green: Windows passed its 37 steps, while Ubuntu exposed the validation-order defect described above. Run #624 verifies the corrected behavior.
- Hosted CI is not local Windows/DSH verification. PR #1 remains Draft/Open/Unmerged.

## Windows suspended AppContainer process launch — implementation slice

- Added `adapters/worker_backends/windows_process.py` with explicit executable/working-directory validation, reparse-point rejection, exact pipe-handle allowlist matching, environment-buffer revalidation, Job Object policy revalidation, standard-handle binding, and `CreateProcessW` suspended launch.
- The process is assigned to the configured Job Object before any thread is resumed. Only after assignment does the launcher close the host's child-end pipe copies and call `ResumeThread`; it requires a previous suspend count of exactly one.
- Post-creation failure handling terminates the Job Object or closes its kill-on-close handle, then requires a signaled process handle before declaring cleanup successful. It raises a fatal cleanup error rather than claiming cleanup if termination cannot be confirmed.
- Added a Windows integration test that attempts to run a harmless `cmd.exe /d /c echo WORKER_OK` inside the AppContainer and checks process exit/output. This test is **pending CI**; it is not yet evidence of successful AppContainer launch.
- No pipe I/O supervisor, output-size cap, stderr/stdout streaming loop, timeout enforcement, host-file/network/child-process adversarial tests, or production WorkerExecutor exists yet. No real platform adapter may be enabled.


## Windows AppContainer launch attempt — Run #625 failure and LOCALAPPDATA correction

- Run #625 passed the Ubuntu job. The Windows focused process-launch test reached `CreateProcessW` but failed with Win32 error 203 (`ERROR_ENVVAR_NOT_FOUND`). The launcher had supplied a valid explicit environment block but omitted `LOCALAPPDATA`.
- Microsoft documents that an AppContainer profile is accessed via `LOCALAPPDATA` or `GetAppContainerFolderPath`; the environment value is the AppContainer's OS-managed local-data directory. This is distinct from the per-run `TEMP/TMP` directory.
- Added `get_appcontainer_folder_path(sid)`, which calls `GetAppContainerFolderPath` and releases its returned buffer with `CoTaskMemFree`. The live capability lease now exposes its package SID, and the startup owner exposes that same SID.
- Added `LOCALAPPDATA` to the strict environment allowlist/required keys. The launcher now checks that it exactly matches the path returned by `GetAppContainerFolderPath` for the same startup SID and that the directory exists. `TEMP/TMP` remain separate and must match the per-run working directory.
- Updated the Windows integration test to use the API-returned path and added a Windows test for the path API. The corrected launch attempt is pending CI; do not treat Run #625 as successful.
- Reference: [Microsoft Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer) and [GetAppContainerFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-getappcontainerfolderpath).


## First real Windows AppContainer process launch verified — Run #626

- Run #626 for tested head `ee32ba513407181686dedd3038a29f4783b160b2` completed with **Success** on both `ubuntu-latest` and `windows-latest`; each matrix job completed all 38 steps.
- The focused Windows process test successfully:
  - resolved the AppContainer's LocalAppData folder using `GetAppContainerFolderPath`;
  - created a dedicated temporary working directory, granted the AppContainer SID the intended temp access, and applied the Low Integrity no-write-up label;
  - built the explicit environment block including the OS-managed AppContainer `LOCALAPPDATA`;
  - created the three anonymous pipes and restricted handle inheritance to the worker ends;
  - created the AppContainer process suspended, assigned it to the configured Job Object, then resumed it;
  - ran `cmd.exe /d /c echo WORKER_OK`, observed exit code 0, and read the expected output.
- This is the first verified end-to-end process launch in the Windows backend. It proves the launch ordering and a basic stdio round trip on GitHub's Windows runner.
- It does **not** prove host-file/CSD-marker denial, network denial, child-process denial, output-overflow termination, timeout handling, or robust concurrent stdout/stderr draining. There is still no production `WorkerExecutor` or complete I/O supervisor.
- Run #625 remains a failed earlier attempt caused by the missing `LOCALAPPDATA`; the correction is verified by Run #626.
- Hosted CI is not owner-local Windows/DSH verification. PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows bounded worker stdio supervisor — implementation slice

- Added `adapters/worker_backends/windows_worker_io.py`: concurrent stdout/stderr readers, chunked bounded stdin writer, EOF signaling by closing the parent stdin endpoint, independent stdout/stderr byte ceilings, and a wall-clock timeout.
- Limits: request ≤ 1 MiB; stdout ≤ 1 MiB; stderr ≤ 64 KiB; timeout 1–300,000 ms. Each stream is drained on its own thread so a full stderr pipe cannot deadlock stdout or stdin.
- On timeout, pipe I/O error, or output overflow, the supervisor terminates the Job Object, falls back to kill-on-close/direct process termination when needed, and requires the process handle to become signaled.
- The supervisor returns raw bounded stdout/stderr and exit code only; it does not parse worker protocol data or create CSD events.
- Updated the Windows process integration tests to use the supervisor for a bounded stdio round trip and to verify that stdout overflow terminates the worker.
- These tests are pending CI. Host-file/CSD-marker denial, network denial, child-process denial, and a dedicated timeout adversarial test remain unimplemented. No real adapter is enabled.


## Windows stdio supervisor Run #627 failure and process-exit wait correction

- Run #627 passed Ubuntu and the Windows stdout-overflow termination test. The normal Windows stdio round-trip exposed a timing assumption: stdout/stderr pipe EOF can arrive just before the process handle becomes signaled.
- The supervisor previously treated "all pipe threads reached EOF" plus "process not yet signaled on an immediate zero-time poll" as an I/O failure. This was too strict; it did not wait for process exit within the already-established deadline.
- Corrected the final phase to continue polling the process in short bounded intervals until it exits or the original wall-clock deadline expires. If the deadline expires, the Job Object is terminated and termination is confirmed before raising a timeout.
- A new CI run is required. Run #627 remains failed on Windows; its stdout-overflow test passed, but the normal round-trip test failed on this race.


## Windows bounded stdio supervisor hosted verification — Run #628

- Run #628 for tested code/test head `d43bed94e739c88f680078776fb670ffd5e5a2e8` completed with **Success** on both `ubuntu-latest` and `windows-latest`; both jobs passed all 38 steps.
- The Windows focused process suite passed:
  - bounded stdio round trip: worker input is written, stdin is closed, stdout/stderr are concurrently drained, process exit code is collected, and the expected output is returned;
  - stdout overflow: an infinite built-in command exceeds the configured 128-byte test limit and the supervisor terminates the worker Job Object; the process handle becomes signaled.
- Windows complete unittest discovery passed all **491 tests** (6 skipped, no failures). Ubuntu complete discovery and the full workflow also passed.
- Run #627 remains a failed earlier attempt. It exposed the pipe-EOF/process-exit timing race; Run #628 verifies the correction that waits for process termination until the same wall-clock deadline.
- This is hosted CI evidence only. It does not replace local Windows/DSH validation.
- Remaining sandbox proof: host secret/CSD marker denial, network denial, child-process denial, and a dedicated timeout adversarial test. No production WorkerExecutor or live SurfCore adapter is enabled.
- PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows adversarial sandbox tests added — pending CI

- Expanded `tests/test_worker_windows_process.py` with four AppContainer-internal probes:
  - read a host-user-temp secret marker and a repository-root CSD marker;
  - connect to a host-owned loopback TCP listener using `curl.exe`;
  - start a child `cmd.exe` while the Job Object active-process limit is one;
  - run a long built-in command and verify the stdio supervisor's timeout kills it.
- The tests use the actual AppContainer launch path, Job Object, and bounded stdio supervisor; they do not infer isolation from configuration flags alone.
- The new adversarial tests are **not yet run**. Do not claim filesystem/network/child-process/timeout isolation until Windows CI completes and the assertions pass.
- Loopback coverage is only one network case; private, link-local, metadata, and public destination attempts remain additional tests.


## Windows adversarial test Run #629 fixture correction

- Run #629 passed Ubuntu, loopback denial, child-process denial, timeout termination, and output-overflow termination on Windows.
- The host-file/CSD-marker test failed before its filesystem assertions because its `cmd.exe type` probe exited without reading the supervisor's stdin request; the writer then correctly received `ERROR_NO_DATA` (232) from the closed pipe.
- This is a test-fixture protocol mismatch, not evidence that the host files were readable. The supervisor intentionally treats an early stdin close as an I/O failure rather than silently accepting an unconsumed request.
- Updated command probes to consume one input line with `set /p` before running the target operation. The curl probe now uses `--data-binary @-` so it also consumes the request body.
- Run #629 remains failed on Windows due to this fixture error. A new run is required before marking the adversarial cases passed.


## Windows AppContainer adversarial suite hosted verification — Run #630

- Run #630 for tested code/test head `89e3f79965984f6d5872bd3b40787cccb89a826f` completed with **Success** on both Ubuntu and Windows; each matrix job passed all 38 steps.
- The focused Windows AppContainer suite passed the new adversarial cases:
  - a worker could not read the host-user-temp secret marker or repository-root CSD marker;
  - a worker could not connect to a host-owned loopback TCP listener;
  - a worker could not launch a child `cmd.exe` under the Job Object's active-process limit of one;
  - the worker timeout terminated the Job Object and the process handle became signaled;
  - the prior stdout-overflow termination test continued to pass;
  - the normal bounded stdin/stdout/stderr round trip continued to pass.
- Run #629 remains a failed earlier attempt. Its host-file test fixture exited before consuming stdin; Run #630 verifies the corrected fixture that reads the request line before attempting file access.
- Scope limitation: loopback denial is not exhaustive network proof. Private, link-local, cloud metadata, and public destinations still need explicit tests. Host-file marker tests cover two representative paths, not every possible host resource.
- This is hosted CI evidence only, not local Windows/DSH verification. No production WorkerExecutor or real platform adapter is enabled.
- PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows temp-write boundary test added — pending CI

- Added a positive/negative filesystem write test to the AppContainer integration suite.
- The worker must be able to create and read a file in its dedicated low-integrity temp working directory, while a write to a separate host-user temp directory must fail (the host checks that no file was created).
- This complements the existing host-secret/CSD-marker read denial tests. It is not yet verified; the next Windows CI run must pass before the write boundary is counted as tested.


## Windows temp write boundary hosted verification — Run #631

- Run #631 for tested code/test head `ccd838e03b6125a15dc64251f8d170d759fe7a7e` completed with **Success** on both Ubuntu and Windows; each matrix job passed all 38 steps.
- The focused Windows AppContainer suite now also proves the worker can create/read a file in its dedicated temp directory while an attempted write into a separate host-user temp directory leaves no file behind.
- Together with Run #630, the currently verified Windows adversarial cases cover:
  - read denial for a host-user-temp marker and repository-root CSD marker;
  - write denial to a separate host-user temp directory;
  - successful write within the dedicated Low Integrity temp directory;
  - denial of a host loopback TCP connection;
  - child-process creation blocked by Job Object active-process limit 1;
  - timeout and stdout-overflow termination with process exit confirmation;
  - normal bounded stdin/stdout/stderr exchange.
- Run #631 is hosted CI only, not local Windows/DSH validation. Private/link-local/metadata/public network destinations and broader filesystem probes remain outstanding. The Windows backend is not yet certified for untrusted production adapters.
- PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows Job Object kill-on-close adversarial test added — pending CI

- Added a test that launches a worker blocked on stdin, closes the Job Object handle while the process is still running, and requires the process handle to become signaled.
- This verifies the configured kill-on-close policy as an actual process behavior, not just a queried Job Object flag. It is pending the next Windows CI run.


## Windows Job Object kill-on-close behavior verified — Run #632

- Run #632 for tested code/test head `8c721e1fa5ac4f291c57dd59910547a9c8130fd1` completed successfully on Ubuntu and Windows; both matrix jobs passed all 38 steps.
- The Windows AppContainer test launched a worker that remained blocked waiting for stdin, closed the Job Object handle while the worker was still running, and verified that the worker process handle became signaled. This proves the configured kill-on-close behavior against a live process.
- Run #632 also retained all previously passing Windows adversarial tests: temp write boundary, host marker read denial, loopback denial, child-process limit, timeout, output overflow, and normal stdio.
- Hosted CI is not local Windows/DSH verification. Private/link-local/metadata/public network probes and broader filesystem coverage remain outstanding.
- PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Windows private-interface network denial test added — pending CI

- Added a second network denial test that discovers a private IPv4 address assigned to the Windows runner, starts a host TCP listener on that address, and first verifies the host can connect (positive control).
- The AppContainer worker then attempts the same connection using `curl.exe`; the test requires connection failure and confirms the host listener received no second connection.
- This supplements loopback denial with a real host-private-interface positive control. It is pending CI; public and metadata destinations remain separate coverage.


## Windows private-interface network denial verified — Run #633

- Run #633 for tested code/test head `9789377ca1d2e115a430cf7f1872c5290640835b` completed successfully on both Ubuntu and Windows; each matrix job passed all 38 steps.
- The new Windows private-network test found a private IPv4 address on the runner, started a TCP listener on that address, and first proved the host itself could connect. The AppContainer worker then attempted the same connection with `curl.exe`; it failed, and the server observed no second connection.
- This adds a positive-control-backed private-interface denial test to the previously passing loopback denial test. Link-local/cloud metadata and public destination attempts remain untested.
- Run #632 already verified Job Object kill-on-close against a live process; Run #631 verified the temp write boundary. These remain separate passing runs.
- Hosted CI only; no local Windows/DSH verification. PR #1 remains Draft/Open/Unmerged.


## Windows runtime ACL recursive hardening — implementation pending CI

- Code audit found the earlier runtime grant applied an inheritable ACE only to the runtime root directory. That does not prove existing files already present beneath it received access.
- Reworked `grant_runtime_read_execute` to enumerate the existing runtime tree, grant read/execute to each existing directory and file through a verified handle, set inheritable ACEs on directories for future descendants, and read each DACL back.
- Enumeration now rejects reparse points in the supplied root's ancestor chain and in every descendant; it does not follow symlinks/junctions. A hard ceiling of 100,000 entries prevents unbounded traversal.
- Added ACL tests with pre-existing nested directories/files and a Windows symlink/reparse-point rejection test. These tests are pending CI.


## Windows recursive runtime ACL hosted verification — Run #634

- Run #634 for tested head `700f4d017ae5e5351dcb1b369289ffde2a83576e` completed successfully on Ubuntu and Windows; both matrix jobs passed all 38 steps.
- The Windows ACL descriptor suite passed with a runtime tree containing pre-existing nested directories and files. The grant helper enumerated and applied/read back access for the existing objects instead of relying only on inherited ACEs at the root.
- The suite also includes a reparse-point rejection test; it skips only if the Windows runner cannot create a symlink. The workflow step passed, but the run log available to this checkpoint does not distinguish pass from conditional skip for that one case.
- This verifies ACL descriptor setup/read-back on hosted Windows, not yet that a copied runtime executable can launch under those ACLs. The next process integration test will execute a copied `cmd.exe` from a separately ACL-hardened runtime directory.
- PR #1 remains Draft/Open/Unmerged.


## Windows copied-runtime process test Run #635 fixture correction

- Run #635 verified that the copied `cmd.exe` in the separately ACL-hardened runtime directory could launch and execute commands; the runtime read/execute-only positive/negative write test passed.
- Two other tests failed because their context-manager destructuring still expected four yielded values after the helper began returning five (it now also returns the runtime directory path).
- The resulting fixture exception interrupted normal cleanup and left the copied executable locked, producing a secondary temporary-directory cleanup error. This is a test fixture mismatch; the process launch and runtime directory test passed.
- Updated the two stale tuple destructuring sites to accept the fifth value. Run #635 remains failed on Windows; a new run is required to verify cleanup and the full suite.


## Windows copied runtime executable and recursive ACL integration verified — Run #636

- Run #636 for tested head `1b062b27c36f830007e67206e34c46b67ee4f274` completed with **Success** on both Ubuntu and Windows; each matrix job passed all 38 steps.
- The Windows process integration helper now copies `cmd.exe` into a separate runtime directory, applies recursive read/execute ACLs to that directory and its existing executable, and launches the copied executable inside the AppContainer.
- The runtime read/execute-only test passed: the worker executed from the copied runtime directory, could not create a file there, and could still create a file in the separately Low-Integrity-labeled temp directory.
- All previously passing adversarial cases also passed, including host marker read denial, host temp write denial, loopback/private-interface network denial, child-process limit, timeout, output overflow, and Job Object kill-on-close.
- Run #635 remains a failed earlier fixture attempt caused by stale tuple unpacking; Run #636 verifies the correction and cleanup.
- Hosted CI only; no local Windows/DSH verification. Link-local/cloud metadata/public network attempts remain outstanding. PR #1 remains Draft/Open/Unmerged.


## Ephemeral AppContainer profile lifecycle — implementation pending CI

- Added `EphemeralAppContainerProfile`, which creates a uniquely named AppContainer profile for one worker invocation, obtains its SID and OS-managed `LOCALAPPDATA` path, and deletes that profile on close.
- Unlike the persistent CI profile helper, the ephemeral helper never reuses an existing profile. If creation or path validation fails, it attempts to delete the just-created profile before raising.
- The caller must close/terminate the worker process and release its process/job/pipe handles before closing the profile. This avoids cross-run AppContainer local-data persistence.
- Added Windows tests for unique names/SIDs, path existence, deletion, and closed-object behavior. The lifecycle tests are pending CI; the production executor does not use the helper yet.


## Ephemeral AppContainer profile lifecycle hosted verification — Run #637

- Run #637 for tested head `76f9b576b5490ba5392df6ec0a0e71a809302fb0` completed successfully on both Ubuntu and Windows; each matrix job passed all 38 steps.
- The Windows AppContainer layout suite verified that the ephemeral profile helper creates unique profile names and SIDs, returns an existing OS-managed LocalAppData folder, deletes the profile on close, removes the folder, and rejects re-entry after close.
- The process-launch integration suite and all previous Windows adversarial tests also passed.
- The current process integration fixture still uses the persistent CI profile; next it will be switched to the ephemeral owner so the full launch lifecycle proves profile deletion after process/job/pipe cleanup.
- Hosted CI only; no local Windows/DSH verification. PR #1 remains Draft/Open/Unmerged.


## Windows process integration switched to ephemeral profiles — pending CI

- Updated the Windows process test harness to create one unique AppContainer profile per worker session, use that profile's SID and LocalAppData path, and delete it after the process, Job Object, startup attributes, and pipes have been closed.
- This exercises profile lifecycle in the actual launch path rather than testing profile creation/deletion separately.
- The change is pending CI. A failed profile deletion must fail the test rather than leave a persistent per-run profile behind.


## Windows process launch with ephemeral profile verified — Run #638

- Run #638 for tested head `4de9553e89adf73c8100d831f1307b402d9b5216` completed successfully on Ubuntu and Windows; both matrix jobs passed all 38 steps.
- The Windows process integration now creates a unique AppContainer profile for every worker session, uses its SID and OS-managed LocalAppData path, and deletes the profile only after the process, Job Object, startup attributes, and pipes have been closed.
- The complete Windows process suite passed with this ephemeral lifecycle, including copied runtime execution, runtime write denial/temp write allowance, host file read/write denial, loopback/private network denial, child-process restriction, timeout, output overflow, and kill-on-close.
- This is still hosted CI, not local Windows/DSH verification. Public and metadata network probes remain outstanding. No production WorkerExecutor or live SurfCore adapter is enabled.
- PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Current next actions after Run #638

The Windows backend has a verified process launch and bounded stdio path, but it is not yet a production WorkerExecutor. Keep the following order:

1. Extend network denial probes to link-local/cloud metadata and public destinations using connection-only tests and host-side positive controls where available; do not send metadata HTTP requests or application payloads.
2. Exercise the actual Python runtime tree under recursive read/execute ACLs (not only the copied `cmd.exe` representative). Verify isolated interpreter flags, standard-library imports, explicit environment, and no writes into runtime.
3. Implement a host-owned `WindowsAppContainerWorkerExecutor` that fulfills the existing `WorkerExecutor` contract using ephemeral profiles, runtime ACLs, low-integrity temp, zero AppContainer capabilities, Job Object, explicit inherited pipes, bounded stdio, timeout, and strict response decoding. It must fail closed on any setup or cleanup failure.
4. Add adversarial checks for the real Python worker and rerun full Windows/Ubuntu CI.
5. Implement Linux Bubblewrap parity and its adversarial suite.
6. Only after both backends pass should live SurfCore QQ ingress be resumed; Bilibili remains later.

Current hard boundary: no production WorkerExecutor, no untrusted adapter execution, no live SurfCore connection, and no local Windows/DSH verification. PR #1 remains Draft/Open/Unmerged.


## AppContainer profile deletion retry hardening — pending CI

- Microsoft documents that a failed `DeleteAppContainerProfile` call leaves profile state indeterminate and recommends calling it again to complete deletion.
- Updated the ephemeral profile owner to retry deletion once after a failed HRESULT. It marks the profile closed only after a successful deletion; two failures raise and fail the worker cleanup path.
- Added unit tests for retry-success and fail-closed-after-two-failures behavior. Pending CI.


## AppContainer profile deletion retry verified — Run #639

- Run #639 for tested head `1a177d2ef73a5b32b0900fa115d922366d3f33be` completed successfully on both Windows and Ubuntu; each matrix job passed all 38 steps.
- The new unit tests verified that a failed `DeleteAppContainerProfile` HRESULT triggers one retry, that a successful retry completes cleanup, and that two failed attempts raise rather than falsely marking the profile closed.
- The Windows ephemeral profile layout and process integration tests also passed. The process tests continue to create a fresh profile per worker and delete it after all process/job/pipe handles close.
- Microsoft documents that failed profile deletion leaves state indeterminate and should be retried; see [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile).
- This remains hosted CI only, not local Windows/DSH verification. The backend still has no production WorkerExecutor; full Python runtime and remaining network destination probes are outstanding.
- PR #1 remains **Draft**, **Open**, and **Unmerged**.


## Python runtime isolation probe added — pending CI

- Extended the Windows AppContainer process test harness to build a minimal copied CPython runtime in the dedicated read-only runtime directory: the base interpreter executable, top-level runtime DLLs, standard-library `Lib`, extension-module `DLLs`, and optional versioned stdlib zip/isolated-path file.
- Added a real Python worker probe launched with `-I -S -B`. It reads the bounded request from stdin; imports `json`, `pathlib`, `ssl`, and `sqlite3`; checks isolated/no-site/no-bytecode flags; checks that `sys.path` stays within the copied runtime; confirms a parent-only secret is absent; proves runtime writes fail while temp writes succeed.
- This is an integration test of the copied Python runtime under the existing AppContainer controls, not yet a production executor or a complete adapter protocol run. CI is pending.
- Added the Windows backend test files to the workflow's pull-request path filters so test-only changes also trigger the matrix.


## Run #640 — Python runtime test exposed AppContainer TEMP redirection

- Ubuntu completed successfully. Windows process integration failed only in the new Python runtime test; the other Windows process tests passed.
- The copied CPython 3.12 executable started inside the AppContainer and imported `json`, `pathlib`, `ssl`, and `sqlite3`. The traceback occurred when the probe tried to write to the process's `TEMP` path: Windows exposed an AppContainer-scoped path under the ephemeral profile, but that temp subdirectory had not yet been created.
- The failure is not evidence that Python or its native extensions cannot run. It revealed that the effective AppContainer `TEMP` path differs from the host-created scratch directory. The test must distinguish the explicitly ACL-granted host temp directory from the OS-managed per-AppContainer temp directory.
- Updated the probe to create and verify the OS-managed temp path, assert that it remains under the AppContainer's `LOCALAPPDATA`, and separately write to the explicitly provisioned temp directory. Also corrected the worker request CRLF comparison.
- The correction is pending Run #641; no Python-runtime integration pass is claimed yet.


## Python runtime AppContainer integration verified — Run #641

- Run #641 for tested head `2c1ac574647dbd61d8cbff256c5d2010e1fa8daa` completed successfully on Ubuntu and Windows; both matrix jobs passed all 38 steps.
- The Windows process suite successfully launched a copied CPython 3.12 runtime inside the AppContainer, imported standard-library modules and native extensions (`ssl`, `sqlite3`), and verified isolated mode (`-I`), no site initialization (`-S`), and no bytecode writes (`-B`).
- The probe verified the interpreter's `sys.path` remains within the copied runtime tree, a parent-only environment secret is absent, writes to the runtime tree are denied, the explicitly provisioned temp directory is writable, and the OS-managed AppContainer temp path is creatable and contained within that ephemeral profile's `LOCALAPPDATA`.
- Run #640 remains a failed first attempt: it exposed the AppContainer-scoped `TEMP` mapping and prompted the correction validated in Run #641. Do not count #640 as passing.
- This verifies a real copied Python runtime under the current low-level launcher harness. It does **not** yet implement the production `WindowsAppContainerWorkerExecutor` or run a real adapter protocol module.
- Next Windows gap: connection-only denial probes for link-local/cloud metadata and public destinations, using host-side positive controls. Then compose the low-level modules into the host-owned executor.
- Hosted CI only; no local Windows/DSH verification. Linux Bubblewrap and live SurfCore ingress remain unimplemented. PR #1 remains Draft/Open/Unmerged.


## Windows network isolation probes extended — pending CI

- Extended the copied-Python AppContainer probe with connection-only TCP checks to public `1.1.1.1:443` and link-local metadata `169.254.169.254:80`.
- Each destination is attempted from the host first. The worker only attempts destinations for which the host established a TCP connection, then immediately closes any connection; no HTTP request, metadata token request, or application payload is sent.
- The worker must fail to connect to every host-positive destination. The test logs which positive-control destinations were actually available; unavailable host routes are not counted as verified coverage.
- Run pending. Existing loopback and host-private-interface tests remain separate and previously passed in Run #640/#641.


## Run #642 — network-probe instrumentation fixture error

- Ubuntu passed. Windows failed in the Python process test before launching the worker because a diagnostic print was inserted before the local `host_targets` list was initialized.
- This was a test-harness ordering error, not an AppContainer/network-policy failure. The probe itself was not executed, so Run #642 provides no metadata/public network result.
- Corrected the diagnostic placement to print after the host-side positive-control scan. The network test still performs TCP handshakes only and sends no application or metadata request.
- Correction pending Run #643.


## Run #643 — Python runtime and network destination isolation verified

- Run #643 for tested head `d36c346ae0b4cc10cbed55814eadde74d74386a7` completed successfully on Ubuntu and Windows; both matrix jobs passed all 38 steps.
- The Windows Python integration test ran 13 tests (one platform-specific validation test skipped as expected); all executed tests passed.
- Host-side positive controls successfully established TCP connections to both public `1.1.1.1:443` and link-local metadata `169.254.169.254:80`. The copied Python worker attempted the same TCP handshakes and was denied to both. No HTTP request, metadata token request, or application payload was sent.
- Existing loopback and private-interface denial tests also passed. Thus the current AppContainer configuration has hosted-CI evidence for loopback, private-interface, link-local metadata, and public network denial.
- Run #642 was a failed test-instrumentation attempt (diagnostic print before variable initialization); Run #643 verifies the correction. Run #640 was the earlier TEMP-directory fixture failure; Run #641 verifies its correction.
- **New contract gap found during pre-executor audit:** `ObservationRequest` and `WorkerRequest` currently carry request/target/modality metadata only. The worker-isolation design says the trusted host supplies already-fetched DTO bytes, but no payload field/path exists in the current request contract. A production executor must not be built until this is addressed explicitly.
- Next: design and implement bounded, digest-verified host-to-worker DTO input; then compose the low-level Windows modules into `WindowsAppContainerWorkerExecutor`. Linux Bubblewrap remains after Windows production executor/adversarial acceptance. No local Windows/DSH verification; no live SurfCore ingress. PR #1 remains Draft/Open/Unmerged.


## Worker protocol v2 — bounded host-to-worker DTO input added

- Extended ObservationRequest with immutable `input_payload` bytes, bounded to 512 KiB. Empty payload remains representable for metadata-only operations.
- Bumped Worker protocol to version 2. Requests now include canonical base64 input bytes and a lowercase SHA-256 digest; decoding enforces exact fields, canonical base64, digest equality, and the 512 KiB limit before the request reaches a worker.
- WorkerHost passes the payload through unchanged to the serialized WorkerRequest. The worker still receives no source credentials and must not fetch its own input.
- Added tests for payload round-trip, deterministic encoding, invalid base64, digest tampering, oversize rejection, ObservationRequest bounds, and WorkerHost payload propagation.
- This closes the earlier design/code mismatch about DTO transport. It does not implement a SurfCore ingress client, a production WorkerExecutor, or real adapter execution. CI pending.


## Run #644 — ObservationRequest payload field missing in first protocol-v2 integration

- Ubuntu failed in the new ObservationRequest contract test because the first committed contract blob contained the validation logic but omitted the dataclass field declaration. The resulting constructor rejected the input_payload keyword.
- The protocol and WorkerHost code already referenced the payload field. This was a code assembly omission, not a design rejection.
- Corrected the contract source from the reviewed payload-enabled version and centralized the 512 KiB limit as MAX_OBSERVATION_INPUT_BYTES. The corrected commit is pending CI.
