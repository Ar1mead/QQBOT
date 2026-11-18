# Adapter Worker Isolation — Design Draft

> Status: design draft; no worker process or OS sandbox is implemented.
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

## 7. Current status

Implemented:
- platform-neutral observation contracts;
- CSD observation v2 mapping and validation;
- explicit in-process adapter registry and capability gate;
- tests for registration, dispatch scope, and returned evidence identity.

Not implemented:
- worker process protocol;
- Windows/Linux sandbox launchers;
- filesystem/network/resource enforcement;
- real Bilibili network access or account integration.

Until these requirements are implemented and verified, the registry must only host trusted project-owned code. This document is a design draft, not a claim that process isolation already exists.
