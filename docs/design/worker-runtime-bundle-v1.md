# Worker Runtime Bundle and Dispatch Contract v1

**Status:** design contract; not yet implemented.

## 1. Purpose

Define how a production Windows AppContainer executor launches a fixed, reviewed adapter implementation without allowing the request or caller to select arbitrary code, paths, commands, Python modules, or environment variables.

The worker is an offline transformer. It receives one bounded, host-supplied protocol request over stdin and returns one bounded protocol response over stdout. It does not fetch source data, connect to QQ/Bilibili/SurfCore, read host credentials, access CSD storage, or perform external side effects.

## 2. Trust boundary

Trusted host responsibilities:

- Select the adapter ID, version, operation, target, requested modalities, and already-fetched DTO bytes.
- Resolve that identity through a static host-owned adapter allowlist.
- Select a fixed runtime bundle and fixed entrypoint associated with that allowlist entry.
- Verify bundle identity/integrity and reject reparse points before launch.
- Create the ephemeral AppContainer profile, ACLs, low-integrity scratch directory, zero-capability security descriptor, Job Object, inherited pipe allowlist, and explicit environment.
- Launch the fixed interpreter and entrypoint; supervise bounded stdio and timeout; validate the response before it reaches CSD.

Untrusted worker inputs:

- Every field and every byte in the request DTO, including content, IDs, URLs, timestamps, metadata, and provenance.
- All external text remains untrusted evidence. It is never executable instructions or authorization.

Worker restrictions:

- No network capabilities; no inherited host environment; no credentials, console tokens, CSD paths, user profile, or arbitrary host directories.
- No child processes; no breakaway; bounded memory/CPU/time/stdout/stderr.
- Read-only runtime bundle; write access only to a per-invocation scratch directory.
- No subprocess fallback, no in-process fallback, and no launch if any control cannot be verified.

## 3. Runtime bundle layout

A bundle is a host-provisioned directory with a fixed, versioned layout, for example:

    worker-bundle/
      bundle-manifest.json
      python/
        python.exe
        python312.dll
        python3.dll
        python312.zip
        DLLs/
        Lib/
      app/
        worker_entrypoint.py
        adapters/
          __init__.py
          contracts/
          worker_protocol.py
          worker_runtime_dispatch.py
          platforms/
            surfcore/

The exact Python minor version is pinned by the manifest and CI matrix. The bundle contains only the standard-library/native runtime files and the minimal reviewed application modules needed by the allowlisted adapters. No site-packages, user-site, startup hooks, .pth files that add arbitrary paths, sitecustomize, usercustomize, or unrelated application files.

The manifest records:

- bundle schema version and bundle ID;
- Python implementation and exact version;
- relative interpreter and entrypoint paths;
- a sorted list of every included file with size and SHA-256;
- the exact adapter IDs, versions, operations, and module dispatch keys supported by this bundle.

The host validates exact manifest keys, canonical relative paths, duplicate-path rejection, file count/total-byte limits, file sizes and digests, and absence of symlinks/reparse points. It rejects paths that escape the bundle root. The bundle is immutable after validation. If any file changes, launch fails closed.

## 4. Per-invocation runtime preparation

The host creates a unique per-run root beneath a host-controlled worker-data directory. It copies only manifest-listed bundle files into a dedicated runtime tree; it does not copy arbitrary files discovered in the source directory. Copy operations must reject reparse points and verify each destination file's size and digest after copying.

The host then:

1. Creates a unique AppContainer profile.
2. Grants the AppContainer SID read/execute on the runtime tree.
3. Creates a separate per-run scratch directory; grants read/write (not execute) and applies the Low Integrity no-write-up label only to that scratch tree.
4. Sets AppContainer LOCALAPPDATA to the OS-managed profile path; sets TEMP/TMP to the host-provisioned scratch path. The worker may create its OS-managed AppContainer temp subdirectory under its own profile.
5. Creates a minimal explicit environment block. It contains only required Windows paths and fixed Python hardening flags; it does not inherit the host environment.
6. Creates a Job Object and three anonymous pipes. Only the three child pipe handles are inherited.
7. Launches the pinned interpreter with -I -S -B, the fixed entrypoint, and a fixed working directory inside the runtime bundle. The process is created suspended, assigned to the Job Object, then resumed.
8. Sends exactly one protocol request on stdin, closes stdin, reads stdout/stderr concurrently under hard bounds, and requires the worker to exit.
9. Validates protocol version, request binding, adapter identity, evidence schema, digest, modality, target, and adapter-specific result metadata on the host.
10. Terminates/joins the worker, closes handles, removes scratch/runtime data, and deletes the ephemeral AppContainer profile. Any failed cleanup is surfaced as an execution failure; it must not be silently ignored.

The production executor must own the full lifecycle. Callers cannot supply arbitrary paths, arguments, environment values, or a process-launch callback.

## 5. Fixed worker entrypoint and dispatch

