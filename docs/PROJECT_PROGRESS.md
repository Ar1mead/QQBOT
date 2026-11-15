# Project Progress Ledger

> Repository: `Ar1mead/QQBOT`  
> Last updated: 2026-11-15 (UTC+08:00)  
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
- [x] Verify the complete cognitive-memory test suite in hosted Linux and Windows CI (249 tests); [ ] verify on the user's own Windows 11 environment.

### 3.4 Life Engine and motivation proposal layer

- [x] Added provider-neutral motivational signal and goal proposal structures.
- [x] Added deliberation outcomes including an explicit `no_op`.
- [x] Added permission/prerequisite gates and ASM handoff classification; the Life Engine reference slice does not dispatch external actions.
- [x] Added evidence-grounded motivation proposal validation distinguishing user-requested actions, platform exposure/autoplay, and independently selected activities.
- [x] Added origin references, evidence non-reuse, signal versioning, and explicit contextualization rather than silently rewriting a signal.
- [x] Added tests for the Life Engine and motivation proposal validator in the repository.
- [ ] Connect the Life Engine to trusted CSD snapshot and event interfaces.
- [ ] Add persistent goal/commitment/affect state and learning/update reducers.
- [ ] Connect no real model provider yet; autonomous deliberation and goal formation remain unimplemented.

## 4. Current work in progress — CSD motivation integration

Branch: `feature/csd-cognitive-memory-slice`

The current work connects motivation signals to the same CSD event stream as cognitive memories. The latest hosted Linux and Windows runs passed; broader adversarial review and the user's own Windows verification remain open.

- [x] Added `core/csd/motivation.py` with interaction provenance validation, motivation proposal validation, CSD-side deterministic decision preparation, signal lifecycle projection, retrieval, and projection consistency checks.
- [x] Added interaction events, motivation proposal events, and CSD-authoritative motivation decision events to the CSD event model.
- [x] Added a SQLite schema migration from cognitive-store schema v1 to v2 for motivation proposal/signal projections.
- [x] Changed global `state_version` to count accepted memory and motivation state transitions, while validating the memory and motivation projections independently.
- [x] Added Recovery rebuilding for motivation proposals and signal projections from the shared event history; Recovery does not call a model/provider or execute external actions.
- [x] Added `tests/test_csd_motivation.py` with migration, provenance, idempotency, origin preservation, signal lifecycle, global version, transaction rollback, and Recovery scenarios.
- [x] Updated the workflow path filters and test step so `test_csd_motivation.py` is included for both pushes and pull requests.
- [x] Run `python -m compileall -q core tests` against the exact branch checkout (GitHub Actions, Linux and Windows runners).
- [x] Run `python -m unittest discover -s tests -v` against the exact branch checkout (250 tests passed).
- [x] Fix the migration test fixture and update this ledger with the exact result; the earlier fixture represented an impossible v1 database state.
- [x] Confirm a successful GitHub Actions run for the current branch: run #144, commit `94240258b793c2dea66b22a05b2bcd8dfeef3656`.
- [x] Review v1→v2 migration against a legacy-schema fixture and verify rollback after an injected partial-DDL failure.
- [~] Reconcile both motivation and accepted-memory proposal/state projections against authoritative events; tampering tests and Recovery repair pass. Duplicate motivation-proposal source-validation bypass is closed; user/platform origin references are checked against observation kinds; return-visit semantics are covered by run #142; event/payload digest checks now cover motivation proposals, decisions, and referenced interaction evidence (run #144). Lifecycle tests cover create/reinforce/weaken/contextualize/pause/resolve. Broader event-schema, replay, and idempotency adversarial coverage remains.
- [x] Run the full suite on a GitHub-hosted Windows runner (250 tests, Python 3.12.10 / SQLite 3.49.1); this is a cross-platform CI check, not the user's own Windows 11 environment.
- [ ] Only after the above: run the tests on the user's Windows environment.

Important implementation boundary: the current CSD motivation decision path is deterministic scaffolding. It does not yet infer authentic human-like interests, feelings, needs, or desires; it does not authenticate adapter identity; and it does not establish that the evidence source is truthful. A caller-supplied adapter string is provenance metadata, not a security credential. Do not describe this slice as autonomous motivation or a complete cognitive system.

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

1. **Continue adversarial review of event schemas, replay determinism, idempotency, and projection integrity.** Motivation and memory projections reconcile against event history. The return-visit rule is verified: the current return is the voluntary choice; the prior linked interaction may be passive exposure or user-requested. A global encounter-ID uniqueness rule was tested and reverted because one encounter may legitimately contain multiple interaction events.
2. **Run the exact suite on the user's Windows 11 / Python 3.12.14 machine.** This is the remaining platform-specific verification step once the remote branch is stable.
3. **Stabilize CSD read/write contracts.** Separate memory, motivation, goal, affect, commitment, and diary state families without creating competing authorities.
4. **Connect Life Engine through explicit CSD interfaces.** The Life Engine may propose intentions; CSD accepts durable state transitions.
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
- Latest code/test commit verified by CI: `94240258b793c2dea66b22a05b2bcd8dfeef3656`, workflow run #144; subsequent commits in this branch update only the report and progress ledger.
- Hosted CI passed on Ubuntu 26.04.1 (Python 3.12.16 / SQLite 3.46.1) and GitHub-hosted Windows (Python 3.12.10 / SQLite 3.49.1).
- `python -m compileall -q core tests` passed.
- `python -m unittest discover -s tests -v` passed: 250 tests on both Linux and Windows runners (Linux 2.083s; Windows 15.623s).
- The v1→v2 migration test uses legacy-only event history; a separate injected-failure test confirms partial DDL rollback.
- Motivation and accepted-memory proposal/state projections are checked against authoritative events; corruption tests verify Recovery repair.
- Detailed results and limitations: `docs/reports/csd-motivation-integration-test-report-001.md`.
- The user's local machine has not cloned this repository; Windows-local verification remains pending.
- Hosted test success does not establish adapter authenticity, semantic truth, or autonomous motivation.

**Resume from section 4: continue event payload/replay/idempotency adversarial review; motivation read paths now verify evidence payload digests, but broader integrity coverage remains, then arrange Windows-local verification.**
