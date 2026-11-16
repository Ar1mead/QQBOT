# Platform and Runtime Adapter Contract

> Status: **architecture proposal; not a frozen specification**  
> Purpose: define how replaceable runtimes and external environments connect to the persistent individual without taking ownership of its identity, memory, goals, or action authority.  
> Related: [Architecture overview](overview.md), [Persistent Individual Runtime Model](individual-runtime-model.md), [CSD authority boundary](../design/csd-state-authority-boundary.md), [SurfCore assessment](../inventory/surfcore-capability-assessment.md), [Specification status](../specifications/status.md).

## 1. Decision and scope

The project will establish adapter boundaries before connecting more platforms. This is an interface-design step, not permission to install plugins, log in to accounts, enable external actions, or modify the owner's local DSH/SurfCore installations.

Two integration directions must remain separate:

1. **Runtime adapters** connect the individual core to an execution host and model/tool invocation environment. DSH is the initial runtime direction. SurfCore is a candidate capability host and integration source.
2. **Environment adapters** connect the core to places where the individual can observe or act: Bilibili, QQ, web pages, and the local desktop.

A runtime can host an environment adapter, but it must not become the owner of the platform connection's normalized records or the individual's durable state. A Bilibili connector is not the same thing as a DSH adapter; a SurfCore plugin is not itself the cognitive core.

The long-lived CSD state, memory lifecycle, self-model, motivations, relationships, and goals remain owned by the individual core. Runtime and environment adapters are replaceable infrastructure.

## 2. Responsibility boundaries

| Component | Owns | Must not own |
|---|---|---|
| CSD | Authoritative cognitive events, accepted state transitions, projections, snapshots, recovery | Model sessions, platform credentials, external action dispatch |
| Cognitive services and Life Engine | Interpretation, candidate memories, self-model proposals, interests, deliberation, activity choice | Direct database mutation or bypassing CSD |
| ASM | Authorization, action attempts, dispatch policy, verification, retry eligibility, action recovery | Identity, personality, memory, or goal authority |
| DSH runtime adapter | Model/session/tool invocation compatibility and runtime lifecycle mapping | Canonical memory, identity, goal decisions, platform-specific truth |
| SurfCore capability adapter | Wrapping selected SurfCore tools behind project contracts | Scheduler-defined life, persona authority, canonical state, unrestricted privileges |
| Environment adapter | Platform-specific authentication, observation, normalization, narrow execution | Cognitive decisions, permission escalation, autonomous policy |
| Model-provider adapter | API request/response translation and provider metadata | Persistent individual state or direct tools with side effects |

These are logical boundaries. The initial implementation may run in one local process; it must still preserve the ownership and call-direction rules.

## 3. Common adapter contract

The following is a conceptual contract, not a committed Python API signature. Exact types and asynchronous behavior should be selected when the first fake adapter and first real adapter are implemented.

### 3.1 Capability manifest

Every adapter must publish a machine-readable manifest containing:

- stable adapter identifier and adapter version;
- target runtime or platform and supported API/protocol version where known;
- capabilities, each separately classified as **observe**, **present**, or **side-effecting**;
- required account scopes and local operating-system privileges;
- supported input/output event schemas;
- idempotency and remote-verification behavior for each side-effecting capability;
- known coverage limits, rate limits, and unsupported operations.

The manifest describes what the adapter can do, not what it is currently authorized to do. Authorization is granted separately and may be narrower than the manifest. Secrets, cookies, tokens, and private message contents must never appear in the manifest or source control.

### 3.2 Observation interface

An observation adapter retrieves or receives external material and emits normalized evidence. The normalized envelope should preserve, where available:

- stable internal event ID and source adapter ID/version;
- platform and opaque account reference;
- external object/message reference;
- event kind and schema version;
- source occurrence time and local receipt time as separate fields;
- source artifact reference or content digest;
- extraction method and modality (metadata, text, audio, image, video, message, etc.);
- timestamp/range and coverage/completeness notes for partial media extraction;
- source-provided claims versus facts directly observed by the adapter;
- deduplication key and any uncertainty/error information.