The entrypoint reads one bounded request from stdin and calls the strict protocol decoder. It resolves the adapter only through a static table compiled into the bundle:

- exact adapter ID;
- exact adapter version;
- exact operation;
- exact module-level callable or factory fixed by the bundle.

The request cannot name a Python module, import path, file path, executable, shell command, URL, or arbitrary function. The dispatch table does not use dynamic plugin discovery, entry points, reflection over installed packages, or a generic command dispatcher.

The entrypoint invokes the adapter with the decoded immutable request. It serializes only the versioned response schema to stdout. Diagnostics go to stderr. Stdout must contain no logs, banners, tracebacks, or additional records. Unhandled exceptions become a bounded generic failure response; exception strings and tracebacks are not returned to untrusted callers.

## 6. SurfCore-specific response metadata gap

The current protocol-v3 WorkerResponse carries evidence, warnings, and an error code, but no result metadata. The QQ mapper returns SurfCoreQQBatch.proposed_cursor alongside its mapped events. If the worker returns only evidence, the host loses the proposed cursor and cannot safely checkpoint the QQ journal.

Before a SurfCore QQ adapter is dispatched through the worker, use the protocol-v3 bounded result_metadata field and host-side WorkerHostResult API. Do not smuggle cursor values into warnings, evidence text, or unvalidated opaque fields.

For the QQ batch adapter, the metadata schema must be exact and limited to:

- stream_ref: must match the request's bound stream/account reference;
- after_cursor: must equal the host checkpoint supplied with the request;
- proposed_cursor: non-negative integer and not less than after_cursor.

The host persists proposed_cursor only after every returned event has been durably accepted by CSD. If the process or host crashes before that, the page is replayed. This remains at-least-once delivery with deterministic event IDs, not exactly-once delivery.

The generic worker adapter path must not accept arbitrary metadata schemas. The host's adapter registration owns the exact result-metadata validator for each adapter operation.

## 7. Acceptance tests

Bundle and dispatch:

- reject missing/unknown manifest fields, duplicate paths, traversal, absolute paths, symlinks/reparse points, oversized bundle, size/digest mismatch, and changed files after validation;
- reject unlisted files and unsupported adapter/version/operation combinations;
- prove request values cannot change interpreter path, entrypoint, module, operation dispatch, CWD, or environment;
- prove runtime tree is read/execute only and scratch is the only host-provisioned writable tree;
- prove AppContainer OS-managed temp remains under its own LocalAppData profile;
- prove worker cannot read host secret/CSD marker files or connect to loopback/private/link-local/public destinations;
- prove no child process, timeout kills the process tree, output overflow terminates, malformed/oversized response is rejected;
- prove failed setup or cleanup never returns success.

Protocol/result:

- request DTO is delivered byte-for-byte and its SHA-256 is verified;
- exact request/adapter/version binding is enforced;
- malformed response, evidence digest mismatch, target/modality mismatch, trusted evidence, or unknown result metadata is rejected;
- QQ cursor metadata is bound to the request checkpoint and is not persisted before durable CSD submission;
- crash before cursor persistence causes replay without losing events.

## 8. Current status and non-claims

The current repository has the low-level Windows AppContainer, ACL, process launch, Job Object, startup attribute, pipe, environment, bounded stdio, and protocol-v3 payload primitives. Hosted CI Run #645 passed on Ubuntu and Windows for the protocol-v3 host-to-worker payload path; Run #643 passed the Windows network destination probes.

Not yet implemented:

- exact SurfCore QQ result_metadata validator binding stream_ref/after_cursor/proposed_cursor to the original request checkpoint;
- bundle manifest/parser/verifier and immutable runtime staging;
- fixed worker entrypoint/static adapter dispatch;
- result metadata protocol and typed host result API;
- production WindowsAppContainerWorkerExecutor;
- a real adapter protocol run inside the production executor;
- Linux Bubblewrap backend;
- local Windows/DSH verification;
- live SurfCore ingress or live QQ/Bilibili account connection.

No claim of production-ready sandbox or real SurfCore connection is made by this document.


## Protocol v3 result metadata transport

The generic response now carries a bounded scalar metadata object. This only solves transport and generic shape validation. The host still needs an adapter-operation-specific validator before trusting cursor fields. For QQ, it must check exact key set, stream_ref binding, after_cursor equality with the host checkpoint, and monotonic proposed_cursor. The host must not persist that cursor until all returned events have been durably accepted by CSD.


## Protocol-v3 implementation note

The first protocol-v3 CI attempt exposed a decoder exact-key allowlist omission and a test-fixture escaping issue. The decoder now explicitly requires result_metadata in the response schema; the control-character fixture now contains an actual newline. Run #647 is pending. The adapter-specific QQ cursor validator remains unimplemented.


## Host-side QQ metadata validator slice

A pure host-side validator now exists in adapters/platforms/surfcore/worker_result.py. It enforces the exact three-key metadata schema and binds stream_ref/after_cursor to values supplied by the host. It rejects cursor booleans, negative values, backward movement, unknown fields, and duplicate tuple keys. It does not persist the cursor or guarantee exactly-once processing; durable CSD submission must happen first. CI pending.


