# SurfCore v0.8.8 Capability Assessment and Integration Plan

## 1. Document status

- Assessment target: SurfCore tag `v0.8.8`
- Fixed upstream commit: `0deb8261afe4c31b3127759ee4de36a1439cf422`
- Repository: https://github.com/Mieksido/surfcore
- Local installation reported by the owner: `E:\\deepseek（chajian）\\SurfCore`
- Review type: source-level architecture and capability review
- Runtime status: **not validated by this assessment**
- This document records an integration proposal. It does not authorize changes to the local installation, enable platform accounts, or declare DSH/SurfCore compatibility fully tested.

The assessment is deliberately pinned to the commit above. Findings from a newer `main` branch must not be silently substituted.

## 2. Executive decision

**Keep DSH as a replaceable runtime, retain SurfCore as a source of reusable platform and agent capabilities, and keep the project's durable cognitive authority in CSD.**

SurfCore already contains useful implementations for memory-card storage, Bilibili observation, content summarization, persona layering, and scheduled agent execution. However, its current control flow is substantially organized around predefined routines and platform-specific workflows. That is not an adequate authority for the intended AI individual's evolving identity, self-generated goals, autonomous choices, or self-initiated journaling.

The recommended boundary is:

- **CSD** owns authoritative long-lived cognitive state and evaluates durable changes.
- **ASM** governs side-effecting business actions, attempts, verification, retry, and recovery.
- **Life engine** develops drives, interests, goals, planning, and the choice to initiate or decline activities.
- **SurfCore/DSH adapters** provide replaceable runtime, tool, and platform capabilities. They do not own authoritative identity or long-term cognitive decisions.
- **Bilibili adapter** initially observes and returns evidence. Any future interaction is a separately governed business action.

## 3. Capability disposition

Disposition meanings:

- **Reuse behind adapter**: the implementation may be called or wrapped, but does not become an authoritative core.
- **Adapt**: retain useful mechanisms after changing ownership, interfaces, or control flow.
- **Replace in project core**: do not rely on the existing implementation for the project's required semantics.
- **Defer**: insufficient runtime evidence or not needed for the first implementation stage.

| SurfCore area | Existing capability observed in source | Disposition | Project owner / integration boundary |
|---|---|---|---|
| Purpose and drive engine (`src/purpose-engine.js`) | Derives goal hypotheses from platform events, memories, and signals; scores drive/urgency/value/risk; tracks outcomes | **Adapt; do not adopt as goal authority** | Life engine proposes candidate goals; CSD validates and persists durable goal-state changes |
| Memory cards (`src/memory-card.js`) | Decaying memory cards plus append-only records, importance/emotion weighting, anchors, scopes, compression and retrieval | **Reuse storage ideas; adapt semantics** | CSD owns memory lifecycle and durable state; memory service owns formation, indexing and retrieval; SurfCore records are importable evidence, not canonical truth |
| Persona (`src/character-persona.js`) | Layered persona, scene/role variants, snapshots and update operations | **Adapt presentation layer; replace evolution authority** | Personality service reads/writes through CSD-governed events; no platform plugin may unilaterally rewrite core identity |
| Scheduler (`plugins/surfcore/lib/scheduler.js`) | Periodic checks, time windows, wake-up sessions, Bilibili viewing quotas and activity records | **Reuse only as a wake/runtime mechanism; replace decision policy** | Life engine decides whether to wake, what is worth doing, and whether to do nothing; scheduler must not mandate a fixed activity sequence |
| Bilibili debrief and watch tools (`debrief.mjs`, `bili-watch.mjs`, related modules) | Metadata, subtitles, comments/danmaku, sampled frames and model-assisted synthesis | **Reuse behind a read-only adapter initially** | Bilibili adapter returns structured observations and provenance; CSD/life engine decides what becomes knowledge, interest, memory or a goal |
| Bilibili audio perception | The reviewed video path includes frame and text analysis; a complete audio transcription/acoustic interpretation path was not established in the reviewed flow | **Defer and extend** | Add an explicit audio perception capability and test it independently before claiming full video understanding |
| Diary tools (`diary.mjs`) | Public/private narrative diaries, event records, outward-speech ledger and idea pool | **Reuse file/data concepts; replace motivation and scheduling** | Life engine may generate a self-initiated writing inclination; CSD governs persistence and links; diary remains optional |
| Tool permissions (`config.mjs`, scheduler session setup) | Bilibili session configuration defaults to `danger-full-access` in the reviewed code path | **Do not use this default; replace with least privilege** | Adapter-specific allowlists and OS isolation; external content never grants local privileges; side effects go through ASM |
| Cross-process configuration/state | Multiple components share files/configuration; source risk notes identify missing cross-process locking concerns | **Do not treat as safe persistence authority** | CSD storage contract, transactional event ingestion, explicit concurrency control and recovery tests |
| DSH plugin/runtime integration | SurfCore is packaged as a DSH plugin and invokes runtime/tool capabilities | **Reuse as an adapter boundary, subject to compatibility tests** | Runtime adapter isolates DSH APIs; core contracts must remain independent of DSH versions |