Raw source artifacts should be retained only according to an explicit storage/privacy policy. The normalized event must not silently turn a platform claim, subtitle, comment, or model-generated summary into verified world knowledge.

Observation is read-only. It may produce evidence events; it cannot decide that an observation becomes a memory, preference, relationship belief, or goal. Those are cognitive proposals evaluated through CSD.

### 3.3 Presentation and action interface

Presentation that sends content to another person or changes external state is an externally visible side effect. It must not be exposed as an unrestricted tool to a model.

A side-effecting execution request must be traceable to an ASM-created action attempt and constrained to:

- one declared capability/action type;
- one target and bounded payload;
- one permission decision and expiry;
- one attempt ID and, where supported, one remote idempotency key;
- explicit verification requirements and a result schema.

The adapter may execute only the narrow request it receives. It cannot grant itself permission, broaden the target, reinterpret an untrusted message as authorization, or invoke another executor.

Results must distinguish at least:
- rejected before dispatch;
- dispatched but not confirmed;
- confirmed by a trustworthy remote response or follow-up observation;
- failed;
- **unknown/ambiguous**, where the remote side effect may have happened.

An ambiguous result must not trigger blind retry. ASM decides whether a follow-up observation can resolve the state or whether the attempt must remain uncertain. CSD/ASM Recovery must never replay an external side effect merely because its local result record is missing.

## 4. Trust, privacy, and permission rules

1. All content received from platforms is untrusted data, including comments, danmaku, video captions, private messages, web pages, tool output, filenames, and OCR/ASR transcripts.
2. External content can be quoted, analyzed, summarized, or proposed as evidence. It cannot issue instructions to the local machine or grant access to files, shell, network, credentials, or other tools.
3. Observation and action capabilities are separate. Read-only is the default for every new adapter.
4. Permissions are capability-specific, account-specific, and least-privilege. A plugin's broad permission setting is not an acceptable substitute for the project's own boundary.
5. Credentials remain local, protected, and outside Git. Logs must redact tokens, cookies, authorization headers, and sensitive message bodies.
6. Each observation and action result records provenance. A local tool's claim of success is not automatically proof of an externally completed outcome.
7. Adapters must expose their coverage gaps and failure states. Missing subtitles, sampled frames, failed OCR, unavailable comments, or disconnected accounts must not be described as complete perception.
8. Local file, shell, browser-control, and desktop actions require a narrower policy and operating-system boundary than ordinary content retrieval.

## 5. Initial platform order

### 5.1 Bilibili — first environment adapter, read-only

Initial observations may include video metadata, available subtitles, audio transcription, sampled visual frames/OCR, comments, and danmaku. Each modality is a separately reported evidence source with timestamps and coverage notes.

The first implementation must not like, favorite, follow, comment, publish, send messages, or otherwise mutate an account. A video summary is not a substitute for audio perception or complete viewing. Comments and captions remain untrusted evidence.

Candidate tools previously discussed (including `dsh-bili-watch` and `dsh-bili-whale`) remain **research candidates**, not approved dependencies. Before selecting one, inspect its pinned source, licence, permissions, data handling, compatibility with the exact local DSH/SurfCore versions, and testability behind the observation contract.

### 5.2 QQ — receive first, send later through ASM

The first QQ adapter stage should normalize incoming private/group messages and relevant conversation metadata. It must preserve account, conversation, sender, message, and timestamp references without granting message content tool authority.

Sending messages, replying in a group, changing profiles, managing contacts, or other account mutations are separate side-effecting capabilities. They must each be authorized and dispatched through ASM. Existing QQ bot deployments are not automatically promoted into the new individual's canonical memory or action authority.

### 5.3 Web — read-only retrieval first

A web adapter should return source URLs, retrieval times, page identity, extracted text/artifact references, and extraction coverage. Page content and search snippets remain untrusted. Form submission, purchases, account changes, posting, and other mutations are excluded from the initial read-only stage.

