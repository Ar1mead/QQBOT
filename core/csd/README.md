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


`get_event()` also verifies that stored payload JSON uses the canonical serialization emitted by the append path. A parseable payload with recomputed content and envelope digests but non-canonical bytes (or a payload that cannot be canonically serialized) is rejected with `CognitiveIntegrityError`; this prevents duplicate-delivery and duplicate-review paths from acknowledging that damaged event. Regression and scope: [canonical event payload read validation report](../../docs/reports/csd-canonical-event-payload-read-validation-test-report-001.md). Hosted CI run #350 passed 348 tests on Ubuntu and Windows, including this path; this is not writer authentication and does not replace Recovery's event-family schema checks.


Persisted event reads now normalize malformed event fields, timestamps, and unexpected validation exceptions to `CognitiveIntegrityError`, while preserving explicit integrity failure messages. Duplicate-delivery regression and scope: [malformed durable event read error normalization report](../../docs/reports/csd-malformed-durable-event-read-error-normalization-report-001.md). Hosted CI run #350 passed 348 tests on Ubuntu and Windows, including this path.


Durable event reads and Recovery bind memory and motivation decision event IDs and correlation IDs to the proposal identity and decision-family replay order. This aligns their replay checks with the goal decision families. Regression and scope: [authoritative decision event identity validation report](../../docs/reports/csd-authoritative-decision-event-identity-validation-report-001.md). Hosted CI run #350 passed 348 tests on Ubuntu and Windows, including this path.


Recovery now rejects SQLite BLOB values stored in the event payload text column and normalizes deeply nested JSON parser/validation failures, malformed event fields, and invalid timestamps to `CognitiveIntegrityError`. Regressions exercise both ordinary event reads and Recovery with malformed storage. See [malformed payload storage and deep JSON recovery report](../../docs/reports/csd-malformed-payload-storage-recovery-report-001.md). Hosted CI run #350 passed 348 tests on Ubuntu and Windows, including this path; user-local Windows verification remains pending.


Recovery now also normalizes expected event-family schema and projection-application failures to `CognitiveIntegrityError`, while preserving already-normalized integrity failures. This ensures a digest-consistent but schema-invalid durable observation cannot leak a raw `ValueError` during projection replay. See [Recovery projection-validation error normalization report](../../docs/reports/csd-recovery-projection-validation-error-normalization-report-001.md). Hosted CI run #333 passed 343 tests on Ubuntu and Windows.


Semantic-review duplicate delivery now validates the prior event's event-local schema after verifying its canonical payload and envelope. This prevents a digest-consistent but schema-invalid prior review from being acknowledged as a valid duplicate, without rejecting legitimate retries after the proposal later reaches a terminal state. See [semantic-review duplicate schema validation report](../../docs/reports/csd-semantic-review-duplicate-schema-validation-report-001.md). Hosted CI run #336 passed 344 tests on Ubuntu and Windows.


Direct event reads through `get_event()` now rerun the event-family schema validator used by duplicate delivery and Recovery, including applicable earlier-event references. This prevents a digest-consistent but schema-invalid observation, proposal, interaction, or other ordinary event from being returned as valid by a direct read. Regression and scope: [direct event schema validation on read report](../../docs/reports/csd-event-schema-validation-on-read-report-001.md). Hosted CI is pending; user-local Windows verification remains pending.


The same-event-ID duplicate path now validates event-family schemas before acknowledging retries, and `get_event()` now applies the same event-local validation to direct reads. Decision-event reads additionally enforce exact payload fields, authority source, proposal-scoped event identity, and correlation identity. See [same-event-ID duplicate schema validation report](../../docs/reports/csd-same-event-id-duplicate-schema-validation-report-001.md) and [direct event schema validation on read report](../../docs/reports/csd-event-schema-validation-on-read-report-001.md). Run #350 verified the decision-read changes (348 tests on Ubuntu and Windows); the new direct-read follow-up is awaiting CI.


Direct reads also revalidate proposal `based_on.state_version` against the authoritative state version immediately before the proposal's original sequence. This prevents a digest-consistent proposal from claiming a future state snapshot. Regression: `test_get_event_rejects_proposal_claiming_future_state_with_valid_digests`; hosted CI is pending.


Decision-event direct reads now also validate historical provenance: the evaluated state version must match the authoritative event history immediately before the decision, and the referenced proposal must be the unique earlier event in the correct proposal family. This check reads the event log rather than mutable projections and uses a bounded internal mode to avoid recursive state-version reads. New tamper regressions and hosted CI are pending; see [decision provenance on direct reads](../../docs/reports/csd-event-schema-validation-on-read-report-001.md).


Direct reads of semantic-review events now bind each review to the unique earlier grounded proposal in the immutable event history. The read path also verifies the proposal digest, reviewed inference claim digest, and supporting-claim lineage, so recomputing payload/envelope digests cannot hide a rebound proposal reference. Regression: `test_get_event_rejects_semantic_review_referencing_another_proposal_event`. Hosted CI and user-local Windows verification are pending.


Follow-up verification: hosted GitHub Actions run #385 passed on Ubuntu and Windows with **353 tests per platform**, including the new decision-history and semantic-review provenance regressions. The same run also verified that historical motivation proposals remain readable after later signal lifecycle changes. This does not replace the user's own Windows 11 / Python 3.12.14 test, which remains deferred until the project is ready to clone.


