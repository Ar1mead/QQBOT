# CSD Event Schema Validation on Direct Read Report 001

Date: 2026-11-16 (UTC+08:00)

## Scope

This slice closes the gap between three event-validation paths: Recovery replay, same-event-ID duplicate delivery, and ordinary direct event reads through `get_event()`.

## Finding

Before this change, `get_event()` verified payload storage type, payload digest, canonical JSON, timestamps, and envelope digest. It also checked the exact field set and proposal-scoped identity of decision events. It did not consistently rerun event-family schema validation for observations, memory proposals, grounded proposals, semantic reviews, interactions, motivation proposals, or goal proposals.

As a result, a direct SQL rewrite that also recomputed the payload reference and envelope digest could leave a malformed non-decision event readable until Recovery or a duplicate-delivery path encountered it.

## Change

- `get_event()` now invokes the same event-local schema validator used by the same-event-ID duplicate path.
- The validator checks the event family shape and applicable earlier-event references.
- Contextual checks remain bounded by the event's original sequence; later lifecycle changes do not invalidate an otherwise valid historical event.
- Proposal `based_on.state_version` claims are checked against the authoritative decision history immediately before the proposal's own sequence. A future-version claim is rejected on direct read even if its payload and envelope digests have been recomputed.
- Earlier evidence references are followed recursively through `get_event()`, with event ordering rules requiring references to point backward.
- Decision event read checks remain in place and are also covered by the shared validator.

## Regression

Added two direct-read regressions:

- `tests/test_csd_semantic_review.py::test_get_event_rejects_schema_invalid_observation_with_valid_digests`.
- `tests/test_csd_semantic_review.py::test_get_event_rejects_proposal_claiming_future_state_with_valid_digests`.

The test:
1. Persists a valid observation event.
2. Changes its `observation_kind` to an invalid empty value.
3. Recomputes the canonical payload reference and envelope digest.
4. Calls `get_event()` directly.
5. Requires `CognitiveIntegrityError` instead of returning the malformed event.

The proposal regression persists a valid grounded proposal, rewrites its `based_on.state_version` to a value that did not exist at that event's sequence, recomputes both digests, and verifies that direct read rejects the historical claim.

## Verification

- Implementation commits: `68956b4092742fb8aa9c2c31e37204c01134b63c` (shared validation on reads), `aa5c13fca447bf7cd64669c8df98890fe9932122` (helper naming and avoid duplicate decision checks), and `c61677c04980cdafb0d51b34efd60588f3fa825d` (generalized error wording), and `dbfa9af2a703283249c440efa4efc6a84e322c77` (proposal chronology on reads).
- Regression test commits: `12c059db63443bb9a848fcd0df4f1c70555cf187` and `f7698e1e0726375211a1dcd73fe99f96007a6edf` (observation schema), plus `559494e1433257bb6501f84db26a9299ea966c5b` (future proposal snapshot).
- Hosted CI: pending; the GitHub connector currently reports no associated workflow run or commit status for this follow-up. Run #350 predates this change.
- User-local Windows 11 / Python 3.12.14 verification: pending.

## Security boundary

The event digest is an integrity checksum, not an authenticated signature. This change detects schema-invalid rewrites even when their hashes are recomputed. It cannot prove authenticity against an actor able to rewrite the complete event history into a different, internally valid history and recompute all dependent values. Stronger tamper evidence requires an independently protected checkpoint or signing key outside the writable SQLite database; that is a separate design decision.

This change does not connect a model provider, infer subjective motivation, or execute external actions.


## Follow-up: decision provenance on direct reads

A further audit found that decision-event reads checked exact payload fields, authority source, proposal-scoped event identity, and correlation identity, but did not independently prove that the decision's `evaluated_state_version` and `proposal_event_id` matched the event history immediately before the decision.

### Change

- Direct reads now require `evaluated_state_version` to equal the authoritative state version immediately before the decision event.
- `proposal_event_id` must identify the unique earlier proposal event with the same `proposal_id`, and the event type must belong to the decision family's expected proposal family.
- The historical proposal is loaded and validated from the immutable event log, not from mutable proposal projection tables.
- Internal authoritative-state scans use a bounded validation mode to avoid recursive contextual reads. They retain envelope, payload, schema, authority, and identity checks for each counted decision.
- Proposal-family matching uses SQLite JSON functions over the durable payload table; malformed JSON is protected by a lazy `CASE` expression.

### Regression

Added:
- `test_get_event_rejects_decision_with_rewritten_evaluated_state_version`
- `test_get_event_rejects_decision_referencing_another_proposal_event`

Both tests recompute payload and envelope digests after tampering, so rejection must come from historical semantic validation rather than checksum mismatch.

### Verification status

