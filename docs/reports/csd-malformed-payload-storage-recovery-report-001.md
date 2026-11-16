# CSD malformed payload storage and deep JSON recovery report 001

## Finding

The durable event-read hardening covered malformed timestamps and canonical JSON failures, but two malformed payload representations still escaped the integrity-error boundary:

- SQLite can store a BLOB in a column declared as TEXT. Calling the payload digest helper on the returned bytes raised a raw `AttributeError` rather than `CognitiveIntegrityError`.
- A deeply nested JSON payload can raise `RecursionError` during `json.loads` in Recovery. Recovery previously normalized only `JSONDecodeError`; its later canonical-validation boundary also omitted recursion/overflow failures.

These cases matter because malformed durable history must fail closed through the same explicit integrity-error contract, not leak implementation exceptions.

## Change

- `get_event()` now rejects payload values that SQLite returns as anything other than `str`.
- Recovery applies the same stored-text type check before hashing.
- Recovery normalizes `TypeError`, `ValueError`, `RecursionError`, and `OverflowError` from JSON decoding, event-field/timestamp validation, digest construction, and event validation to `CognitiveIntegrityError`.
- Added three regressions:
  - A BLOB payload is rejected by both ordinary event reads and Recovery.
  - A deeply nested JSON payload with recomputed payload reference and event-envelope digest is rejected by both ordinary event reads and Recovery.
  - A malformed durable event timestamp is normalized to `CognitiveIntegrityError` during Recovery.

## Verification status

- [x] Implementation committed to `feature/csd-cognitive-memory-slice` (`86fe9385e2497d01a396968ebd38565eab87125d`).
- [x] Regression tests committed (`b02207e5b84886666c3481d748b522ec369955c6`, `292497e66619173ca3a66ce3c5227d867ac9bb05`).
- [x] GitHub Actions run #331 passed on Ubuntu (Python 3.12.16 / SQLite 3.46.1) and Windows (Python 3.12.10 / SQLite 3.49.1): 342 tests passed on each platform; compileall passed.
- [ ] User-local Windows 11 / Python 3.12.14 verification remains pending; hosted Windows CI is not a substitute.

## Boundary

This hardening normalizes malformed payload storage and parser failures. It does not authenticate event writers, provide cryptographic signatures, establish source truth, or replace event-family replay and projection reconciliation.

Follow-up Recovery field-validation fix: `b38452bd4529a6f06546883343e74369e61f43d2`. Regression: `test_recovery_normalizes_malformed_event_timestamp`. This closes the mismatch where `get_event()` normalized malformed timestamps but Recovery could leak a raw `ValueError`.

CI follow-up: the first two attempts exposed test-fixture-only defects (an ambiguous joined-column reference, then a missing referenced payload row). Both were corrected in test commits `f8000fd3cbeddd6357f7a35eac9e50e34d0198ef` and `1bccee2da79cd8fd5b4d90746f1c1e12eee3199f`. Final run #331 passed 342 tests on both hosted platforms.