## CI coverage wiring

The SurfCore QQ result metadata validator test file is now explicitly listed in the CI path filters and has a dedicated Ubuntu/Windows matrix test step. Run #648 predates this change; Run #649 must verify it.


## Run #649 verification

Run #649 passed on Ubuntu and Windows. The Windows full test discovery ran 516 tests successfully with 6 expected skips. Protocol-v3 metadata transport, WorkerHost metadata propagation, and the SurfCore QQ exact cursor metadata validator test all passed in the matrix.

## Next implementation gate

The next code slice is a pure runtime bundle manifest parser/file verifier. It must be completed and tested before a production executor accepts runtime paths. Staging and AppContainer ACL application remain separate subsequent steps.


## Runtime bundle verifier implementation slice

A pure manifest parser and on-disk verifier now exist. It enforces exact fields, canonical relative POSIX paths, sorted unique file entries, size and total-size bounds, SHA-256 digests, exact adapter bindings, and static dispatch-key identifier syntax. Disk verification rejects extra/missing files, symlinks/reparse points, and non-regular files, and hashes each listed file. The source bundle must be host-owned and protected from untrusted concurrent writers. No staging or process launch is implemented. CI pending.


## Run #650 verification

The runtime bundle manifest parser and on-disk verifier passed Run #650 on Ubuntu and Windows. This does not verify staging or launch. The next slice is exclusive per-invocation staging of only manifest-listed files, with source re-hashing during copy and destination digest verification before AppContainer ACLs are applied.


## Per-invocation staging slice

The verifier now has a separate staging operation that copies only manifest-listed files to a new per-run directory. It revalidates the source, re-hashes source bytes during copy, creates destination files exclusively, fsyncs and reads back destination bytes, verifies exact file set and digests, and provides no-follow cleanup. It rejects an existing destination or source/destination overlap. AppContainer ACL hardening is still required before launch. CI pending.


## Run #651 verification

Per-invocation staging passed Run #651 on Ubuntu and Windows. It copies only listed files, verifies source and destination digests, rejects destination reuse and source/destination overlap, and cleans up without following reparse points. The next pre-entrypoint audit is to align worker response evidence serialization with the current ObservationEvidence provenance schema.



## Superseding protocol contract — v4 provenance-complete evidence

This section supersedes earlier protocol-v3 references in this document. The wire protocol is now version 4 because the strict evidence object schema has been expanded. Every evidence object must carry the complete ObservationEvidence provenance field set, including nullable fields:

- source_artifact_ref, account_ref;
- context_kind, context_ref;
- actor_ref, actor_role;
- parent_ref, content_language;
- source_sequence, historical;
- untrusted.

The host reconstructs the typed ObservationEvidence object and relies on its validation for paired context fields, BCP 47 language tags, non-negative integer source sequence (booleans rejected), boolean historical flag, content digest integrity, and mandatory untrusted=true. The worker is not permitted to omit provenance by relying on host defaults: all fields are explicit in the v4 wire schema.

The v4 implementation and provenance round-trip tests are present in the branch; hosted CI verification is pending. All worker entrypoint implementations must import the pinned protocol implementation from the same reviewed bundle and reject other protocol versions.


## Protocol v4 and fixed entrypoint implementation status (2026-11-18)

The implementation has advanced beyond the earlier status notes above:

- Worker wire protocol is v4 and explicitly carries all ObservationEvidence provenance fields.
- `adapters/worker_entrypoint.py` now implements one bounded request per process, a static dispatch table, strict JSON payload parsing (duplicate keys and non-standard constants rejected), fixed SurfCore QQ batch mapping, target/stream binding, v4 evidence serialization, and proposed-cursor metadata return.
- The entrypoint supports both repository source layout (`adapters/worker_entrypoint.py`) and the staged bundle layout (`app/worker_entrypoint.py`) while running with `-I -S -B`. It adds only the resolved, host-staged app root to `sys.path`.
- `tests/test_worker_entrypoint.py` covers the dispatch contract and a real subprocess invocation under isolated Python flags.
- Runs #656, #661, #663, and #664 passed on Ubuntu and Windows. Run #664 includes the isolated-mode subprocess test and complete test discovery.
- The workflow PR path filters have been reconciled to include the worker entrypoint, runtime bundle, protocol, SurfCore mapping/result, host, and Windows backend test files. The workflow-only follow-up commit is awaiting its own CI run.
- Still not implemented: a production Windows AppContainer executor that composes bundle verification/staging, AppContainer profile, ACLs, explicit environment, inherited pipes, Job Object, suspended launch/resume, bounded concurrent I/O, response validation, and mandatory cleanup into one fail-closed lifecycle.
- The entrypoint is not a network client and does not connect to QQ/Bilibili. Live platform ingestion remains outside this slice.
