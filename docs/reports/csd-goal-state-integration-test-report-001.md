# CSD Goal-State Integration Test Report 001

## Result

**Result: PASS — GitHub-hosted Linux and Windows CI completed successfully.**

- Repository: `Ar1mead/QQBOT`
- Branch: `feature/csd-cognitive-memory-slice`
- Verified code/test commit: `6f1ff70026c7234ae452581e1d2f01cc5416c73d`
- GitHub Actions: [CSD cognitive slice tests #205](https://github.com/Ar1mead/QQBOT/actions/runs/43686771898)
- Linux: GitHub-hosted Ubuntu — Python 3.12.16 / SQLite 3.46.1; 281 tests passed in 2.064s.
- Windows: GitHub-hosted Windows — Python 3.12.10 / SQLite 3.49.1; 281 tests passed in 14.982s.
- Both jobs passed `python -m compileall -q core tests`, all individual test steps, and full test discovery.

The Windows runner is a cross-platform CI check, not the user's own Windows 11 / Python 3.12.14 environment.

## Implemented scope

The first durable CSD goal-state slice now includes:

- `life.goal_batch_proposed.v1` public proposal events and CSD-reserved `life.goal_batch_decided.v1` decision events.
- SQLite schema v3 migration adding `goal_proposals`, `goal_versions`, and `goals` projections.
- Proposal identity/digest validation, idempotent retries, and conflict rejection.
- CSD-side exact source signal-version resolution at the decision event's sequence.
- CSD-derived goal origin classification. Emerging voluntary patterns attached to user/external-origin interests are classified as mixed-origin; the original signal origin is not rewritten.
- Atomic multi-goal acceptance. A whole accepted batch creates version-1 `candidate` goals and increments the shared state version once.
- Stale proposals receive one `deferred` decision without rebasing; rejected/deferred batches do not change the state version.
- Proposal-scoped deterministic decision event identity and one-decision-per-proposal enforcement.
- Event-backed projection reconciliation and deterministic Recovery.
- CSD Life Engine snapshot now includes persisted goals; the reader maps them into `GoalState` contracts.

## Test coverage

The new `tests/test_csd_goals.py` covers:

1. Candidate creation and Life Engine snapshot visibility.
2. `no_op` disposition coexisting with a separately proposed candidate goal.
3. Stale proposal deferral without automatic rebasing.
4. Missing source signal rejection without partial batch creation.
5. Existing goal identity collision rejecting the entire batch.
6. Identical proposal retry and conflicting proposal identity rollback.
7. Rejection of public attempts to append CSD-reserved decision events.
8. Recovery from a corrupted latest-goal projection.
9. CSD-derived user-requested goal origin.
10. User-origin interest with a later emerging voluntary pattern becoming mixed-origin.
11. Multiple goals created atomically with one shared state-version increment.
12. A goal retains the exact historical signal version it referenced after that signal is revised; Recovery preserves the same lineage.
13. Corruption of the append-only goal-version projection is detected and repaired by Recovery.

Existing CSD motivation, cognitive memory, Life Engine, and other test suites also passed in the same run.

## Design clarifications applied

The proposal remains a design proposal, not a frozen CSD/ASM specification. Review clarifications are recorded in `docs/design/csd-goal-state-integration-proposal.md`:

- Proposal events do not increment state_version.
- Empty no-op deliberations are not submitted as goal batches; a submitted batch must contain at least one goal.
- Stale proposals are deferred once and never silently rebased.
- Decision event identity is deterministic and proposal-scoped.
- Replay resolves the latest source signal version visible before the decision event, not today's latest signal projection.
- One accepted decision may create multiple goals, so the decision event identity is shared by multiple goal-version rows; transition IDs remain unique per goal.

## Limitations and non-claims

This is a candidate-persistence slice only:

- No goal activation, pause, block, satisfaction, abandonment, supersession, revision, or priority solver is implemented in CSD.
- No activity execution or external side effect is connected.
- The Life Engine activity-option collection remains empty until a trusted capability-filtered source exists.
- A persisted candidate is not proof of subjective desire, commitment, or an instruction to act.
- Adapter identity is not authenticated by the current caller-supplied component metadata.
- Recovery rebuilds projections; it does not call models or execute actions.
- The user's own Windows 11 environment has not yet run the tests.
