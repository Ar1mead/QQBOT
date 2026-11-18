# SurfCore QQ Journal — Patch-Ready Implementation Blueprint

> Status: implementation blueprint for a separately reviewed SurfCore upstream patch.
> Target source: `Mieksido/surfcore` v0.8.8, commit `0deb8261afe4c31b3127759ee4de36a1439cf422`.
> This document is not an implementation. No SurfCore upstream file has been modified.

## 1. Verified source constraints

The pinned `package.json` establishes:

- Node.js engine requirement: `>=22.13.0`.
- ESM project (`"type": "module"`).
- Existing tests are standalone `scripts/test-*.mjs` programs run with Node, not a conventional Jest/Vitest setup.
- `src/bridge.js` already imports `node:fs`, `node:path`, and `node:crypto`; it also imports `hardenDir` from `src/state-acl.mjs`.
- `src/owner-audit.js` is a local single-writer JSONL precedent, but it skips malformed lines when reading and rotates/truncates under different semantics. It must not be reused as the journal implementation.

At the pinned `src/bridge.js` callback site:

- Private incoming messages are self-filtered, then passed to `handleIncoming('private', ...)`.
- Group incoming messages are self-filtered, then passed to `handleIncoming('group', ...)`.
- These two callbacks are the only v1 capture tap points. Notice handlers are out of scope.
- The capture tap must run after the existing self-message rejection and before the existing `handleIncoming` call.

## 2. Proposed file-level patch

### New: `src/observation-policy.js`

Keep policy as pure functions with no filesystem, network, DSH, or QQ SDK dependency.

Proposed exports:

- `DEFAULT_OBSERVATION_INGRESS_CONFIG`: all disabled; private/group allowlists empty.
- `normalizeObservationIngressConfig(raw)`: accept only known fields, clamp configured limits, reject malformed allowlist values, and never inherit `allowAllWhenEmpty`.
- `shouldCaptureIncoming({ config, conversationKind, conversationId, senderId, selfId, event })`: return a structured allow/deny result with a stable reason code; never return raw identifiers in diagnostics.
- `extractIncomingText(event, maxChars)`: allowlisted OneBot text-segment extraction only. Unsupported segments must be explicitly omitted/partial or cause the record to be rejected; never stringify arbitrary nested payloads.

Policy invariants:

1. Global ingress, conversation-kind switch, and explicit non-empty conversation allowlist must all permit export.
2. Existing deny-user and deny-conversation rules are additional vetoes, never grants.
3. Self-authored events, non-message events, malformed IDs, and unsupported message kinds are rejected.
4. Existing chat mode, wake eligibility, session state, and reply behavior do not affect export permission.
5. Empty allowlists always mean export nothing.

### New: `src/observation-journal.js`

Implement a dedicated append-only journal. Do not import bridge logic or the SnowLuma SDK.

Proposed public surface:

- `createObservationJournal(options)`
- `await journal.open()`
- `await journal.capture(event, { conversationKind })`
- `await journal.readPage({ afterCursor, limit })` (internal/test use in this first patch; not an HTTP route)
- `journal.health()`
- `await journal.close()`

Internal responsibilities:

- Generate/load a dedicated HMAC key; never reuse console, DSH, SnowLuma, or Bilibili credentials.
- Derive domain-separated opaque account, conversation, sender, and source-record references.
- Serialize all appends through one promise queue shared by private and group callbacks.
- Validate and normalize a minimal DTO before allocating a cursor.
- Append one JSONL record and await file-handle `sync()` before reporting durable success.
- Advance the in-memory cursor only after successful sync.
- On startup, validate every complete line and rebuild the next cursor from the journal itself.
- Repair only a final unterminated byte tail. A malformed complete line, stream mismatch, duplicate cursor, or cursor regression marks the journal unhealthy and blocks reads/writes; never skip corruption.
- Keep health counters coarse and redact message bodies, raw IDs, paths, and credentials from logs.

### Existing: `src/bridge.js`

Make the smallest possible integration:

1. Construct/open the journal only when the new observation ingress setting is explicitly enabled.
2. Add a small local helper that attempts capture and catches all capture errors.
3. In the private callback, after the current self-message guard, call the helper with `conversationKind: 'private'`.
4. In the group callback, after the current self-message guard, call the helper with `conversationKind: 'group'`.
5. Call the original `handleIncoming` exactly once, with the same arguments and error behavior as before.
6. If journal initialization fails, log a redacted, rate-limited health warning and continue normal bridge operation.

Do not put capture inside `handleIncoming`; its existing mode/session/deny gates and wake/reply behavior are deliberately separate from observation consent.

### Configuration integration

Add one isolated `observationIngress` block to the existing bridge config normalization path. Do not alter existing `allow`, `deny`, `allowAllWhenEmpty`, or chat-mode semantics. The exact UI/config persistence surface must be checked before adding settings UI; the first patch may require explicit config-file opt-in only.

All defaults remain off. No listener, account export, or journal file should be created when disabled.

## 3. Deliberate first-patch limit: no HTTP and no automatic pruning

The first upstream patch should implement only policy + durable journal + callback tap + tests.

- Do not add the HTTP server in this patch.
- Do not add a CSD polling client.
- Do not add Bilibili support.
- Do not add any message send, wake, session, mark-read, or account mutation behavior.
- Do not implement automatic retention deletion until segment boundaries, retained cursor floor, and crash-safe rotation have their own tests.

To avoid silent data loss, the first patch should enforce a hard journal byte ceiling. When full, capture fails closed, health becomes degraded, and ordinary SurfCore chat continues. It must not truncate or rotate away records. A later retention patch can implement bounded segments plus explicit `cursor_expired` semantics.

