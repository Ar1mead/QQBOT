# CSD Minimal Persistence Vertical Slice — Design Proposal

> Status: **proposal; not a frozen CSD specification or an implementation commitment**  
> Scope: first independently testable persistence slice  
> Target environment: local Windows 11; Python 3.12.14 and Node.js 24.21.0 are present in the reported environment  
> Related: `docs/architecture/overview.md`, `docs/specifications/status.md`

## 1. Objective

Establish a small, durable CSD foundation that can accept an event, deduplicate it, update one deterministic state projection atomically, create a snapshot, restart, and reconstruct the same state.

The first slice validates persistence and recovery mechanics. It does **not** attempt to implement a complete memory system, personality model, goal engine, scheduler, agent loop, or platform integration.

The central invariant is:

> An event is either durably accepted together with its projection update, or it is not accepted. Recovery reconstructs cognitive state from durable records and never performs external actions.

## 2. Non-goals

The first slice will not:
- call a model or make semantic judgments;
- connect to DSH, SurfCore, QQ, Bilibili, or any external account;
- dispatch messages, clicks, likes, comments, payments, file operations, or shell commands;
- implement ASM attempt/retry policy;
- freeze unresolved CSD or ASM clauses;
- decide the final language, process topology, or production deployment model;
- claim power-loss durability before the storage-mode test matrix is run.

## 3. Proposed component boundary

The first implementation should be a library/service boundary with a small API. It should not import DSH or SurfCore modules.

Conceptual interfaces:

- `submit_event(event)` — validate and durably ingest one event.
- `get_state_snapshot()` — return the current derived state and its event offset.
- `create_snapshot()` — persist a checkpoint of derived state.
- `recover()` — validate storage, load the latest valid checkpoint, replay later events, and return recovered state.
- `get_event(event_id)` — retrieve the accepted event envelope and payload reference for diagnostics/tests.

No CSD recovery function receives a tool executor, platform client, shell runner, or action-dispatch callback. This is an intentional architectural restriction, not merely a runtime flag.

## 4. Proposed event envelope

Retain the discussed CSD event fields:

| Field | Meaning | Initial validation |
|---|---|---|
| `event_id` | Globally unique idempotency identity | Required, non-empty, stable across retries |
| `occurred_at` | Time the source says the event occurred | Required, timezone-aware timestamp |
| `received_at` | Time CSD accepted the submission for processing | Assigned by CSD; timezone-aware |
| `correlation_id` | Groups related events | Required for the slice; stable identifier |
| `event_type` | Versioned event name | Required, namespaced string |
| `source` | Originating adapter/component | Required, namespaced string |
| `payload_ref` | Durable reference to immutable event payload | Required; must resolve before commit |

The payload is immutable once referenced. For the first SQLite implementation, a local payload table is proposed so event and payload can be committed in the same database transaction. The reference should be content-addressed (for example, a SHA-256 digest) rather than a mutable file path. This is a storage implementation detail, not a change to the logical event contract.

The accepted event envelope and payload digest must be retained. If the same `event_id` arrives again:
- identical immutable envelope and payload digest: return the original acceptance result without applying the reducer again;
- any different immutable content: return an explicit idempotency conflict; never silently overwrite the first event.

A duplicate submission may have a different transport arrival time. The implementation should distinguish transport retry metadata from the original accepted event's immutable content; it must not replace the original `received_at`.

## 5. Minimal SQLite data model

Proposed tables:

### `event_payloads`
- `payload_ref` — content-addressed primary key (SHA-256 of canonical payload bytes).
- `payload_json` — immutable canonical payload representation.

### `events`
- `sequence` — monotonically increasing local event-log offset.
- `event_id` — unique primary idempotency key.
- `occurred_at`
- `received_at`
- `correlation_id`
- `event_type`
- `source`
- `payload_ref` — foreign key to `event_payloads`.
- `event_digest` — digest of the immutable event envelope fields, checked during recovery.

### `projection_state`
- `state_key` — primary key.
- `state_json` — canonical serialized value.
- `updated_through_sequence`.

### `snapshots`
- `snapshot_id`
- `through_sequence`
- `state_bytes`
- `state_digest`
- `created_at`.

### `metadata`
- schema version and any required storage-format metadata.

The event log is the source for deterministic reconstruction. Projection rows and snapshots are derived and can be rebuilt. A snapshot is an optimization, not the sole copy of state. The prototype also installs database triggers that reject updates/deletes to event and payload rows; the event digest provides an additional corruption check during recovery.

The first implementation should avoid storing secrets or credentials in event payloads. A later encryption and retention design is required before sensitive personal content is stored.

## 6. Atomic event ingestion

Proposed transaction:

1. Validate the envelope and canonicalize/hash the payload.
2. Begin a write transaction (initial SQLite candidate: `BEGIN IMMEDIATE`).
3. Look up `event_id`.
4. If it exists, compare immutable fields and payload digest; return duplicate or conflict without reducing again.
5. Insert the immutable payload if it does not already exist; verify digest on any existing row.
6. Insert the event and obtain its monotonic sequence.
7. Run a deterministic reducer for the explicitly supported event type.
8. Update the projection and its `updated_through_sequence`.
9. Commit once.

Any validation, reducer, or database error before commit must roll back the payload insertion, event insertion, and projection update together.

The reducer must be deterministic, side-effect free, and versioned. It may update only the local projection. It must not call a model, platform, network, file writer outside the database, or action executor.

## 7. First projection used by the vertical slice

Use a deliberately unambitious test projection, such as:
- accepted event count by event type;
- latest accepted event sequence;
- latest accepted event type.

This proves that event ingestion changes durable state without prematurely deciding how autobiographical memory, emotion, preference, or goals should work.