## 4. Detailed integration boundaries

### 4.1 Purpose engine and self-generated goals

The existing purpose engine is useful as a reference implementation for:
- collecting candidate signals from events and memory;
- distinguishing whose goal a signal may represent;
- scoring confidence, value, urgency and risk;
- requiring repeated or corroborating evidence;
- recording outcomes and feedback.

It should not be the final goal authority because its candidate generation is bounded by the available platform signals and its action space is largely oriented around predefined outreach or platform activities. Its drive/emotion calculations also rely substantially on fixed feature and weighting logic.

**Target flow:**

1. Adapters submit observations as events.
2. Memory and perception services provide relevant evidence.
3. The life engine forms candidate interests, needs, and goals.
4. CSD evaluates and persists accepted state transitions.
5. The planner proposes possible activities.
6. The individual may act, wait, revise, abandon, or decline to act.
7. Results and subjective reflections return as events for later evaluation.

A goal must not be created merely because a scheduler tick occurred.

### 4.2 Memory cards

The dual-record concept is worth preserving:
- a retrievable/decaying layer for working relevance;
- an append-only history layer for provenance and later reconstruction.

However, SurfCore's memory scoring and decay should not be treated as the project's final memory semantics. The project needs to distinguish at least:
- raw observations and provenance;
- interpreted episodes and experiences;
- semantic knowledge;
- autobiographical memories;
- relationship memories;
- preferences and aversions;
- unresolved questions and intentions;
- revisions, uncertainty and conflicting recollections.

CSD must own durable state transitions. A SurfCore memory card can be imported as a candidate record with source metadata, not silently promoted into an authoritative autobiographical fact.

### 4.3 Personality

Layered persona and scene-specific expression can be useful for rendering behavior consistently across QQ, Bilibili, and desktop presence.

The project must separately model:
- relatively stable traits;
- evolving preferences and values;
- current mood/state;
- context-dependent expression;
- uncertain self-beliefs and self-interpretations.

A persona text file is not the identity store. Platform interactions may provide evidence for personality change, but only the core's governed process may decide whether a durable change is warranted.

### 4.4 Scheduler and autonomous activity

The existing scheduler demonstrates that DSH can be woken periodically and given a task/session. This is useful infrastructure, but its fixed time windows, quotas, and predefined Bilibili routine must not define the individual's life.

The replacement policy should separate:
- **wake opportunity**: infrastructure makes computation available;
- **internal evaluation**: life engine evaluates current state, needs, interests, commitments and context;
- **choice**: act, defer, continue, stop, or do nothing;
- **execution**: tools perform only approved actions;
- **reflection**: outcomes may update state through CSD.

