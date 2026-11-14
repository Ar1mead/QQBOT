# Specification Status Register

This register records the status of specification work at repository initialization. It is not a substitute for the full source specifications.

## CSD

**Status: working contract; not frozen.**

A CSD contract v0.1 has been discussed. Its direction includes:

- CSD as the authoritative source of long-term cognitive state.
- Runtime components submit events rather than directly evaluating and mutating authoritative long-term state.
- Idempotent event ingestion, with deduplication and business-state updates committed atomically.
- Read interfaces for state snapshots, memory retrieval, and goal retrieval, plus event submission and recovery.
- Recovery reconciles durable logs and snapshots without replaying external side effects.
- Uncertain external outcomes are inspected and verified rather than blindly retried.

The CSD contract, recovery details, storage behavior, and test matrix still require implementation-level validation. Do not treat this summary as a verbatim specification.

## ASM-5.3

**Status: confirmed semantic working baseline; verbatim source restoration incomplete.**

The current confirmed baseline includes:

- ASM-5.3 is the decision gate for creating a new outbound business-action attempt.
- Retry eligibility depends on execution evidence, repeatability, and platform idempotency constraints.
- A confirmed execution prohibits retrying the same `business_action_id`; this does not prohibit other business actions under the same `correlation_id`.
- A 5.4 authorization result does not itself create an attempt; the 5.3 checks still apply.
- Verification-attempt creation/frequency is outside the retry rules for outbound business-action attempts.

This is a summary of the confirmed semantic baseline, not a replacement for the original clauses.

## ASM-5.4

**Status: under review; not frozen.**

A reconstructed, explicitly non-verbatim 5.4 text and a set of semantic questions have been discussed. The current working interpretation is that 5.4 handles retry-eligibility cases not conclusively decided by fixed 5.3 rules. It does not create attempts or change execution facts. Its decision outputs and audit requirements have been discussed, but several boundaries remain unresolved.

Do not present ASM-5.4 as finalized, and do not generate conformance tests from unresolved interpretations as if they were normative clauses.

## General handling rules

- Distinguish verbatim source text from reconstructed summaries.
- Label confirmed decisions, proposed patches, engineering assumptions, and unresolved questions separately.
- Do not silently promote an unresolved issue into a normative rule.
- Build conformance tests only against an explicitly selected and sufficiently stable source baseline.
