# SurfCore ↔ CSD Integration Assessment and Plan

> Status: **integration design proposal; no live adapter is implemented**
> Reviewed source: `Mieksido/surfcore` commit `0deb8261afe4c31b3127759ee4de36a1439cf422` (package version `0.8.8`).
> Scope: reuse SurfCore's existing QQ and Bilibili connectivity; do not build duplicate platform connectors.

## 1. Decision

SurfCore is the existing platform capability layer for QQ and Bilibili. The individual-AI repository should build a narrow integration adapter between SurfCore and the existing platform-neutral Observation contract / CSD Observation v2. It must not replace SurfCore's QQ bridge or Bilibili toolchain, and must not adopt SurfCore's scheduler, purpose engine, memory cards, persona, or platform registry as the individual's authoritative cognition or identity.

This decision corrects the earlier generic platform plan that treated Bilibili/QQ connectors as future independent projects. The platform connection already exists in SurfCore source; what is missing is a safe, stable, machine-readable ingress contract into this project's CSD.

## 2. What the pinned SurfCore source actually provides

### QQ

- `src/bridge.js` is a separate Node process. It receives OneBot v11 WebSocket events from SnowLuma, normalizes private/group messages, tracks message IDs/timestamps/session identity, and forwards prompts to DSH.
- The bridge also consumes DSH's `api.events.mux()` stream for turn/output lifecycle and sends completed content back through QQ.
- Its local console HTTP server binds to loopback. Most endpoints require the broad `consoleToken`; agent-token access is separately constrained by endpoint allowlists.
- Existing `state/social-v2.json` and `state/qq-public-feed.jsonl` are internal state formats, not a stable project integration API. The public feed is group-only and therefore cannot represent all QQ observations.
- The bridge already has message provenance and deduplication concepts, but its current external interface is designed for SurfCore/DSH operation, not a separate CSD consumer.

### Bilibili

- The pinned `plugins/surfcore/tools/bili.mjs` exposes a command map with both read and write operations. The source labels read-only commands separately from commands that can like, favorite, comment, send private messages, publish dynamics, or send danmaku.
- Read paths include video metadata/subtitles/comments/danmaku, feed/search, watch history, and related inspection commands.
- Some read commands print human-oriented console text rather than a versioned JSON result. Some also write local cache/artifact files. The CLI therefore cannot be treated as a ready-made stable observation API.
- The Bilibili toolchain uses SurfCore-managed account credentials. Those credentials must remain inside SurfCore's protected environment and must never be copied into this repository, adapter manifests, CSD events, or logs.

### Existing SurfCore plugin platform registry

- `plugins/surfcore/lib/platforms.js` describes built-in `qq` and `bili` adapters, but its capability vocabulary includes `memory.write` and `actions`; it is not equivalent to this project's narrower `observe:<modality>` contract.
- Its local extension loader imports extension code into the DSH process. It is not an OS sandbox and must not be used as a trust boundary for unreviewed code.

## 3. Integration gaps and security conclusions

1. There is no currently verified, dedicated, read-only, machine-readable SurfCore → CSD event API.
2. Reusing the broad console token would grant more authority than observation requires. The project adapter must not receive it.
3. Reading SurfCore's private state files directly would couple CSD to unstable internal schemas and could expose unrelated private state.
4. Parsing human-oriented CLI output is brittle and does not reliably preserve source time, coverage, modality, and provenance.
5. SurfCore's existing ability to perform account mutations does not authorize this individual to perform them. All external mutations remain blocked until an ASM action contract exists.
6. The existing WorkerHost is only an orchestration/protocol interface with fake executors in tests. There is no production subprocess launcher or OS sandbox. Do not run third-party SurfCore/plugin code as an untrusted worker under the current implementation.

## 4. Proposed narrow integration boundary

Add a dedicated, versioned, read-only observation interface on the SurfCore side. Prefer explicit endpoints or a dedicated IPC channel over private state-file scraping.

### QQ observation feed

The feed should expose bounded, cursor-based records for incoming private/group messages and relevant notices. Each record should contain only the minimum required fields:

- stable event/message reference and monotonic cursor;
- conversation kind and opaque conversation reference;
- opaque account reference and sender reference;
- source timestamp and local receipt timestamp;
- normalized text plus typed, bounded media placeholders/references;
- event kind and an explicit indication of whether the record is historical/backfilled;
- schema version and truncation/coverage metadata.

The feed must be read-only: polling must not mark messages read, acknowledge them, trigger a wake, send a reply, or change SurfCore session state. Cursor replay is acceptable because CSD event identity and ingestion are idempotent. The feed must not expose agent tokens, console tokens, cookies, local file paths, or raw credentials.


### QQ cursor and replay contract