Grounded proposal reads now validate the chronology of any source event that already exists in the event log: a proposal cannot cite a later observation as earlier evidence, even after payload/envelope digests are recomputed. Existing observation sources are loaded through the normal integrity-checked read path. Missing source events remain pending (`needs_more_evidence`); semantically invalid but structurally durable candidates (non-observation references, mismatched quotes, invalid ranges) remain reviewable and are deterministically rejected by evaluation. Hosted GitHub Actions run #393 passed on Ubuntu and Windows with **355 tests per platform**, including regressions for future-evidence rebinding and corrupted source observations. User-local Windows 11 / Python 3.12.14 verification is still pending.


Legacy memory proposals using `evidence_event_ids` now receive the same event-history checks as grounded-memory v2 claims: any already-existing evidence event must precede the proposal, and observation evidence is read through the full integrity validator. Missing evidence remains a pending condition; non-observation sources are deterministically rejected at evaluation. Hosted run #400 passed on Ubuntu and Windows with **356 tests per platform**.


Memory decision event reads now verify that `evidence_event_ids` exactly matches the evidence attached to the historical proposal (legacy `evidence_event_ids` or the derived grounded-memory v2 source-event list). They also check the allowed missing-evidence outcomes, source event chronology, and observation-vs-non-observation outcome rules. Hosted run #405 passed on Ubuntu and Windows with **356 tests per platform**.


For grounded-memory decisions using semantic review policy v0.2, direct reads now recompute the review summary from immutable review events strictly before the decision sequence. The recorded review IDs/status, policy version, applied flag, and outcome must match that history; later reviews cannot retroactively justify an earlier decision. Hosted run #411 passed on Ubuntu and Windows with **357 tests per platform**.


Motivation decision reads now bind their ordered evidence list to the historical motivation proposal's supporting and counter-evidence lists. The referenced proposal is revalidated through the durable event path, which in turn validates the interaction evidence and chronology. Hosted run #419 passed on Ubuntu and Windows with **359 tests per platform**.


Goal batch, activation, and pause/resume decision direct reads now trigger the goal subsystem's event-history replay and projection reconciliation. The replay validates every decision against its earlier proposal and the goal versions/status that existed at that point in the log. Three digest-recomputed tamper regressions cover all goal decision families. Hosted run #428 passed on Ubuntu and Windows with **362 tests per platform**.


### Schema v6 — event-history query index

Schema v6 adds the composite SQLite index `idx_events_event_type_sequence` on `events(event_type, sequence)`. It supports event-family scans and historical decision-prefix queries while preserving the event log as the authoritative source. The v5→v6 migration is transactional and has rollback coverage. The query-plan regression verifies that the shared decision-family prefix query can use this index.

This is a low-risk query improvement, not a complete solution to repeated historical prefix scans. The historical replay cost audit remains open: per-operation prefix aggregation is the next optimization, and no claim is made that long-history scaling is solved.


### Transaction-scoped verified decision replay context

The repeated prefix aggregation has now been replaced with a transaction-scoped `_DecisionReplayContext`:

- The context selects all five durable decision families in event-sequence order once for the active SQLite transaction.
- Every selected decision is still read through the ordinary integrity-aware `get_event(..., _validate_decision_context=False)` path. Payload digest, canonical payload serialization, envelope digest, event-local schema, authority source, and event identity checks remain active. Only the recursive decision-context callback is suppressed during this inner scan.
- Accepted decision sequence numbers are retained in an immutable tuple. Historical state versions are computed with a binary-search prefix lookup, counting accepted decisions only through the requested prior sequence.
- Standalone memory, motivation, goal, and event-read validations establish a SQLite read transaction when one is not already active. Recovery and writes reuse their existing transaction. The context is cleared at transaction exit and invalidated after an event append; it is never cached across snapshots.
- The mixed-family regression creates accepted memory, motivation, goal-batch, goal-activation, and pause/resume decisions, then verifies a single decision-family prefix query for the combined read projection checks and a single query for Recovery. It also checks that the in-memory context is cleared after each operation.

This removes repeated full-prefix aggregation within one history-wide operation. It is not yet a long-history wall-clock benchmark, and other per-event integrity/projection validation work remains. Hosted query-count coverage is deterministic and does not claim a production performance threshold. User-local Windows 11 / Python 3.12.14 verification remains deferred until project handoff.


### Follow-up — per-family decision ordinals and accepted-transition counts

The replay context now also stores decision sequence indexes and accepted-decision sequence indexes per event family:

- Memory and motivation decision numbering reads the verified family count from the active transaction context instead of issuing repeated SQL prefix counts.
- Motivation accepted-transition counting uses the accepted sequence index, including bounded historical counts.
- The mixed-family regression creates two memory decisions and two motivation decisions, verifies the second decision in each family receives ordinal `:2`, and also exercises two goal-batch decisions.
- It asserts no decision-family `COUNT(*)` prefix query during decision creation, combined projection validation, or Recovery; one shared five-family prefix selection per read/Recovery operation; cache cleanup; and unchanged replay state version (8).

Hosted PR workflow run #481 passed on Ubuntu and Windows with **365 tests per platform**, including compileall, focused suites, and full unittest discovery. This is hosted CI, not user-local Windows verification. Run #480's push-triggered result was not independently available through the workflow lookup used for this review.

The remaining SQL `COUNT(*)` calls that count projection rows for diagnostics or consistency checks are not decision-history prefix counts. This optimization does not claim that all projection work is linear or that long-history wall-clock performance has been benchmarked.

Latest verification refresh (2026-11-16): the documentation-updated branch head `59376a2abc4ced6be3398804900956493e0398b4` passed PR workflow run #485 on both Ubuntu and Windows, including compileall, focused suites, and full unittest discovery. The runtime/test code under test is commit `20ef3c5f021c2ff1d6010d993a18be024947ef5c`; run #481 had already passed that code/test commit with 365 tests per platform. Run #480 remains unverified. This is hosted CI only, not user-local Windows verification.