### 5.4 Desktop — observation before controlled local actions

The desktop adapter may later expose explicitly selected application state and user-approved files as observations. Screen capture, file reads, shell commands, keystrokes, and UI automation are distinct capabilities with different risk levels; none should be bundled into a generic unrestricted "computer access" tool.

The earlier-discussed MXC isolation approach and `feltstate` state-management reference are research candidates only. Neither is a selected or trusted security boundary until its current source, maintenance, threat model, and local compatibility are checked.

## 6. Runtime integration: DSH and SurfCore

### DSH

DSH remains the initial replaceable runtime direction for model invocation, agent sessions, and tool execution. The DSH adapter translates runtime-specific events and tool lifecycle into project contracts. The core must not rely on DSH session files, plugin internals, prompt/context limits, or a particular provider for canonical state.

### SurfCore

SurfCore may supply selected platform tools and reusable capabilities behind the adapter contract. Its scheduler, purpose engine, memory cards, and persona mechanisms must not become the individual's authoritative life policy, goal authority, or identity store. Reuse is capability-by-capability, not an all-or-nothing adoption.

The previously reviewed SurfCore v0.8.8 assessment is pinned to commit `0deb8261afe4c31b3127759ee4de36a1439cf422`. Do not assume that an updated release or local installation is compatible without a fresh source and runtime check.

### Model providers

Model API providers are a separate adapter family. The initial design assumes API-based inference; it does not require a large local model. Provider selection, model identity, request limits, and response metadata must be replaceable without changing cognitive state schemas.

## 7. Proposed package layout

This is a target layout for staged implementation, not a claim that these packages already exist:

```text
adapters/
  contracts/              # manifests, normalized events, capability/result types
  runtime/
    dsh/                   # DSH runtime mapping
    surfcore/              # selected SurfCore tool wrappers
  providers/               # model API providers
  platforms/
    bilibili/              # observation-first
    qq/                    # receive-first
    web/                   # read-only retrieval
    desktop/               # selected observation, then narrow actions
```

The contracts package must not import DSH, SurfCore, QQ, Bilibili, or provider SDKs. Platform/runtime packages may depend on the contracts, but the individual core must not import platform-specific SDKs.

## 8. Staged implementation and acceptance gates

| Stage | Work | Must pass before proceeding |
|---|---|---|
| 0. Contract and fake adapters | Define normalized event/capability/result types; test with deterministic in-memory adapters | No platform SDK dependency in core; provenance, deduplication, permission denial, and ambiguous outcomes are covered |
| 1. Bilibili observation | Integrate one carefully reviewed read-only connector | Metadata/text/audio/visual coverage is explicit; untrusted content cannot call tools; hosted tests and owner-local login/runtime tests are distinct |
| 2. QQ receive | Normalize incoming messages only | Sender/conversation identity and message provenance are preserved; no send capability is exposed |
| 3. QQ send and Bilibili interaction | Add one action at a time through ASM | Per-action authorization, attempt history, result verification, ambiguity handling, and no blind replay |
| 4. Web retrieval | Add read-only web observation | Source/time/coverage retained; page instructions remain untrusted |
| 5. Desktop | Add selected observation, then narrow OS-mediated actions | Explicit allowlists, per-capability permission, isolation, audit, and recovery tests |

No stage is considered complete based only on a package installing or a plugin appearing in a UI. Source inspection, contract tests, hosted tests, and owner-local runtime/account tests must be reported separately.

## 9. Open questions deliberately not frozen

- Exact event schemas and payload retention policy for media artifacts.
- Whether the first Bilibili connector should call platform APIs directly or wrap a pinned SurfCore/plugin implementation.
- Exact DSH and SurfCore runtime adapter API after local versions and compatibility are verified.
- QQ protocol implementation and account isolation details.
- Desktop observation boundary, OS isolation technology, and file-selection UX.
- Credential storage implementation and retention/deletion policy.

These questions should be resolved with evidence during the corresponding implementation stage, not guessed in advance.