- Implementation: commits `44b295b170ca32b5f7f4b9b4e1055bf6c6280645` and `cc3a2ae8035aac68b61ad02fbc6e4804a2ebee4e`.
- Tests: commits `6a52756d9e1186f1950a71c504dbec0af487a971` and `6ca959bdab7d36a77c1bdcc996befa8ddbf96c8e`.
- Hosted CI: pending. Run #350 (348 tests per OS) predates this change and is not evidence for these additions.
- User-local Windows 11 / Python 3.12.14: pending.


## Follow-up: semantic-review proposal provenance on direct reads

- Direct reads now verify that a semantic-review event references the unique earlier grounded proposal event for its proposal ID.
- The referenced proposal is loaded through the immutable event log and validated through the normal event-read path; its proposal digest, inference claim ID/digest, and direct supporting-claim lineage are checked.
- Regression: `tests/test_csd_semantic_review.py::test_get_event_rejects_semantic_review_referencing_another_proposal_event` rewrites the review's proposal event reference to a different real proposal and recomputes the payload and envelope digests. The expected result is `CognitiveIntegrityError`.
- Implementation commits: `64222e020b7dde086c0befe98e878ec4a7053acf` and `7db787634f58b142b5b1027954fd3355fa67f9c0`; regression commit: `333cae330f51e8cfc7a7dd665e960c616ef9e071`.
- Hosted CI and local Windows verification: pending. The new test has been committed but has not yet been executed.


## Verification correction: hosted run #385

The first follow-up runs exposed two issues that were corrected before the successful run:

- Historical direct reads of motivation proposals were reusing live projection checks. After later motivation transitions, those checks incorrectly rejected valid earlier proposals. The direct-read path now performs structural and event-evidence validation without comparing an old proposal against today's signal projection; append-time validation still applies the live-state checks.
- Two existing regression assertions still expected the older error wording. They now assert the shared `invalid durable event schema` integrity error.

Hosted GitHub Actions run #385 passed on both Ubuntu and Windows. `python -m compileall -q core tests` passed, every workflow test step passed, and complete unittest discovery passed **353 tests on each platform**. This is hosted CI only; the user's own Windows 11 / Python 3.12.14 verification remains intentionally deferred until the project is ready to clone.


## Follow-up: grounded evidence chronology and source-event integrity

- `get_event()` now validates grounded proposal references against immutable event history. If a referenced evidence event already exists, it must have been appended before the proposal; a later observation cannot be rebound as prior evidence even if the proposal payload and envelope digests are recomputed.
- When the referenced event is an observation, the read path also loads it through `get_event()` so its durable envelope and observation schema are verified before treating it as a valid source record.
- A missing evidence event remains an allowed pending-candidate condition; deterministic proposal evaluation continues to return `needs_more_evidence`. Existing but non-observation references, mismatched quoted text, and invalid text ranges remain deterministic rejection outcomes rather than being conflated with durable-log corruption.
- Regressions: `test_get_event_rejects_grounded_proposal_referencing_later_observation` and `test_get_event_validates_existing_grounded_source_observation`. Both use recomputed payload/envelope digests where applicable.
- Implementation commit: `03e202ce0d4c5f367cc4d2b84b02aa43dc373a1a`; test commit: `b3f08b6c0704c3d8fd0bfddd2e9c95468144ffc8`.
- Hosted GitHub Actions run #393 passed on Ubuntu and Windows. Compileall and every focused test step passed; complete unittest discovery passed **355 tests per platform**. User-local Windows 11 / Python 3.12.14 verification remains deferred until project handoff.


## Follow-up: legacy memory proposal evidence chronology

- The same historical evidence rule now covers legacy `memory.proposed.v1` events that use `evidence_event_ids`, not only grounded-memory v2 claims.
- For each reference that already exists in the event log, the referenced event must precede the proposal. Existing observation events are loaded through `get_event()` to verify their stored envelope and observation schema. A missing evidence event remains a pending proposal condition; non-observation evidence is still handled as a deterministic rejection by the evaluator.
- Regression: `tests/test_csd_semantic_review.py::test_get_event_rejects_legacy_memory_proposal_referencing_later_observation`, which rebinds a legacy proposal to a later observation and recomputes payload and envelope digests.
- Implementation commit: `95e43fcda22f84bbbca1100c477434dabe6a8935`; regression commit: `ce26413e331e3f8910004b403a0774d5361b6ffe`.
- Hosted GitHub Actions run #400 passed on Ubuntu and Windows. Compileall and all focused test groups passed; complete unittest discovery passed **356 tests per platform**. Local Windows 11 / Python 3.12.14 verification remains pending.


## Follow-up: memory decision evidence binding on direct reads

