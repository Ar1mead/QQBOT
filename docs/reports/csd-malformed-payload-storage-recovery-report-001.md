# CSD malformed payload storage and deep JSON recovery report 001

## Finding

The durable event-read hardening covered malformed timestamps and canonical JSON failures, but two malformed payload representations still escaped the integrity-error boundary:

- SQLite can store a BLOB in a column declared as TEXT. Calling the payload digest helper on the returned bytes raised a raw `AttributeError` rather than `CognitiveIntegrityError`.
- A deeply nested JSON payload can raise `RecursionError` during `json.loads` in Recovery. Recovery previously normalized only `JSONDecodeError`; its later canonical-validation boundary also omitted recursion/overflow failures.

These cases matter because malformed durable history must fail closed through the same explicit integrity-error contract, not leak implementation exceptions.

## Change

- `get_event()` now rejects payload values that SQLite returns as anything other than `str`.
- Recovery applies the same stored-text type check before hashing.
- Recovery normalizes `TypeError`, `ValueError`, `RecursionError`, and `OverflowError` from JSON decoding and event validation to `CognitiveIntegrityError`.
- Added two regressions:
  - A BLOB payload is rejected by both ordinary event reads and Recovery.
  - A deeply nested JSON payload with recomputed payload reference and event-envelope digest is rejected by both ordinary event reads and Recovery.

## Verification status

- [x] Implementation committed to `feature/csd-cognitive-memory-slice` (`86fe9385e2497d01a396968ebd38565eab87125d`).
- [x] Regression tests committed (`b02207e5b84886666c3481d748b522ec369955c6`).
- [ ] GitHub-hosted Ubuntu and Windows CI pending.
- [ ] User-local Windows 11 / Python 3.12.14 verification remains pending.

## Boundary

This hardening normalizes malformed payload storage and parser failures. It does not authenticate event writers, provide cryptographic signatures, establish source truth, or replace event-family replay and projection reconciliation.