This is intentionally more conservative than the eventual v1 transport target. The journal must not claim retention support until it can prove the cursor-gap contract.

## 4. Test plan using the repository's existing conventions

Add focused scripts, for example:

- `scripts/test-observation-policy.mjs`
- `scripts/test-observation-journal.mjs`
- `scripts/test-observation-bridge-wiring.mjs`

Use temporary directories and synthetic OneBot fixtures only. Never connect to a real QQ account or DSH instance.

Required assertions:

### Policy

- Default config disables all capture.
- Empty private/group allowlists export nothing.
- Private and group permissions are independent.
- Deny entries override allow entries.
- Self-authored and unsupported event types are rejected.
- Chat mode/wake/reply configuration cannot broaden observation export.
- Unknown config fields and malformed allowlists fail closed.

### Journal

- HMAC references are stable and domain-separated; raw numeric IDs do not appear in serialized records.
- Private and group concurrent captures produce one strictly increasing cursor sequence.
- The append promise resolves only after sync; injected write/sync failures do not advance the cursor.
- Restart recovers the last cursor from complete records.
- A final incomplete tail is truncated to the last newline.
- Corrupt complete lines and cursor regressions make the journal unhealthy.
- Duplicate source delivery retains a stable record identity; changed content under the same identity remains detectable by the CSD idempotency conflict path.
- Byte ceiling fails closed without deleting or truncating prior records.
- Journal failure never suppresses the original `handleIncoming` call.

### Bridge regression

- Both private and group callbacks invoke capture only after self-message filtering.
- The original `handleIncoming` is invoked exactly once with unchanged arguments.
- Ingress disabled means no journal file/key/listener is created and existing callback behavior is unchanged.
- Capture failure does not throw into or short-circuit normal QQ handling.

Run the new scripts directly with Node and include them in an existing aggregate test script only after reviewing its runtime and duration implications. Also run relevant existing bridge/QQ regression scripts and the existing privacy scan.

## 5. Security and Windows-specific acceptance gates

- HMAC key creation must be atomic and resistant to concurrent startup.
- File permissions must be verified on Windows, not inferred from POSIX `chmod` calls. Reuse existing ACL helpers only after confirming their exact behavior for the journal directory and key file.
- Never log raw errors if they can include paths or sensitive values; map errors to bounded reason codes and keep detailed diagnostics local only where safe.
- No third-party extension code is executed by this journal module.
- This remains in-process code and is not an OS sandbox. The worker isolation requirement still applies before any untrusted adapter code is loaded.

## 6. Patch sequence and review gates

1. Implement pure policy module and policy tests.
2. Implement journal storage/recovery and journal tests.
3. Add the disabled-by-default bridge tap and wiring regression tests.
4. Run focused scripts, existing QQ/bridge regressions, privacy scan, and syntax checks on Linux and Windows CI.
5. Review the complete diff for data minimization, error paths, and config compatibility.
6. Only after this patch is reviewed should a separate change add loopback GET-only HTTP, dedicated bearer auth, bounded pagination, and explicit retention-gap behavior.
7. Only after that exact API exists should this project's Python adapter gain a live HTTP client.

No step in this plan authorizes modifying the SurfCore upstream repository automatically. The upstream patch must remain a separate, reviewable change.

## 7. Status

- Source baseline and callback placement: reviewed at the pinned commit.
- Node/ESM/test conventions: checked from the pinned `package.json` and existing test script.
- Journal implementation: not started.
- HTTP service/client: not implemented.
- Real QQ/DSH connection: not tested.
- User-local test: not performed.

## 8. Isolated reference implementation in this repository

A first executable reference slice now exists under `integrations/surfcore-qq-journal/`:

- `observation-policy.mjs` — disabled-by-default configuration normalization, independent private/group allowlists, deny overrides, strict OneBot message provenance, and text-only segment extraction with explicit partial-coverage notes.
- `observation-journal.mjs` — injected HMAC key and mandatory host ACL callback, domain-separated opaque references, serialized private/group appends, synced JSONL writes, strict startup recovery, incomplete-final-tail repair, corruption fail-closed behavior, bounded page reads, and a hard capacity ceiling that preserves existing records.
- `observation-journal.test.mjs` — synthetic fixtures for policy, privacy, cursor ordering, duplicate source identity, restart recovery, corruption, partial media, and capacity behavior.
- `.github/workflows/surfcore-qq-journal-reference.yml` — Node 22 Ubuntu/Windows test workflow.

This code is a reference implementation in the individual-AI repository, not a SurfCore upstream patch. It is not imported by SurfCore, has no QQ SDK connection, and does not provision or persist the HMAC key. A production SurfCore caller must supply a dedicated random key and a verified Windows/Linux ACL-hardening callback.

### Contract cross-check with the Python mapper

The journal record is shaped to match the existing exact-key mapper in `adapters/platforms/surfcore/mapping.py`:

- Every record has the required base fields plus QQ provenance: `account_ref`, `cursor`, `conversation_kind`, `conversation_ref`, `sender_ref`, `historical`, and `actor_role`.
- `account_ref` equals the page `stream_ref`.
- The page envelope is exactly `schema_version`, `stream_ref`, `after_cursor`, `next_cursor`, and `records`.
- The first reference implementation emits only `qq.message.incoming`, with `historical=false`, `actor_role=sender`, text modality, explicit coverage, and opaque source/account/conversation/sender references.
- No `stream_ref`, token, raw QQ ID, or unrecognized convenience field is added to an individual record.

The reference test workflow has been added, but no passing result has yet been confirmed through the available status lookup. Treat these files as unverified until the Ubuntu and Windows jobs finish successfully.
