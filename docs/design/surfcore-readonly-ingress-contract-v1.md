# SurfCore Read-only Ingress Contract v1

> Status: proposal for a separately reviewed SurfCore change. This repository does not implement the HTTP/IPC server.
> Compatibility target: SurfCore v0.8.8 source commit `0deb8261afe4c31b3127759ee4de36a1439cf422`.
> Security posture: observation-only, local transport, untrusted payloads, no action dispatch.

## 1. Why a new interface is required

The pinned `src/bridge.js` currently writes `state/qq-public-feed.jsonl` only for selected group messages. The record is intentionally redacted/truncated and contains only `at`, `groupId`, `senderId`, `senderName`, `isOwner`, and `text`. The call site is gated to `kind === 'group'`, non-empty plain text, and non-command content. Private messages are explicitly excluded. It is therefore a specialized QQ→Bilibili memory feed, not a complete or stable CSD observation interface.

The QQ ingress path already receives OneBot event fields in `handleIncoming(kind, id, event, cfg)`: `message_id` / `msg_id` / `message_seq`, `time`, `user_id`, optional `group_id`, `sender`, and `message` segments. The adapter must not read bridge state files or parse the existing human-oriented feed. Instead, SurfCore should expose a dedicated versioned projection at the point where these events are normalized.

The existing local console is not an acceptable shortcut. It is a broad management API protected by `consoleToken`, and includes configuration, session, send, reset, and other privileged operations. Giving that token to the CSD adapter would violate least privilege.

## 2. Transport

Preferred first implementation: a dedicated loopback-only HTTP listener owned by SurfCore, separate from the management console.

- Bind only to `127.0.0.1`; reject any non-loopback bind configuration.
- Use a dedicated random observation credential, distinct from `consoleToken`, agent tokens, SnowLuma access tokens, and Bilibili cookies.
- Authenticate every request with a dedicated header, compare tokens in constant time, and fail closed if missing or invalid.
- Do not accept `Origin`/Host values that resolve to non-loopback; do not support reverse proxy or remote binding in v1.
- Only GET routes exist. No POST, generic command route, arbitrary URL fetch, filesystem path, or tool dispatch.
- Bound request line/header size, page size (max 500), response bytes (max 1 MiB), execution time, and per-client request rate.
- Never log credential values, message content, cookies, or raw account identifiers.
- Expose health/version metadata only; never expose configuration or private state.

A future stdio IPC transport may replace HTTP, but it must preserve the same DTO and privilege boundary.

## 3. QQ cursor feed

### Route

`GET /v1/observations/qq?after_cursor=<uint>&limit=<1..500>`

The cursor is scoped to one SurfCore account/feed identity. The response contains:

```json
{
  "schema_version": 1,
  "stream_ref": "opaque:qq-stream:...",
  "after_cursor": 120,
  "next_cursor": 128,
  "records": [
    {
      "schema_version": 1,
      "platform": "qq",
      "record_id": "opaque-stable-source-record-id",
      "cursor": 124,
      "external_ref": "opaque-source-message-ref",
      "observation_kind": "qq.message.incoming",
      "account_ref": "opaque-qq-account-stream-ref",
      "conversation_kind": "group",
      "conversation_ref": "opaque-stable-conversation-ref",
      "sender_ref": "opaque-stable-sender-ref",
      "actor_role": "sender",
      "content_origin": "source_provided",
      "modality": "text",
      "content": "normalized text or explicit bounded media placeholder",
      "source_ref": "surfcore://qq/message/opaque-source-message-ref",
      "observed_at": "2026-11-18T08:00:00+00:00",
      "received_at": "2026-11-18T08:00:01+00:00",
      "extraction_method": "onebot_v11_segment_normalizer",
      "historical": false,
      "coverage": {
        "modality": "text",
        "extraction_method": "onebot_v11_segment_normalizer",
        "complete": true,
        "start_ms": null,
        "end_ms": null,
        "missing_ranges_ms": [],
        "notes": []
      }
    }
  ]
}
```

Rules:

