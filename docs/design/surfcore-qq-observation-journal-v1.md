# SurfCore QQ Observation Journal v1

> Status: implementation specification for a separately reviewed SurfCore change.
> Source baseline: SurfCore v0.8.8, commit `0deb8261afe4c31b3127759ee4de36a1439cf422`.
> Scope: inbound QQ text observations only. No Bilibili transport, no message sending, no DSH turn creation.
> This repository does not implement the journal or HTTP service. No upstream SurfCore source was changed during this design pass.

## 1. Design decision

Add a dedicated observation journal beside SurfCore's existing QQ receive path. Do not reuse `state/qq-public-feed.jsonl`, `sessions.json`, `social-v2.json`, the DSH console API, or the current management token.

The journal is an append-only, bounded, versioned record stream with its own monotonically increasing cursor. The HTTP reader is a separate loopback-only, GET-only service using an observation-specific credential.

The journal is a source-side transport buffer, not CSD memory and not an interpretation layer. CSD remains responsible for durable cognitive history, memory formation, retrieval, and interpretation.

## 2. Pinned source facts and callback placement

At the pinned source commit:

- `src/bridge.js` creates one `SnowLumaWebSocketClient` with reconnect enabled.
- The private callback at approximately line 16966 rejects self-authored messages by comparing `event.user_id` and `event.self_id`, then calls `handleIncoming('private', event.user_id, event, cfg)`.
- The group callback immediately after it rejects self-authored messages using `event.sender.user_id` and/or `event.user_id`, then calls `handleIncoming('group', event.group_id, event, cfg)`.
- `handleIncoming` applies the existing bridge mode/session and deny gates, normalizes OneBot segments, and eventually performs memory, wake, and reply work.
- The existing `appendPublicFeed` is called much later in the group-message path. It is group-only, only records selected plain text after existing processing gates, and uses a capped logger that rotates one backup and may truncate on rotation failure.
- `loadConfig()` currently normalizes `allow.private`, `allow.groups`, `deny.users`, `deny.private`, `deny.groups`, and `allowAllWhenEmpty`. These settings govern the existing bridge behavior; they are not sufficient consent for a separate long-term observation export.
- SurfCore already has `src/owner-audit.js` as a useful local pattern for a single-writer JSONL component with health reporting and rotation. It is an audit log, not a ready-made event journal: its retention/rotation behavior must not be copied blindly.

### Exact insertion point

In each of the two OneBot callbacks:

1. Keep the existing self-message rejection first.
2. Await a new `observationJournal.capture(event, { conversationKind })` call inside its own try/catch.
3. Continue to call the existing `handleIncoming(...)` exactly as before, whether capture succeeds or fails.

Do not insert the tap inside `handleIncoming`: that function intentionally returns early for current mode, session, sender-deny, and other chat-processing policy. Observation export has a separate, explicit policy and must not inherit DSH wake/reply side effects. Conversely, the tap must not bypass its own explicit export allowlist.

Capture failure must never prevent normal SurfCore chat handling. It must update a health/error counter and emit rate-limited diagnostics without message bodies, raw QQ identifiers, or credentials.

## 3. Export policy and privacy defaults

Add a separate config block, conceptually:

```json
{
  "observationIngress": {
    "enabled": false,
    "private": {
      "enabled": false,
      "conversationAllowlist": []
    },
    "groups": {
      "enabled": false,
      "conversationAllowlist": []
    },
    "maxRecordChars": 16000,
    "retention": {
      "maxBytes": 67108864,
      "maxAgeDays": 30
    },
    "http": {
      "enabled": false,
      "port": 3101
    }
  }
}
```

This is illustrative configuration, not a patch to the existing `config.json`. Exact names and UI exposure require a separate review.

Rules:

- All switches default off. An empty allowlist means export nothing; there is no `allowAllWhenEmpty` behavior for observation.
- Private-message export requires both the global ingress switch and explicit private enablement plus a non-empty private conversation allowlist.
- Group export requires the global switch, group enablement, and a non-empty group allowlist.
- Existing bridge allowlists may be used as an additional upper-bound check, but they never grant observation consent by themselves. Existing deny users/conversations always override export.
- Export policy is evaluated independently of chat mode, wake eligibility, or whether SurfCore replies. Do not export a message merely because it reached a DSH prompt.
- Do not export bot-authored outgoing messages in v1.
- Do not export notices, poke events, friend requests, group membership changes, or arbitrary OneBot event types in v1.
- The first slice is text-only. For a message containing unsupported media segments, either omit the whole record or retain only a clearly typed bounded placeholder with `coverage.complete=false`; never claim the media was understood.
- Apply a strict per-record character/byte limit. Reject or truncate only with explicit coverage notes; do not silently claim complete content.
- Do not include display names, QQ numbers, group numbers, raw OneBot payloads, cookies, tokens, local paths, or arbitrary nested event fields.
- Do not run semantic PII detection as a substitute for explicit consent. The explicit per-conversation allowlist is the primary boundary; deterministic secret-pattern redaction may be defense-in-depth but can never make unrestricted export safe.