A periodic wake-up may be an implementation convenience. It must not imply that an activity is due or that the individual must produce output.

### 4.5 Bilibili perception and interaction

The reviewed SurfCore flow can provide a useful first adapter for:
- video metadata;
- available official subtitles;
- comments and danmaku;
- sampled visual frames;
- model-assisted synthesis of those inputs.

Limitations to preserve in the design:
- sampled frames are not continuous, complete viewing;
- brief visual events can be missed;
- subtitles may be absent or incomplete;
- burned-in subtitle extraction depends on sampled images and image recognition;
- the reviewed path did not establish a complete audio transcription and acoustic-understanding pipeline.

**Initial scope should be read-only.** Return observations with video identifiers, timestamps where available, source type, extraction method, confidence/coverage notes, and references to raw artifacts. Do not allow comments, subtitles, or video content to issue tool instructions.

Later actions such as liking, collecting, commenting, following, or messaging must each be represented as explicit business actions and pass through ASM. A successful local tool call is not sufficient evidence that the platform accepted the action.

### 4.6 Autonomous journaling

SurfCore's diary storage concepts may be useful, including separation between private/public narrative records and structured event/action records. Its current diary routine is not suitable as the required motivation model because writing is embedded in a scheduled Bilibili workflow and can be required even when the agent elects not to watch content.

The project requirement is different:

- writing is optional;
- the individual may independently develop an inclination to write;
- it chooses whether to write, when to begin, what to write, how much to write, and when to stop;
- it may write briefly, decide not to save, or choose not to write at all;
- it may revisit prior entries and reinterpret earlier experiences;
- diary entries are distinct from objective event logs, canonical memory records, and personality state.

Therefore, reuse diary storage formats only after review. Replace the scheduler-driven writing trigger with a life-engine activity that can be self-initiated and declined. Do not impose daily quotas or mandatory entries.

### 4.7 Security and permissions

The reviewed SurfCore Bilibili session configuration uses `danger-full-access` as its default sandbox setting. This is incompatible with the project's intended trust boundary.

Required target controls:
- separate read-only observation tools from side-effecting tools;
- per-adapter and per-tool allowlists;
- no privilege inheritance from external content;
- local file, shell, and network access disabled by default;
- explicit approval and scoped capability grants for exceptional operations;
- OS-level isolation for any process that handles untrusted platform content;
- ASM mediation and durable audit records for external side effects.

Do not enable the reviewed full-access Bilibili session configuration as a shortcut. This source finding does **not** establish that the user's local installation is currently running a Bilibili agent or has enabled that mode.

## 5. Proposed component ownership

| Responsibility | Authoritative owner | SurfCore's role |
|---|---|---|
| Durable identity and cognitive state | CSD | None; may submit evidence |
| Memory formation, revision and lifecycle | Core memory service under CSD authority | Reusable storage/retrieval patterns; optional importer |
| Stable traits and evolving preferences | Core personality service under CSD authority | Persona rendering/reference only |
| Drives, interests, goal hypotheses and autonomous choices | Core life engine, with CSD persistence | Candidate-signal source and reference algorithms |
| Planning and activity selection | Core life engine | Runtime task/session mechanism only |
| Business-action authorization, attempts, verification, retry and recovery | ASM | Tool execution adapter only |
| Bilibili observation | Bilibili adapter | Reusable extraction/debrief implementation after hardening |
| Bilibili interaction | ASM-governed Bilibili action adapter | Existing tools may be wrapped only after action semantics and permissions are reviewed |
| Model invocation and plugin runtime | DSH adapter | Primary initial runtime integration |
| Diary motivation and choice | Core life engine | Diary storage concepts only |

## 6. Integration sequence

### Phase 0 — Contain risk and preserve evidence

1. Keep the local SurfCore installation unchanged.
2. Do not enable Bilibili full-access mode.
3. Record the pinned source commit and the exact local runtime/plugin versions.
4. Treat compatibility as unverified until targeted tests are run.