The first test event can be a synthetic `test.observation_recorded.v1` event. It must not be presented as a real user memory or a personality update.

## 8. Snapshot and recovery

Proposed recovery procedure:

1. Open the database and validate the schema version.
2. Run SQLite integrity checks; do not delete or recreate damaged files automatically.
3. Read candidate snapshots newest-first and validate their state digest and referenced event offset.
4. Load the newest valid snapshot, or start from the empty initial projection if none is valid.
5. Read accepted events strictly after the snapshot offset in ascending sequence order.
6. Verify event/payload references and apply deterministic reducers only.
7. Reconcile the rebuilt projection and its event offset.
8. Return the recovered state and a recovery report.

If a snapshot is invalid, ignore that snapshot and rebuild from the event log. If the event log itself is incomplete, contradictory, or cannot be validated, stop and preserve the database for inspection; do not fabricate state or silently discard records.

Recovery must not:
- call an external platform;
- create or dispatch an ASM attempt;
- replay a tool call;
- infer that an uncertain external action did not happen;
- delete the event log or damaged database.

The CSD process should have no reference to external action executors, making accidental side-effect replay structurally harder.

## 9. SQLite transaction and durability settings

Candidate initial settings:
- enable foreign-key enforcement on every connection;
- configure a bounded `busy_timeout`;
- use one serialized writer path initially;
- evaluate `WAL + FULL` as the conservative first durability candidate;
- do not silently change journal or synchronous modes at runtime.

Before choosing production defaults, test the agreed matrix:

| Journal mode | Synchronous mode | Question |
|---|---|---|
| WAL | FULL | Conservative durability baseline |
| WAL | NORMAL | Performance and last-commit loss trade-off |
| DELETE | FULL | Rollback-journal comparison |
| DELETE | NORMAL | Performance comparison |

Tests must include clean shutdown, process termination during a transaction, restart with WAL/SHM files present, concurrent readers, competing writers, busy timeout, snapshot corruption, and event-log corruption. Simulated process termination is not equivalent to physical power-loss testing; record that limitation.

## 10. Minimal acceptance tests

The first vertical slice is not complete until tests demonstrate:

1. A valid event is accepted and appears in the event log.
2. Its deterministic projection update is committed with the event.
3. Re-submitting the same event ID and same content does not increment the projection twice.
4. Re-submitting the same event ID with different immutable content produces a conflict and preserves the original event.
5. A reducer exception leaves neither a partial event nor a partial projection update.
6. A snapshot can be created and validated.
7. Restart/recovery from a valid snapshot plus event tail reproduces the expected state.
8. A corrupted snapshot is bypassed and state is rebuilt from the event log.
9. A damaged or unverifiable event log causes a safe stop with the original files preserved.
10. Recovery does not call any external action executor. The test should use a spy/failing stub and assert it is never invoked; the production CSD API should not accept such an executor in the first place.

## 11. Implementation-language decision — provisional prototype choice

Do not select a language solely because DSH uses Node.js. CSD must remain independent of the runtime.

For the first disposable reference prototype, Python 3.12 standard-library `sqlite3` is selected. Python's documented SQLite API is stable and supports explicit transaction control without adding a third-party package. Node.js 24.21.0's built-in `node:sqlite` is classified by the official v24 documentation as Stability 1.2 — Release candidate, not Stable (Stability 2). This makes Python the more conservative choice for a first persistence-focused spike.

This is **not** a decision that production CSD must use Python. The prototype must remain isolated and portable. The final language/process topology will be reconsidered after testing Windows lifecycle, DSH integration boundaries, and the maturity of Node's SQLite API.

See [ADR 0002](../decisions/0002-csd-reference-implementation-language.md) for the decision and source links.

## 12. Decisions still requiring evidence or explicit confirmation

- Final implementation language and process topology.
- Exact timestamp format and clock-trust policy.
- Whether event payload bytes live in SQLite or a separate immutable content store.
- Event schema evolution and reducer version migration.
- Snapshot cadence and retention.
- Backup/restore semantics and trusted backup coverage.
- Encryption, privacy scopes, deletion/retention, and handling of sensitive memories.
- Production journal/synchronous mode after the test matrix.
- Multi-process writer policy and operational locking.
- Full event-log integrity strategy and repair procedure.

These are not blockers for a disposable synthetic vertical-slice prototype, but they are blockers for claiming production-ready persistence.

## 13. Prototype implementation status

An isolated Python reference spike now exists on branch `feature/csd-persistence-spike`:

- `core/csd/store.py` — SQLite event ingestion, idempotency, deterministic projection, snapshots and recovery.
- `tests/test_csd_store.py` — synthetic persistence and recovery tests.
- `core/csd/README.md` — how to run the isolated test suite.

The current test run passed 10 tests in the assistant's isolated environment (Python 3.13.5, SQLite 3.46.1). This is not the user's Windows environment and does not yet verify the reported local Python 3.12.14 runtime. See [test report 001](../reports/csd-persistence-spike-test-report-001.md).

The prototype is not merged to `main`, is not connected to DSH/SurfCore, and must not store real personal memories yet. Forced process termination, power-loss behavior, multi-process contention, backup/restore, privacy and retention remain untested.

## 14. Recommended execution order

1. Implement a disposable prototype with synthetic events and no external integrations.
2. Run idempotency, atomicity, snapshot and recovery tests.
3. Run the SQLite mode/concurrency/interruption matrix.
4. Review the evidence and choose language/process topology.
5. Only then connect the CSD API to DSH through a narrow adapter.
6. Only after CSD and ASM contracts are sufficiently stable, add memory, goal, and external-action workflows.

The implementation must remain on a dedicated feature branch until tests and design review are complete. Do not merge this proposal into the main branch automatically.