The default installation therefore remains behaviorally unchanged and exports no new observations.

## 4. Opaque identifiers

The API must not expose raw QQ account, conversation, or sender identifiers by default.

Use a dedicated local HMAC key, separate from the HTTP bearer credential:

- Generate the key with a cryptographically secure random generator on first explicit enablement.
- Store it under the SurfCore state directory with restrictive filesystem permissions/ACL. Never return it through HTTP or log it.
- Derive opaque stable references using domain-separated HMAC-SHA-256, for example `HMAC(key, "conversation:private:" + rawConversationId)`.
- Derive sender references with a distinct prefix and source message identity with a distinct prefix.
- Include a key-version identifier in internal state so future key rotation is explicit. Rotating the key changes opaque references and therefore requires a documented new stream identity; do not silently rotate it.
- Use the stream/account opaque reference plus stable source message identity as the record identity input. A repeated source message must map to the same `record_id` even if delivered again after reconnect.

A hash without a secret is not adequate for QQ numeric identifiers because the input space is enumerable.

## 5. Journal record and cursor

Each complete JSONL line is one v1 record. The record contains only the allowlisted fields required by the CSD mapper:

- `schema_version: 1`
- `platform: "qq"`
- `record_id`: stable opaque source-record identity
- `cursor`: positive integer allocated by the journal, monotonically increasing within one `stream_ref`
- `external_ref`: opaque stable source message reference
- `observation_kind`: `qq.message.incoming`
- `account_ref`: opaque stream reference; equal to the response `stream_ref`
- `conversation_kind`: `private` or `group`
- `conversation_ref`: opaque stable conversation reference
- `sender_ref`: opaque stable sender reference
- `actor_role: "sender"`
- `content_origin`, `modality: "text"`, `content`
- `source_ref`: opaque SurfCore source reference, not a URL containing raw IDs
- `observed_at`: valid source event time when available
- `received_at`: local receipt time
- `extraction_method`: fixed versioned OneBot v11 text-normalizer identifier
- `historical: false` in v1
- `coverage`: explicit completeness and omission notes

The journal cursor is not `message_id`, `msg_id`, or `message_seq`. Those are source references, not a proven monotonic durable feed checkpoint. Keep them only as inputs to opaque source identity.

The v1 callbacks observe live incoming events only. History catch-up/backfill is excluded; do not set `historical=true` for ordinary live callbacks or infer historical status from timestamps. A later backfill feature must be a separately specified source path with its own ordering and duplicate semantics.

## 6. Append, durability, ordering, and recovery

The bridge is the single writer for this journal. The initial implementation should use one serialized asynchronous writer and a single open append handle.

For each allowed event:

1. Normalize and validate the minimal DTO; reject unsupported/malformed fields.
2. Compute stable opaque references and deterministic `record_id`.
3. Assign the next cursor for this stream.
4. Serialize one JSON object plus exactly one newline.
5. Append the complete line and await a file-handle sync before treating capture as durable.
6. Only after successful append/sync, advance the in-memory next cursor and success counters.
7. Then allow the callback to continue to the unchanged `handleIncoming` path.

If the append or sync fails, do not advance the in-memory cursor; report capture failure and continue normal chat handling. Never silently skip a cursor while reporting success.

Startup recovery:

- Scan the active journal from its beginning (or from a verified segment index) and validate every complete line, schema version, stream identity, and strictly increasing cursor.
- A final unterminated byte tail may be truncated back to the last newline because it is not a complete committed record. A malformed complete line, cursor regression, or stream/key mismatch is a hard integrity error: mark the journal unhealthy and refuse to serve it until repaired. Do not silently skip corrupt complete records.
- Reconstruct the next cursor from the last valid complete record. The durable journal, not a separate cursor counter file, is authoritative.
- A duplicate source message redelivered by OneBot may be appended with a later journal cursor, but it must retain the same deterministic `record_id`. The CSD mapper/event identity then makes the repeated event idempotent; if the same ID arrives with changed content, CSD conflict detection must surface it rather than silently overwrite it.
- Do not promise exactly-once delivery. The guarantee is durable append plus at-least-once read/replay and deterministic event identity.

### Retention and gaps

Do not copy the existing capped logger's “rename one backup / truncate on failure” behavior.

Use bounded segment files or a reviewed rotation implementation with an explicit retained cursor floor. If old data is pruned, expose `earliest_cursor` and `latest_cursor`. A request whose `after_cursor` predates the retained range must return a clear `410 Gone` / `cursor_expired` response containing the earliest available cursor. Never return a normal empty page that hides a retention gap.

The first implementation should prefer a small fixed total size and conservative age cap. Rotation/pruning must be serialized with append and reads. A segment may be deleted only after its maximum cursor is below the declared retention floor. CSD owns its own durable checkpoint; SurfCore has no acknowledgement/delete endpoint.