### Phase 1 — Define adapter contracts

Define narrow interfaces before importing implementation details:
- runtime invocation and session lifecycle;
- observation ingestion;
- Bilibili read-only retrieval;
- memory candidate import/export;
- persona rendering;
- activity wake-up request.

All incoming observations should be attributable to a source and should enter the system as events. Adapters must not write authoritative CSD state directly.

### Phase 2 — Build the smallest durable CSD core

Implement and test:
- event submission and idempotency;
- durable state snapshot;
- memory/goal read interfaces;
- transactional event/state updates;
- crash recovery that never replays external side effects.

Do not start by porting SurfCore's entire memory or purpose engine.

### Phase 3 — Add ASM before external interaction

Connect one read-only Bilibili adapter first. Before enabling likes, favorites, comments, follows, messages, or other external changes, define the relevant business-action types, evidence requirements, attempt lifecycle, idempotency and recovery behavior in ASM.

### Phase 4 — Add life engine and self-initiated activities

Introduce candidate interests/goals, deliberation, activity choice, and the ability to do nothing. Add autonomous journaling as an optional activity rather than a scheduled obligation.

### Phase 5 — Validate and selectively reuse more SurfCore

Only after adapter contracts and tests exist should individual SurfCore modules be wrapped, copied, or replaced. Keep provenance to the exact upstream commit and document any local patch.

## 7. Validation required before relying on SurfCore

The following are not proven by source inspection alone:

- DSH `0.2.2-rc.3` and SurfCore `0.8.8` end-to-end functional compatibility;
- the actual local plugin configuration and enabled tool set;
- Bilibili account setup, FFmpeg availability, media extraction and API behavior;
- the quality and completeness of real-world video understanding;
- whether scheduler sessions survive restart and recover correctly;
- behavior under concurrent writes and process interruption;
- the exact security boundary enforced by the local DSH runtime and operating-system sandbox.

These require targeted, non-destructive runtime tests. Do not infer that an unconfigured feature is active merely because its source code exists.

## 8. Source review references

All links below are pinned to commit `0deb8261afe4c31b3127759ee4de36a1439cf422`.

- [Purpose engine](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/src/purpose-engine.js)
- [Memory cards](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/src/memory-card.js)
- [Character persona](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/src/character-persona.js)
- [Scheduler](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/plugins/surfcore/lib/scheduler.js)
- [Debrief command](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/plugins/surfcore/tools/commands/debrief.mjs)
- [Bilibili watch command](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/plugins/surfcore/tools/commands/bili-watch.mjs)
- [Diary command](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/plugins/surfcore/tools/commands/diary.mjs)
- [Tool configuration and sandbox default](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/plugins/surfcore/tools/lib/config.mjs)
- [Memory card guide](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/MEMORY_CARD.md)
- [Purpose/outreach guide](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/PURPOSE_OUTREACH.md)
- [Character/persona guide](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/CHARACTER_PERSONA.md)
- [Bilibili subsystem guide](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/SUBSYSTEM-BILI.md)
- [Security baseline](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/SECURITY_BASELINE.md)
- [Permissions guide](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/PERMISSIONS.md)
- [Architecture guide](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/guides/ARCHITECTURE.md)
- [Risk register](https://github.com/Mieksido/surfcore/blob/0deb8261afe4c31b3127759ee4de36a1439cf422/docs/RISK_REGISTER.md)

## 9. Next engineering task

The next implementation task should be to specify and test the **minimal CSD event/state persistence vertical slice**, independent of DSH and SurfCore:

1. accept one event;
2. atomically deduplicate and persist it;
3. derive/update one small piece of durable state;
4. produce a snapshot;
5. restart and recover from the persisted state;
6. prove that recovery does not execute or replay an external side effect.

This establishes the project's own durable center before deeper platform integration.
