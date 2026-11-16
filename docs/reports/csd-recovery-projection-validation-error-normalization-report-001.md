# CSD Recovery projection-validation error normalization report 001

## Finding

Recovery validates each durable event envelope before rebuilding projections, but event-family validation and projection application occur later. Those family handlers intentionally use ordinary validation exceptions (for example, `ValueError`) at their public submission boundaries. When replaying a malformed but otherwise digest-consistent durable event, Recovery could therefore leak a raw validation exception instead of the CSD integrity-error contract.

The regression uses a canonical, correctly re-hashed observation event whose `coverage.complete_for_fixture` field has the wrong type. Its payload reference and event-envelope digest are recomputed, so the failure is specifically in family-schema validation during projection replay, not in the lower-level digest checks.

## Change

- Recovery now wraps expected domain/schema/projection failures from `_apply_projection_event` as `CognitiveIntegrityError`.
- Existing `CognitiveIntegrityError` instances pass through unchanged.
- Normalization includes CSD store-domain errors, type/value/key/index errors, recursion/overflow errors, and SQLite integrity constraint failures.
- The write transaction still encloses projection deletion and replay; a failed replay rolls back the rebuild.

## Regression

- `tests/test_csd_semantic_review.py::test_recovery_normalizes_invalid_observation_projection` mutates a valid observation into a malformed but canonical event, recomputes its content reference and event-envelope digest, and verifies Recovery raises `CognitiveIntegrityError`.

## Verification

- [x] Implementation commit: `3088f6610058513d6a166784d08a496beac56907`.
- [x] Regression commit: `4e8f8d048dab661a53e12ffac6e3d4cb6146fc16`.
- [x] GitHub Actions run #333 passed on Ubuntu (Python 3.12.16 / SQLite 3.46.1) and Windows (Python 3.12.10 / SQLite 3.49.1): 343 tests passed on each platform; compileall passed.
- [ ] User-local Windows 11 / Python 3.12.14 verification remains pending.

## Boundary

This makes Recovery consistently classify malformed event-family replay as durable-history integrity failure. It does not make external event sources authentic, prove semantic truth, or provide cryptographic writer authentication.