## 7. Read-only HTTP surface

Use a separate listener, not the existing management console server:

- Bind only to `127.0.0.1`; do not permit LAN, wildcard, IPv6-any, or configurable remote binding.
- Use a dedicated random observation bearer credential stored separately from `consoleToken`, DSH launch tokens, SnowLuma access tokens, and Bilibili cookies.
- Require the credential on every request and compare it in constant time.
- Expose only `GET /v1/observations/qq` and a minimal `GET /v1/observations/health`.
- Reject all other methods and paths. No generic command route, tool dispatch, filesystem path, arbitrary URL fetch, console proxy, or write endpoint.
- Validate the Host header as loopback and reject unexpected Origin headers. Do not rely on CORS as authentication.
- Bound page size to 1–500 records and response size to 1 MiB. Bound header size, execution time, and request rate.
- Never include raw IDs, message content, credentials, or filesystem paths in logs or health output.
- The health route reports only schema version, enabled/disabled, journal writable/integrity status, retained cursor range, and coarse counters. It must not reveal the credential or private conversation allowlist.

Suggested route:

`GET /v1/observations/qq?after_cursor=<uint>&limit=<1..500>`

Response envelope:

```json
{
  "schema_version": 1,
  "stream_ref": "opaque:qq-stream:...",
  "after_cursor": 120,
  "next_cursor": 128,
  "earliest_cursor": 1,
  "records": []
}
```

`next_cursor` is the last cursor actually included in the page, or equals `after_cursor` when no records are returned. Do not advance it over records that were never appended. If policy filters an event before append, it receives no journal cursor. The consumer's checkpoint sequence is therefore contiguous across exported records, not across all raw QQ traffic.

The service does not acknowledge reads. The CSD host writes all returned events durably first, then stores `next_cursor`. A crash before checkpoint persistence causes replay.

## 8. Consumer ordering with the existing adapter

The existing Python mapper already validates a bounded QQ page, requires monotonically increasing record cursors, checks that each record's `account_ref` matches `stream_ref`, and returns a proposed cursor without persisting it.

The consumer must:

1. Read the last CSD-durable cursor for the exact stream reference.
2. Request a page after that cursor.
3. Validate the entire envelope and map every record before applying any checkpoint.
4. Durably submit all resulting CSD events.
5. Persist the returned `next_cursor` only after every event is durable.
6. On any partial failure, retain the old cursor and replay the page.

The transport must not save cursor state in SurfCore, and SurfCore must not know whether CSD accepted an event.

## 9. Required tests before merging an upstream implementation

### Policy and privacy
- All defaults disabled; empty allowlists export nothing.
- Private export requires both explicit private enablement and a conversation allowlist.
- Group export requires its own explicit allowlist.
- Existing deny users/conversations override export.
- Bridge mode/wake/reply state does not broaden export.
- Bot-authored events, notices, and unsupported event types are excluded.
- Raw QQ IDs, display names, tokens, and raw OneBot payloads never appear in records, API responses, or logs.

### Journal integrity
- Cursor allocation is monotonic and serialized under concurrent private/group callbacks.
- Complete append is synced before capture reports success.
- Restart recovers the last cursor from the journal.
- An unterminated final tail is repaired safely.
- Corrupt complete lines and cursor regressions mark the journal unhealthy.
- Append/sync failure does not stop normal `handleIncoming`.
- Duplicate source messages retain stable record IDs; changed payload under the same source ID is visible to CSD conflict detection.
- Retention returns an explicit expired-cursor error and never hides a gap.
- Rotation cannot race with append or page reads.

### HTTP boundary
- Only loopback bind succeeds.
- Missing/invalid credential is rejected.
- Observation credential cannot access management console or write operations.
- Only the two documented GET routes are exposed.
- Oversized page, response, header, invalid cursor, unexpected Host/Origin, and rate-limit cases fail closed.
- GET requests never wake DSH, create sessions, mark messages read, or send QQ messages.

### Compatibility and regression
- Existing QQ private/group callback handling is unchanged when ingress is disabled.
- Journal failure does not suppress or duplicate the existing `handleIncoming` call.
- No change to SurfCore's existing chat allow/deny behavior.
- The Python adapter accepts the produced fixture and rejects malformed/unknown fields.
- Windows and Linux tests cover filesystem/ACL differences; real DSH/OneBot integration requires a separate owner-run validation.

## 10. Explicit non-claims and next gate

This specification is grounded in the pinned source, but it is not implemented. It does not prove the user's currently installed SurfCore build, QQ account connection, or actual data capture. The existing Python DTO mapper still consumes supplied test data only; no live HTTP client exists.

Next engineering gate: create a narrowly scoped upstream SurfCore patch (separate repository/PR) implementing the journal module and callback tap with ingress disabled by default, plus unit tests. Do not add the HTTP listener until journal recovery, privacy policy, and cursor semantics pass tests. Do not add a client to this CSD repository until the exact upstream route and response implementation exist and are reviewed.
