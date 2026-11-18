# Adapter Worker Isolation — Design Draft

> Status: design draft; low-level Windows AppContainer process/Python-runtime harness and protocol v2 bounded DTO input path are implemented, but no production WorkerExecutor or Linux sandbox backend exists.
>
> Scope: define the security requirements for eventually running third-party or otherwise untrusted environment-adapter code without loading it into the authoritative individual-core process.

## 1. Why this boundary is needed

The current `ObservationAdapterRegistry` is an application-level allowlist. It constrains the project's normal dispatch path, but Python code executing in the same process can import sockets, access files, inspect process state, or bypass the registry.

Therefore:
- Only project-owned or otherwise trusted adapter code may currently be loaded in-process.
- Third-party plugins must not be imported into the core process merely because their manifest declares observation-only capabilities.
- A manifest is a declaration, not a security sandbox and not proof of actual behavior.

## 2. Threat model

Treat the worker implementation as potentially buggy or compromised. It may attempt to:
- access credentials, browser profiles, environment variables, or unrelated local files;
- open arbitrary network connections or contact loopback/private-network services;
- spawn child processes or consume excessive CPU, memory, disk, or time;
- return malformed, oversized, misleading, or identity-spoofed observations;
- write to shared storage or mutate state outside the requested operation.

The worker is not trusted to decide what it is allowed to do. The host owns adapter registration, request validation, time/resource limits, result validation, and CSD persistence.

## 3. Required host/worker boundary

The host should communicate through a versioned, structured request/response protocol. Do not pass shell command strings, arbitrary URLs, filesystem paths, or executable snippets supplied by platform content.

A request should contain only:
- protocol version;
- registered adapter ID and pinned adapter version;
- one request ID;
- an allowlisted operation name;
- typed, bounded arguments such as a canonical BV identifier;
- explicitly approved modality names.

A response should contain only:
- request ID and adapter identity;
- a bounded status value;
- normalized observation evidence;
- explicit coverage, warnings, and error codes.

The host must reject mismatched request IDs, adapter identities, unsupported protocol versions, undeclared modalities, oversized payloads, malformed evidence, and any attempt to return a non-observation action.

## 4. OS isolation requirements

A production worker must be launched with host-controlled restrictions, not with permissions chosen by the plugin.

Minimum requirements:
- separate process; no import into the core process;
- no inherited secrets, browser profiles, cookies, API keys, or unrelated environment variables;
- no access to the CSD database or project source tree;
- a dedicated temporary working directory with bounded storage and cleanup;
- outbound network denied by default; if a future adapter needs network access, use a separately reviewed egress policy with destination and protocol allowlists;
- no access to loopback, link-local, private-network, or cloud metadata endpoints unless an explicit reviewed exception exists;
- bounded wall-clock time, CPU, memory, process count, output size, and log size;
- no shell interpolation; executable and arguments are selected by the trusted host;
- terminate the worker on timeout or protocol violation and treat its result as failed/unknown, never as verified truth.

Windows and Linux require different enforcement mechanisms. The project must verify the actual OS controls in integration tests; a Python subprocess by itself is not isolation. Container use also does not automatically guarantee network or filesystem restrictions unless configured and tested.

## 5. Evidence and persistence rules

- Worker output is untrusted, including its claimed timestamps, source references, captions, OCR, ASR, and summaries.
- The host validates content digests and provenance fields, then maps accepted observation envelopes into CSD v2.
- The worker never receives a CSD write handle and cannot submit memory, motivation, goal, or decision events.
- CSD remains the authoritative event store. Observation ingestion is not memory acceptance.
- A worker crash or timeout must not cause the host to invent a complete result. Partial evidence is accepted only when the response itself passes validation and reports partial coverage.

## 6. Acceptance gates before using third-party code