The adapter's DTO batch envelope is versioned and bounded. Each QQ record has a non-negative integer cursor; records in one page must be strictly increasing, unique by record ID, greater than the caller's last durable cursor, and no greater than the page's proposed next cursor. A page may contain zero records while advancing over feed entries filtered out by SurfCore.

Observation identity is derived from platform + opaque account reference + source record ID. This prevents the same source-local message ID from colliding across separate account contexts. Reusing the same identity with changed content deliberately produces the same CSD event ID but a different immutable payload, allowing CSD's idempotency-conflict check to reject silent source mutation.

The mapper returns CSD events and a **proposed** next cursor but never persists a checkpoint. The integration host must submit every event durably to CSD before saving that cursor. If the process stops before saving it, it requests the same page again; deterministic event identity and CSD idempotency make replay safe. Do not advance the checkpoint before all event writes complete. This is not an exactly-once transport guarantee; it is at-least-once delivery with idempotent durable ingestion.

### Bilibili observation API

Expose only individually allowlisted read operations initially, using canonical BV targets rather than arbitrary URLs. Return structured records rather than human-formatted stdout:

- video identity/metadata;
- subtitle tracks and timestamped text when available;
- comments/danmaku as separately attributed evidence;
- extraction method, source reference, source time where available, and explicit completeness/coverage notes.

A missing subtitle, inaccessible comment page, sampled frame set, or failed extraction must be represented as partial/unavailable rather than silently described as complete viewing. Do not expose like/favorite/follow/comment/reply/publish/danmaku-send/private-message operations through this interface.

The current fake DTO mapper now enforces the per-record provenance shape: every Bilibili record is attached to its canonical video reference and declares the relevant actor role; a stable actor reference is preserved only when the source supplies one. Subtitle language and comment parent/thread references are typed fields, not text conventions. See the detailed v1 contract for exact allowlists and validation rules.

### Authentication and transport

- Use a dedicated observation-only credential/scope, distinct from `consoleToken` and agent tokens.
- Bind to loopback only; validate Host/origin and request size; deny remote binding.
- The interface must have no generic command execution, path argument, URL fetch proxy, or arbitrary tool dispatch.
- Apply bounded page sizes, response sizes, timeouts, and rate limits.
- Redact credentials and message content from diagnostic logs.
- Treat every returned field as untrusted external evidence. The CSD adapter validates and maps it through the existing Observation v2 contract; it does not accept memories or goals.

## 4.1 Detailed read-only ingress contract

The concrete proposed transport and DTO schema are specified in [SurfCore Read-only Ingress Contract v1](./surfcore-readonly-ingress-contract-v1.md). This is a proposal for a separate SurfCore-side change, not an endpoint that exists today. It explicitly replaces the unsafe shortcuts of reading `state/qq-public-feed.jsonl` or reusing the management `consoleToken`.

## 5. Implementation sequence

1. **SurfCore interface review** — finish endpoint/IPC schema design against the pinned source and confirm the actual installed version before any local activation.
2. **Fake contract adapter** — add deterministic fixtures for QQ message records and Bilibili video/subtitle/comment records; map them into `ObservationEvidence` and CSD v2 events. No network, credentials, local SurfCore files, or external side effects.
3. **SurfCore read-only interface** — implement the narrow feed/API in a separately reviewed SurfCore change or supported extension point. Do not use existing broad console routes as a shortcut.
4. **Host integration** — only after a real, tested process/OS isolation boundary exists, connect the adapter through WorkerHost. Until then, use fake executors only.
5. **Owner-local validation** — only when the user explicitly proceeds to local setup: verify the exact installed SurfCore/DSH version, connection state, read-only feed, cursor replay, and privacy boundaries. Hosted CI is not a substitute.

## 6. Acceptance gates

- QQ private and group messages can be read without changing read/unread state or triggering replies.
- Cursor replay and duplicate delivery produce stable CSD event identities and no duplicate durable observations.
- Bilibili read operations return structured provenance and coverage; write commands are absent from the exposed capability manifest and rejected at the interface.
- No console token, agent token, Bilibili cookie, or local filesystem path crosses into CSD.
- All external evidence remains `untrusted=true`; model interpretation can only submit proposals through CSD.
- Linux and Windows contract tests pass. Production worker execution is not enabled until actual OS restrictions are independently tested.
- No platform action is dispatched by Recovery.

## 7. Explicit non-claims

This assessment is source review at the pinned SurfCore commit, not a live connection test. It does not establish that the user's currently installed SurfCore is still v0.8.8, that QQ/Bilibili accounts are logged in, or that any API endpoint is enabled in the user's local environment. No local files, settings, credentials, plugins, or accounts were changed.
