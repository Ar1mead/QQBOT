# CSD persistence reference prototypes

This directory contains two isolated Python 3.12 / SQLite reference implementations:

- `store.py`: the original generic append-only persistence spike, with its original 16-test baseline preserved.
- `cognitive.py`: the typed cognitive-memory slice, using a separate SQLite database and a separate event/projection schema.
- `proposals.py`: a v1 provider-neutral interface that converts model/provider output into untrusted candidate events; it never accepts memory state.
- `grounded_proposals.py`: the v2 typed provider boundary for claim-level text evidence; it binds evidence and state provenance and submits pending proposals only.
- Accepted-memory reads: deterministic substring, memory-kind, epistemic-type, evidence-event, and pagination filters; list/single reads fail closed on a count mismatch with the authoritative accepted-decision history.

No real model-provider adapter is included. These reference prototypes do not integrate with DSH, SurfCore, network services, platform clients, or external-action executors. Provider interfaces are tested only with synthetic providers.

Run tests from the repository root:

```powershell
py -3.12 -m unittest discover -s tests -p "test_csd_cognitive.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_proposal_pipeline.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_grounded_memory.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_grounded_proposal_pipeline.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_memory_retrieval.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_store.py" -v
```

The generic store's WAL/DELETE journal modes and FULL/NORMAL synchronous modes are test candidates, not production durability guarantees. The cognitive slice currently uses the same selectable SQLite settings but has not been validated for Windows power-loss behavior.

The cognitive-memory implementation, both provider-neutral pipelines, and filtered Memory Retrieval API are engineering prototypes only. Retrieval checks accepted-projection consistency before returning data and fails closed until Recovery rebuilds a mismatched projection. Retrieval currently supports exact substring/filter/pagination operations, not semantic search. The v1 free-form candidate pipeline is retained for compatibility; a real provider should target the grounded v2 path in pending-only mode. See the [memory proposal provider contract](../../docs/design/memory-proposal-provider-contract.md) and [grounded-memory v2 design](../../docs/design/grounded-memory-proposal-v2.md). See [implementation decisions](../../docs/design/csd-cognitive-slice-implementation-decision.md) and the [vertical-slice design](../../docs/design/first-cognitive-state-vertical-slice.md).

Fresh schema bootstrap (`user_version=0` → v1) explicitly rolls back partial DDL if initialization fails. The regression test injects a conflicting table name and verifies the transaction closes, `user_version` remains 0, partial tables/triggers are removed, and the pre-existing table remains. See [fresh-schema migration rollback report](../../docs/reports/csd-fresh-schema-migration-rollback-test-report-001.md). Hosted CI run #279 passed 327 tests on Ubuntu and Windows.

Recovery acquires `BEGIN IMMEDIATE` before integrity checks and reading the event stream, then rebuilds projections and reports counts from that same serialized snapshot. This prevents an event appended by another connection between the old pre-transaction read and rebuild from being omitted. A deterministic two-connection regression test passes on both hosted platforms; see [Recovery event-snapshot atomicity report](../../docs/reports/csd-recovery-event-snapshot-atomicity-test-report-001.md). Hosted CI run #282 passed 328 tests on Ubuntu and Windows.

Recovery now revalidates each durable event through the shared append-time event-envelope contract, including reserved event-ID namespaces, source/type rules, and canonical payload serialization. Invalid durable events fail closed before projections are cleared. This is covered by a direct-SQL forged-event regression; see [durable event-envelope validation report](../../docs/reports/csd-durable-event-envelope-validation-test-report-001.md). Hosted CI run #287 passed 329 tests on Ubuntu and Windows.

Repeated delivery of an existing `event_id` now validates the stored event through `get_event` before returning an idempotent duplicate acknowledgement. A corrupted payload or envelope digest therefore fails closed rather than being hidden by a retry. See [duplicate delivery integrity report](../../docs/reports/csd-duplicate-delivery-integrity-test-report-001.md). Hosted CI run #290 passed 330 tests on Ubuntu and Windows.

The shared transaction context manager now rolls back when `COMMIT` itself fails and SQLite leaves the transaction active. A deferred-foreign-key regression verifies rollback, no partial event row, and successful reuse of the same connection after failure. See [commit-failure rollback report](../../docs/reports/csd-transaction-commit-failure-rollback-test-report-001.md). Hosted CI run #293 passed 331 tests on Ubuntu and Windows.

Both `get_state_snapshot()` and `get_life_signal_snapshot()` now use a shared explicit read-transaction helper. Diagnostic counts, authoritative state version, and projection consistency checks are read from one SQLite snapshot. A two-connection regression confirms a concurrent append is excluded from the in-flight snapshot and visible afterward. See [transactional read snapshot report](../../docs/reports/csd-transactional-read-snapshot-test-report-001.md). Hosted CI run #297 passed 332 tests on Ubuntu and Windows. The first test draft's thread-affinity error in run #296 was a fixture issue; the writer connection is now created and closed inside its worker thread.

Diagnostic and Life Engine snapshots use explicit SQLite read transactions. A two-connection regression commits an event after the diagnostic snapshot establishes its read view and verifies that the returned counts remain consistent with that earlier snapshot. The test keeps each SQLite connection on its creating thread; the earlier cross-thread test-harness failure did not indicate a production snapshot defect. Hosted CI run #298 passed 332 tests on Ubuntu and Windows.

Semantic-review duplicate delivery is keyed by `review_id`, but now resolves and validates the prior authoritative event through `get_event` before acknowledging a duplicate. A damaged prior event therefore fails closed rather than being hidden by a retry. See [semantic-review duplicate integrity report](../../docs/reports/csd-semantic-review-duplicate-integrity-test-report-001.md). Hosted CI run #302 passed 333 tests on Ubuntu and Windows.


`get_event()` also verifies that stored payload JSON uses the canonical serialization emitted by the append path. A parseable payload with recomputed content and envelope digests but non-canonical bytes (or a payload that cannot be canonically serialized) is rejected with `CognitiveIntegrityError`; this prevents duplicate-delivery and duplicate-review paths from acknowledging that damaged event. Regression and scope: [canonical event payload read validation report](../../docs/reports/csd-canonical-event-payload-read-validation-test-report-001.md). Hosted CI is pending; this is not writer authentication and does not replace Recovery's event-family schema checks.


Persisted event reads now normalize malformed event fields, timestamps, and unexpected validation exceptions to `CognitiveIntegrityError`, while preserving explicit integrity failure messages. Duplicate-delivery regression and scope: [malformed durable event read error normalization report](../../docs/reports/csd-malformed-durable-event-read-error-normalization-report-001.md). Hosted CI is pending.


Durable event reads and Recovery bind memory and motivation decision event IDs and correlation IDs to the proposal identity and decision-family replay order. This aligns their replay checks with the goal decision families. Regression and scope: [authoritative decision event identity validation report](../../docs/reports/csd-authoritative-decision-event-identity-validation-report-001.md). Hosted CI is pending.


Recovery now rejects SQLite BLOB values stored in the event payload text column and normalizes deeply nested JSON parser/validation failures to `CognitiveIntegrityError`. Regressions exercise both ordinary event reads and Recovery with malformed storage. See [malformed payload storage and deep JSON recovery report](../../docs/reports/csd-malformed-payload-storage-recovery-report-001.md). Hosted CI and Windows-local verification are pending.