1. Threat-model review for the specific adapter and its dependencies.
2. Protocol schema and strict size/type validation tests.
3. Worker-launch tests proving secrets and CSD files are not visible to the worker.
4. Filesystem tests proving access is limited to its dedicated working directory.
5. Network tests proving outbound, loopback, private, link-local, and metadata access are denied by default.
6. Resource-limit and timeout tests on both Windows and Linux.
7. Malformed/oversized response and worker-crash tests.
8. Recovery tests confirming worker failures never replay external side effects or create accepted memories.
9. Separate owner-local verification of the actual runtime and OS policy before enabling a real platform connector.

## 6.1 Initial transport protocol slice

Implemented in `adapters/worker_protocol.py`:

- protocol version 2 with distinct observation-request and observation-response message types;
- exact envelope field allowlists (unknown fields are rejected);
- request-side host-fetched DTO bytes carried as canonical base64 plus SHA-256, capped at 512 KiB;
- duplicate JSON key rejection and strict UTF-8 decoding;
- a 1 MiB encoded-message ceiling, bounded identifiers/target references, and bounded modality/evidence/warning counts;
- request/response binding checks for request ID and pinned adapter ID/version;
- response status shape checks for complete, partial, unavailable, and failed outcomes.

This is a transport and evidence-reconstruction implementation. It does not launch a worker, establish a secure channel, authenticate a worker process, or impose OS permissions. The host can reconstruct each evidence object through the existing observation dataclasses, which enforce provenance-field shape, timezone-aware timestamps, SHA-256 content digest, coverage consistency, and the untrusted invariant. Do not treat a valid JSON envelope as trustworthy evidence; it must pass this semantic reconstruction and request-binding step before CSD mapping.

## 6.2 Fail-closed host orchestration

Implemented in `adapters/worker_host.py`:

- `WorkerHost` builds a typed request, invokes an explicitly injected host-owned `WorkerExecutor`, bounds the timeout and response size, decodes the response, and reconstructs validated observation evidence.
- `WorkerBackedObservationAdapter` bridges that host to the existing `ObservationAdapter` interface and checks returned platform and target against the registered manifest/request.
- Missing executor configuration is rejected. There is no fallback that imports or executes adapter code inside the core process.
- Backend timeout, execution error, malformed response, oversized response, and identity/target mismatches fail closed. A production backend must terminate the worker on timeout and cap output while streaming it; the host's post-return size check cannot undo memory already allocated by a backend that buffered an oversized response.

Important: `WorkerExecutor` is an interface, not an OS sandbox. The current WorkerHost tests still use an in-memory fake executor. Protocol v2 transports the bounded host-fetched DTO bytes but does not itself provide a trusted source ingress client. Separate low-level Windows modules now launch an AppContainer process, apply file/network/process/resource restrictions, and pass hosted adversarial tests, including a copied CPython runtime. They are not yet composed into a production WorkerExecutor. No Linux isolation backend exists. A production executor must be host-owned and separately reviewed. Do not inject third-party executor code.

## 7. Current status

Implemented:
- platform-neutral observation contracts and CSD observation v2 mapping/validation;
- explicit in-process adapter registry and capability gate;
- versioned Worker protocol and fail-closed WorkerHost orchestration;
- low-level Windows AppContainer process launch, ephemeral profile lifecycle, zero-capability STARTUPINFOEX, handle-based runtime/temp ACLs, Job Object controls, explicit environment, anonymous pipes, and bounded stdio/timeout handling;
- hosted Windows adversarial tests for copied cmd.exe and copied CPython 3.12, filesystem boundaries, loopback/private-interface denial, host-positive link-local metadata/public TCP denial, child-process restriction, timeout, output overflow, and kill-on-close;
- Run #643 passed on Ubuntu and Windows, 38 steps per matrix job.

Not implemented:
- production WindowsAppContainerWorkerExecutor composition;
- host-side SurfCore ingress client that supplies DTO bytes through the new bounded protocol path;
- Linux Bubblewrap backend and parity tests;
- local Windows/DSH verification;
- real Bilibili/QQ account integration or live SurfCore connection.

Until the production executor, DTO input contract, Linux parity, and owner-local Windows verification are complete, the registry must only host trusted project-owned code. This document is a design draft, not a claim that production process isolation is ready.