1. `cursor` is a monotonically increasing integer within `stream_ref`; it is assigned by SurfCore when the normalized record is appended, not copied from QQ message IDs.
2. `record_id` and `external_ref` are stable opaque identifiers. The same source message redelivered after reconnect must retain its identity.
3. `account_ref` on every record must equal the response `stream_ref`; the consumer rejects cross-stream records. `conversation_kind` is exactly `private` or `group`. Conversation and sender identifiers are stable opaque references; do not export raw QQ numbers by default.
4. `observed_at` comes from the source event timestamp when valid; `received_at` is the SurfCore receipt time. If source time is missing/invalid, preserve that fact in coverage notes and use receipt time only as the event's observation time with an explicit fallback note.
5. `historical` distinguishes backfilled/history-catch-up messages from live events. Do not silently relabel backfill as live.
6. Text normalization must preserve provenance. Media not yet supported by the adapter must appear as a typed placeholder and make coverage partial; do not pretend an image/audio/video was understood.
7. The feed is append-only for the retention window. Cursor replay is supported. Empty pages may advance `next_cursor` across source records deliberately filtered by the feed policy.
8. Do not include the bot's own outgoing messages in the incoming feed. Notices are a separate allowlisted observation kind and must not be mixed with user messages.
9. The feed applies the existing configured allow/deny policy before export. Private conversations require explicit opt-in in the SurfCore configuration; group feeds require an explicit group allowlist. The observation API must not broaden the bridge's chat/reply authorization.
10. A read request must not mark messages read, acknowledge them upstream, create a DSH turn, wake the agent, send a reply, or mutate QQ/SurfCore session state.

### Cursor checkpointing

The consumer sends its last **durably ingested** cursor. It writes every returned CSD event first, then stores `next_cursor`. A crash before checkpoint persistence causes replay. CSD idempotency handles duplicate delivery. The API must not expose an acknowledgement endpoint: consumer checkpoint state belongs to the CSD host.

## 4. Bilibili read-only observation

### Routes

- `GET /v1/observations/bilibili/video/<canonical-BV-id>`
- Optional bounded subresources may be added for `metadata`, `subtitles`, `comments`, and `danmaku`.

Only canonical BV identifiers are accepted. Reject arbitrary URLs, shell fragments, command arguments, and path traversal. Responses use the same versioned observation record shape, with:

- `external_ref`: canonical BV identifier;
- `context_kind`: exactly `video`;
- `context_ref`: the same canonical BV identifier as `external_ref`;
- `observation_kind`: one of `bilibili.video.metadata`, `bilibili.video.subtitle`, `bilibili.video.comment`, or `bilibili.video.danmaku`;
- `actor_role`: role associated with the record — `uploader`, `subtitle_contributor`, `comment_author`, or `danmaku_sender`, matching the observation kind;
- `actor_ref`: stable opaque actor identity when the source exposes one; omit it rather than inventing identity when unavailable;
- `parent_ref`: optional opaque parent/root comment reference, allowed only for comment records;
- `content_language`: optional BCP 47 language tag, allowed only for subtitle records;
- `source_artifact_ref`: opaque reference to SurfCore-managed cache/artifact, never a filesystem path;
- `coverage`: explicit partial/unavailable notes for missing subtitles, inaccessible comments, sampled frames, or failed extraction.

The adapter preserves these as structured CSD fields. It never infers a person identity from display text. A missing actor identity remains missing even when the actor role is known.

v1 does not expose image/frame binary content through this text contract. It must not expose any write operation: like, favorite, follow, comment, reply, private message, dynamic publish/edit/delete, or danmaku send.

## 5. Adapter mapping requirements

The project-side adapter accepts only the exact versioned DTO fields. It must:

- reject unknown fields and unsupported schema versions;
- require the QQ conversation/sender/history metadata and Bilibili video/actor-role provenance above;
- keep all content `untrusted=true`;
- retain account, conversation, sender, source-message, cursor, and historical provenance in the CSD event payload (not in free-form content); the generic ObservationEvidence contract exposes `context_kind`, `context_ref`, `actor_ref`, `actor_role`, `parent_ref`, `content_language`, `source_sequence`, and `historical`;
- derive deterministic observation/event identity from platform + opaque account/stream reference + stable source record ID;
- reject cursor regression, out-of-page records, duplicate record IDs, and oversized batches;
- never persist the cursor itself or call SurfCore.

The mapper now validates and carries the QQ conversation/sender/history fields and binds every batch record's `account_ref` to the batch `stream_ref`; the transport remains unimplemented.

## 6. Security and privacy acceptance tests

- Missing/wrong observation credential returns 401/403 and reveals no endpoint details.
- A non-loopback Host/bind attempt is rejected.
- The observation credential cannot access the management console or any write route.
- GET requests have no side effects and never trigger a DSH prompt or QQ response.
- Private messages are absent unless private-feed opt-in is explicitly enabled.
- Denied users and non-allowlisted groups are not exported.
- Raw QQ identifiers, SnowLuma access token, console token, agent tokens, Bilibili cookies, local paths, and message bodies never appear in diagnostics.
- Cursor replay returns identical record identities and payloads.
- Bilibili write commands are not routable through the observation service.
- All returned evidence is treated as untrusted by the CSD adapter.

## 7. Non-claims

This document is a proposed contract, not a SurfCore implementation. The pinned source review does not prove the user's currently installed version or account state. No live connection, private-message export, local credential, or platform action has been tested.
