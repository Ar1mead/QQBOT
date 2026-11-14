# Memory Proposal Provider Contract

> Status: **engineering interface proposal and prototype documentation; not a frozen CSD specification**  
> Implementation: `core/csd/proposals.py`

## 1. Purpose

The proposal provider is the replaceable semantic-analysis boundary between observed evidence and CSD's authoritative state path.

A provider may later call a model API, a local model, or a different cognitive service. Its output is always untrusted candidate data. It cannot accept memory, update personality, create goals, or trigger external actions.

This interface does not select a model vendor or contain API credentials.

## 2. Input

The pipeline supplies:
- one persisted observation event, including its immutable event ID and evidence payload;
- the current accepted-state version derived from CSD's durable decision history.

The provider receives this context outside a SQLite write transaction. It may return zero candidates.

The first implementation supports one observation per proposal-generation call. It does not yet support cross-event synthesis or long-term memory consolidation.

## 3. Output

The provider returns zero or more `MemoryCandidate` values containing only:
- `proposal_id`;
- `memory_kind`;
- `candidate_content`;
- `uncertainty_label`;
- optional `confidence` in the inclusive range 0 to 1.

The pipeline, not the provider, attaches:
- the exact observation event ID as evidence provenance;
- provider identity and version;
- the state version observed before provider execution;
- a new event ID, timestamp, and correlation ID.

This prevents the provider from choosing its own evidence references or claiming a different CSD state version in this prototype.

The pipeline rejects unsupported output types, duplicate proposal IDs in one batch, invalid confidence values, and malformed fields. The CSD event schema rejects additional authority-like fields such as `accepted`, `transition_id`, or executable instructions.

## 4. Lifecycle

1. Read the observation and current state version from CSD.
2. Call the provider outside the database transaction.
3. If it returns no candidates, stop without changing CSD.
4. Convert each candidate into a typed proposal event.
5. Submit the proposal event through Event Submit.
6. Leave it pending.
7. A separate CSD-owned evaluation call may accept, reject, defer, or request more evidence.

Proposal generation does not automatically evaluate or accept the candidate. Provider timeout/failure does not mutate CSD state.

If state changes while a provider is running, the pipeline retains the earlier state version. CSD's later evaluation detects the stale version and defers the proposal rather than applying it blindly.

## 5. Trust boundary

The provider's candidate text is untrusted model output. It must not be interpreted as executable instructions. No provider output is passed to a shell, browser, filesystem writer, platform action, or tool executor.

The provider ID and version are provenance labels, not cryptographic authentication. This Python interface is not a security boundary against hostile code in the same process.

## 6. Current limits

- One observation per call.
- Text-only observation fixture.
- No model adapter is included.
- No semantic entailment or hallucination check is performed.
- No evidence-span extraction, multi-source synthesis, or conflict resolution.
- No candidate editing/revision lifecycle; a changed proposal uses a new proposal ID.
- No automatic acceptance or external side effects.

The first production-facing provider must add source-grounded claim/evidence mapping and a separate semantic review contract before its output can be considered suitable for durable autobiographical memory. The deterministic test policy in the current slice is not a production acceptance policy.