- Direct reads of CSD memory decision events now compare `evidence_event_ids` with the exact evidence set in the uniquely referenced earlier proposal event. Legacy proposals use their `evidence_event_ids`; grounded-memory v2 proposals derive the ordered unique list from source-assertion claims.
- Direct read validation also enforces the decision replay rules for these evidence references: a missing source is only compatible with `needs_more_evidence` or `rejected`; an existing source must precede the decision; and a non-observation source is only compatible with a rejected outcome.
- Regression: `tests/test_csd_semantic_review.py::test_get_event_rejects_memory_decision_with_rebound_evidence_ids` changes the decision's evidence list, recomputes the payload and envelope digests, then confirms `get_event()` fails closed.
- Implementation commit: `ef043337c610603e6065a7bfdf48acb2944c919e`; regression commit: `bdb52b9f794776efc7bee9fbba7911fd06ea2e68`.
- Hosted GitHub Actions run #405 passed on Ubuntu and Windows. Compileall and all focused workflow groups passed; complete unittest discovery passed **356 tests per platform**. User-local Windows 11 / Python 3.12.14 verification remains pending.


## Follow-up: decision-to-semantic-review history binding

- Direct reads of memory decision events using grounded review policy v0.2 now compare `semantic_review_event_ids` and `semantic_review_status` with the immutable semantic-review event history that existed before the decision.
- The direct-read path also checks the policy family/version, the `semantic_review_applied` flag, allowed review status/outcome combinations, and the rule that an inference cannot be accepted without supported prior review evidence.
- The review summary is recomputed with an explicit `before_sequence` bound, so reviews appended after a decision cannot retroactively justify it. Every referenced review is itself validated against its unique earlier grounded proposal, proposal digest, inference claim digest, and supporting-claim lineage.
- Regression: `tests/test_csd_semantic_review.py::test_get_event_rejects_memory_decision_with_rebound_semantic_review_ids` removes the review reference from an otherwise accepted decision, recomputes both digests, and confirms direct read rejection.
- Implementation commit: `312a204a7cf0bd04719cac58e15ccbd83d77aa9a`; regression commit: `b3b450cc01df62a3df6f3bcd8acfbf7720df5043`.
- Hosted GitHub Actions run #411 passed on Ubuntu and Windows. Compileall and all focused workflow groups passed; complete unittest discovery passed **357 tests per platform**. User-local Windows 11 / Python 3.12.14 verification remains pending.


## Follow-up: motivation decision evidence binding on direct reads

- Direct reads of motivation decision events now compare the decision's ordered `evidence_event_ids` with the exact concatenation of the referenced historical proposal's `supporting_event_ids` and `counter_evidence_event_ids`.
- The proposal is loaded through the normal event-read path. Its evidence is independently checked as prior interaction events with valid interaction schema and grounded subject/origin relationships before the decision's evidence list is trusted.
- Regression: `tests/test_csd_motivation.py::test_get_event_rejects_motivation_decision_with_rebound_evidence_ids` tampers with an accepted motivation decision's evidence list, recomputes payload and envelope digests, and confirms direct read rejection.
- Implementation commit: `f4617e1757cfc43cfe5082fca3b916f30cbc2f5d`; regression commit: `1197c1b0ae3cdbfbd560e1e8016b7fb6f1261a68`.
- Hosted GitHub Actions run #419 passed on Ubuntu and Windows. Compileall and every focused test group passed; complete unittest discovery passed **359 tests per platform**. User-local Windows 11 / Python 3.12.14 verification remains pending.


## Follow-up: goal decision direct-read replay validation

- Direct reads of goal batch, activation, and pause/resume decision events now invoke the goal subsystem's sequence-ordered history replay and projection reconciliation. This re-derives candidate/active/paused goal transitions from the historical proposals and prior state, instead of trusting only the mutable goal projections or the decision envelope digest.
- The goal replay's internal event reads suppress only the recursive decision-context callback; event envelope/schema checks still run, and the replay itself validates each decision against the proposal and goal state that existed before its sequence.
- Added tamper regressions for all three decision families: `test_get_event_rejects_goal_batch_decision_with_rewritten_transition`, `test_get_event_rejects_activation_decision_with_rewritten_goal_version`, and `test_get_event_rejects_pause_resume_decision_with_rewritten_operation`. Each rewrites a valid decision payload and recomputes its content and envelope digests before requiring `CognitiveIntegrityError`.
- Implementation commits: `7d8220d97c390b66ec2b0a446a882301172c237d` and `e7a012e6c423caa7fc4d6db27ad35bfbe5be2d0d`; regression commit: `197e7c9cd1303549268a6f45ae652f5a336417cf`.
- Hosted GitHub Actions run #428 passed on Ubuntu and Windows. Compileall and every focused workflow group passed; complete unittest discovery passed **362 tests per platform**. User-local Windows 11 / Python 3.12.14 verification remains deferred until project handoff.
