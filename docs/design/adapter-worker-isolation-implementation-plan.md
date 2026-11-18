# Adapter Worker OS Isolation — Implementation Plan

> Status: implementation plan; no production launcher or sandbox is implemented.
>
> Decision: implement and verify Windows first because the intended owner runtime is Windows, then implement Linux parity. Do not enable any untrusted adapter until both the target OS backend and its adversarial tests pass.

## 1. Why this is the next critical path

The repository already has:

- a versioned, strict JSON worker protocol;
- host-side request/response validation and evidence reconstruction;
- a `WorkerExecutor` interface;
- a `WorkerBackedObservationAdapter` bridge;
- fake-executor tests on the Ubuntu/Windows CI matrix.

It does not yet have a process launcher or an OS security boundary. The fake executor proves protocol and host validation only. A Python subprocess alone would not close this gap.

The SurfCore QQ journal reference code is separate and remains unconnected. It may continue to be reviewed as a reference artifact, but live QQ/Bilibili data must not be admitted to CSD through an unisolated third-party adapter.

## 2. Scope and trust boundaries

The first production worker is an **offline observation transformer**:

- Input: one bounded, versioned request plus already-fetched DTO bytes supplied by the trusted host over an anonymous pipe.
- Output: one bounded worker-protocol response over a separate anonymous pipe.
- No direct CSD database handle, project root, user profile, browser profile, QQ/Bilibili credential, API key, or inherited environment.
- No network access, including loopback, private, link-local, and metadata destinations.
- No child process creation.
- Only a dedicated temporary directory is writable.
- All worker output remains untrusted and is reconstructed/validated by the existing host before CSD mapping.

This deliberately avoids giving the worker the SurfCore bearer credential or allowing it to fetch its own input. A future network-requiring adapter would need a separately reviewed, narrow host-owned egress broker; it must not silently weaken this default.

The worker executable, runtime, and adapter package are host-selected and pinned. The worker does not choose its executable, command-line arguments, working directory, environment, filesystem mounts, or security policy.

## 3. Windows backend — first implementation target

### 3.1 Required controls

Use a dedicated Windows AppContainer identity with no network capabilities, combined with a Job Object. Create the process suspended, assign it to the Job Object, and only then resume it.

The host-owned launcher must:

1. Create or derive a stable, project-specific AppContainer profile SID.
2. Grant that SID read/execute access only to the pinned worker runtime and adapter package.
3. Grant that SID read/write access only to a fresh per-invocation temporary directory.
4. Create a minimal environment block from an explicit allowlist; do not inherit the parent environment.
5. Create anonymous stdin/stdout/stderr pipes and use an explicit inherited-handle list. No unrelated host handles may be inherited.
6. Launch with `STARTUPINFOEX` and `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`, with an empty capability list (in particular, no internet/private-network capabilities).
7. Create a Job Object with kill-on-close, active-process limit 1, bounded process memory, and a CPU-rate or CPU-time limit. Assign the suspended process before resume.
8. Enforce wall-clock timeout by terminating the entire Job Object.
9. Read stdout/stderr incrementally with strict independent byte caps; terminate the job immediately on overflow. Do not buffer unbounded output and check only after process exit.
10. Close all handles and remove the per-invocation temporary directory on every exit path.

### 3.2 Fail-closed conditions

- If AppContainer creation, ACL setup, process attribute setup, Job Object configuration, assignment, or any required policy check fails, do not launch the worker.
- Do not fall back to ordinary `subprocess.Popen`.
- Do not grant broad access to the user's profile or project directory to make Python imports work. Package the required runtime/dependencies in a dedicated read-only worker runtime and grant only that path.
- Do not add network capabilities for convenience.
- Do not claim the process is sandboxed merely because its token is AppContainer; acceptance tests must prove the actual filesystem, network, process, and resource restrictions.

### 3.3 Windows implementation modules (proposed)

- `adapters/worker_backends/windows_appcontainer.py`: AppContainer profile/SID, ACL setup, STARTUPINFOEX process creation, Job Object, pipe and cleanup lifecycle.
- `adapters/worker_backends/windows_acl.py`: narrowly scoped ACL helpers for the worker runtime and per-run temp directory.
- `adapters/worker_backends/common.py`: bounded pipe reader, request framing, timeout/result types shared by OS backends.
- `adapters/worker_backends/__init__.py`: explicit platform backend selection; unsupported platforms fail closed.

Use Python standard-library `ctypes` initially to avoid a hidden dependency on an unpinned helper package. Keep Win32 structures/constants in a small audited module and add layout/size assertions for every ctypes structure passed to the OS.

### 3.4 First ACL helper slice — directory descriptors only

The reference implementation now contains `adapters/worker_backends/windows_acl.py`:

- Opens the target directory through `CreateFileW` with a handle, share-all semantics, backup-directory support, and `FILE_FLAG_OPEN_REPARSE_POINT`; it rejects a final-component reparse point and non-directory target.
- Reads the existing DACL with `GetSecurityInfo`, merges one package-SID grant through `SetEntriesInAclW`, applies only `DACL_SECURITY_INFORMATION` with `SetSecurityInfo`, and reads the DACL back to verify the package SID, requested access mask, and inheritance flags.
- Refuses a null DACL rather than silently replacing an everyone-full-access descriptor. Runtime gets read/execute; the per-run temp directory gets read/write without an execute grant.
- Sets the temp directory's Low Integrity label using `LABEL_SECURITY_INFORMATION` and a `SYSTEM_MANDATORY_LABEL_NO_WRITE_UP` ACE with object/container inheritance. This targets the mandatory-label component rather than replacing the audit SACL; it does not request `SACL_SECURITY_INFORMATION` or enable `SE_SECURITY_NAME`. The handle requests `WRITE_OWNER`; if the host cannot apply the label, setup fails closed.
- Reads the mandatory label back and checks the Low Integrity SID, no-write-up mask, and inheritance flags. ACL-related ctypes structures have Win64 size assertions.

Limitations at this slice:

- These helpers configure and inspect directory security descriptors; they do not launch an AppContainer process or prove effective access from its token.
- Runtime packaging must use a host-controlled dedicated tree. Inheritable ACEs are set on the selected root; protected descendant ACLs and ancestor reparse points still require explicit staging/verification by the eventual launcher. Do not point this helper at an arbitrary existing user or project tree.
- The Windows-only integration test is a hosted CI check of descriptor setup/read-back. It is not an adversarial sandbox test and is not local verification on the owner's machine.

### 3.5 Job Object policy slice — configuration only

The next reference module, `adapters/worker_backends/windows_job.py`, creates an unnamed Job Object and configures:

- kill-on-job-close;
- active process limit of exactly one;
- finite per-process and per-job memory ceilings;
- CPU hard-cap control in Windows 1/100-percent units;
- no breakaway flags.

It queries the Job Object back and rejects any mismatch. The API requires explicit memory and CPU limits; it does not silently choose a machine-dependent default. The scoped wrapper closes the Job Object handle, which will terminate assigned members once a launcher exists.

This slice does not yet create or assign a process. It does not test that closing the Job Object kills a real worker, and it does not provide timeout supervision. Those behaviors must be tested when suspended process creation and assignment are implemented.

### 3.6 STARTUPINFOEX attribute-list slice — no process creation yet

The reference module `adapters/worker_backends/windows_startup.py` now builds the two required extended-startup attributes:

- `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`: accepts one to three unique handles only, verifies each handle is valid and marked inheritable, and retains the native handle array.
- `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`: accepts only a live `EmptyAppContainerCapabilities` lease whose package SID is present and whose capability count is exactly zero.
- Uses the documented two-call `InitializeProcThreadAttributeList` size-probe pattern, requires the expected `ERROR_INSUFFICIENT_BUFFER`, initializes the opaque list, applies both attributes, and retains all referenced buffers and the capability lease.
- Initializes `STARTUPINFOEX.StartupInfo.cb` to the full extended structure size. The caller must keep both this object and the capability lease alive through the future `CreateProcessW` call.

This is attribute-list construction and handle validation only. It does not call `CreateProcessW`, create anonymous pipes, build the explicit environment block, assign the process to a Job Object, or resume a suspended thread. The Windows tests use inheritable event handles to validate attribute construction without starting a child process.

Additional Microsoft references:
- [InitializeProcThreadAttributeList](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-initializeprocthreadattributelist): required size probe, initialization, and deletion lifecycle.
- [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute): explicit handle-list and AppContainer security-capability attributes.
- [Create processes](https://learn.microsoft.com/en-us/windows/win32/procthread/creating-processes): avoid inherited handles except the explicitly enumerated list.
### 3.7 Pipe-handle and environment preparation slices — no process launch yet

Two preparation modules are now present:

- `adapters/worker_backends/windows_pipes.py` creates three anonymous pipes with a bounded requested buffer size. It retains parent stdin-write/stdout-read/stderr-read ends and child stdin-read/stdout-write/stderr-write ends. All six handles are checked; only the three child ends remain inheritable. The parent ends have `HANDLE_FLAG_INHERIT` cleared and are read back before the object is returned.
- The pipe owner exposes exactly the three child ends for the startup handle allowlist and provides a one-way close operation for the host copies after a future successful CreateProcess call. It has no read/write implementation yet; a future I/O supervisor must stream and cap bytes rather than buffer unbounded output.
- `adapters/worker_backends/windows_environment.py` builds a sorted Unicode environment block from a strict allowlist. It requires absolute `SystemRoot`, `WINDIR`, `TEMP`, and `TMP` paths; rejects unknown names, case-colliding names, NULs, empty values, and oversized blocks; and forces Python's no-user-site, no-bytecode, and safe-path flags. It never copies the host's ambient environment.
- These are resource-preparation helpers only. No process is created, no pipes are read or written, no output limit or timeout is enforced, and no process has been assigned to a Job Object.

### 3.8.1 AppContainer LOCALAPPDATA requirement discovered by the first launch attempt

The first Windows AppContainer process creation attempt returned Win32 error 203. The environment block was syntactically valid, but it omitted the AppContainer-specific `LOCALAPPDATA` variable. Microsoft's AppContainer launch documentation states that the container profile is accessed through `LOCALAPPDATA` or `GetAppContainerFolderPath`; the documented value is the profile's AppContainer local-data directory, not an arbitrary host or worker temp path.

The implementation now:

- adds `LOCALAPPDATA` to the strict environment allowlist and required absolute-path set;
- exposes the SID associated with the live `EmptyAppContainerCapabilities` lease;
- calls `GetAppContainerFolderPath` for that exact SID and frees the returned path with `CoTaskMemFree`;
- requires the launch environment's `LOCALAPPDATA` to match that OS-managed path and requires the folder to exist;
- keeps `TEMP` and `TMP` pointed at the separately ACL-hardened per-run working directory.

The Windows launch test now uses the API-returned AppContainer profile path. This is a correction based on Microsoft's documented environment contract, not yet a verified launch result; the corrected process-launch CI run is pending.

Reference: [Microsoft — Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer) and [GetAppContainerFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-getappcontainerfolderpath).

### 3.8 Suspended AppContainer process launch — first end-to-end launch path

The reference module `adapters/worker_backends/windows_process.py` now implements the launch ordering:

1. Validate the executable and working directory as absolute existing paths; resolve them and reject a reparse-point executable or working directory.
2. Re-verify the worker's three pipe handles and the exact inheritance split; re-verify the environment block's metadata and native buffer; require `TEMP` and `TMP` to match the dedicated worker working directory.
3. Re-query the Job Object and require kill-on-close, one active process, no breakaway flags, finite matching process/job memory limits, and the configured CPU hard cap.
4. Bind the three child pipe handles to `STARTF_USESTDHANDLES` and require the STARTUPINFOEX handle allowlist to match those exact three handles.
5. Call `CreateProcessW` with an explicit application path, writable command-line buffer, explicit Unicode environment, `bInheritHandles=TRUE` (required by the handle-list attribute), and `CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT`.
6. Assign the still-suspended process to the Job Object.
7. Close the host's duplicate child pipe endpoints.
8. Call `ResumeThread` and require the previous suspend count to be exactly one.

Any failure after process creation attempts Job Object termination (or kill-on-close) and then requires the process handle to become signaled before cleanup is considered successful. If termination cannot be confirmed, it raises a distinct fatal cleanup error and deliberately does not pretend the process was cleaned up.

The returned `WorkerProcess` owns the process handle and supports bounded wait/exit-code inspection. The caller retains the Job Object, pipes, startup attribute list, and environment owners.

### 3.9 Bounded concurrent stdio supervisor — implementation slice

The module `adapters/worker_backends/windows_worker_io.py` now performs one bounded request/response exchange:

- starts independent reader threads for stdout and stderr before writing input, preventing one full output pipe from blocking the worker while the host writes;
- writes the request in chunks, with a 1 MiB maximum, then closes the host's stdin writer to signal EOF;
- concurrently drains stdout (maximum 1 MiB) and stderr (maximum 64 KiB), retaining no more than the configured limits plus one detection byte;
- enforces a 1–300,000 ms wall-clock deadline;
- terminates the Job Object on timeout, pipe error, or output overflow, with kill-on-close and direct-process termination fallbacks, and requires a signaled process handle;
- returns raw bounded stdout/stderr and the process exit code. It does not interpret protocol JSON; the existing host/protocol layer remains responsible for schema, request binding, evidence, and digest validation.

The pipe supervisor is a separate orchestration helper. The caller still owns and must close the process handle, pipe owner, startup attribute list, capability lease, and Job Object. The Windows tests now exercise a successful stdio round trip and an output-overflow case that must terminate the worker.

This still does not complete the security proof. Host-file/CSD-marker denial, network denial, child-process denial, and a timeout-specific adversarial case remain mandatory. A process that is merely launched inside AppContainer is not yet approved for untrusted adapters.


**This is the first process launch implementation, not a complete WorkerExecutor.** The current Windows integration test launches a harmless `cmd.exe /d /c echo WORKER_OK` process in an AppContainer, assigns it to the configured Job Object while suspended, resumes it, and checks its exit/output. It does not yet prove host-file denial, network denial, child-process denial, whole-job timeout, streaming output limits, or complete pipe-drain behavior. Those adversarial tests and the I/O supervisor remain mandatory before any real adapter is enabled.

## 4. Linux backend — parity implementation after Windows

Use a host-installed `bubblewrap` executable selected by an absolute, administrator-reviewed path. Do not use a shell.

Minimum launch policy:

- new user, mount, PID, IPC, UTS, and network namespaces;
- no host network interface (network namespace with loopback only);
- minimal read-only runtime and adapter package mounts;
- no home, project root, CSD store, credential directories, or host `/run` mounts;
- a fresh writable tmpfs or dedicated bounded temporary directory only;
- cleared environment and fixed working directory;
- no-new-privileges and an explicit seccomp policy where supported;
- cgroup v2 limits for memory, CPU, and process count, or fail closed if the configured limits cannot be enforced;
- kill the whole sandbox process tree on timeout or protocol violation.

Do not assume `bubblewrap` exists or that user namespaces/cgroups are available on every Linux host. Probe the required features and fail closed. A container runtime by itself is not proof that the required network/filesystem/resource policy is active.

## 5. Worker protocol integration

The production executor must implement the existing `WorkerExecutor.execute(...)` contract but own all process creation and policy enforcement.

- The host constructs the exact request bytes.
- The worker receives only those bytes on stdin.
- The worker emits exactly one bounded response on stdout.
- stderr is diagnostic-only, bounded, never parsed as protocol, and never trusted.
- The host validates response size while streaming, process exit status, request binding, adapter identity, evidence provenance, digest, and coverage.
- A timeout, non-zero exit, malformed output, pipe closure, output overflow, or sandbox setup failure returns a failed/unknown result. It must never synthesize complete evidence.
- Worker processes receive no database access and cannot append CSD events.

## 6. Adversarial acceptance tests

Each OS backend must run tests that attempt the following from inside the worker:

| Attempt | Required result |
|---|---|
| Read a host-created secret marker outside the runtime/temp directory | Access denied / path absent |
| Read a host-created CSD database marker | Access denied / path absent |
| Read a parent-only environment secret | Variable absent |
| Write outside the dedicated temp directory | Access denied |
| Write inside the dedicated temp directory | Allowed |
| Connect to loopback | Denied |
| Connect to private/link-local/metadata address | Denied |
| Connect to public network | Denied |
| Spawn a child process | Denied |
| Exceed memory/process/CPU limits | Worker terminated or operation rejected by OS limit |
| Hang beyond timeout | Entire process tree/job terminated |
| Emit oversized stdout or stderr | Terminated while streaming; host memory remains bounded |
| Emit malformed, spoofed, or mismatched response | Rejected before CSD mapping |
| Crash after receiving a request | No CSD event is accepted |

Tests must prove the denial from inside the worker, not infer it from launcher flags. Positive controls must prove the worker can still read its pinned runtime, process the bounded input, emit a valid response, and write only to its temporary directory.

The first Windows adversarial integration cases are now authored in `tests/test_worker_windows_process.py`:

- attempt to read host-user-temp and repository-root marker files;
- attempt a TCP connection to a host loopback listener using the Windows `curl.exe`;
- attempt to start a child `cmd.exe` while the Job Object active-process limit is one;
- run a long built-in command and require the wall-clock timeout to terminate it.

These are pending Windows CI and must not be counted as passed until the run is complete. A loopback denial test does not by itself prove all private, link-local, metadata, or public network destinations are blocked; those remain additional coverage.


## 7. Rollout gates

1. Review the Win32 API/ctypes layout and threat model before implementation.
2. Implement the Windows backend only; run the adversarial suite on GitHub Windows and then owner-local Windows 11.
3. Implement Linux parity; run the same semantic suite on Ubuntu.
4. Run protocol, host, CSD, and complete repository regressions on both OSes.
5. Only then enable `WorkerBackedObservationAdapter` for a real read-only source.
6. Keep SurfCore's independent QQ journal disabled by default until its own patch and endpoint are separately reviewed.
7. No third-party adapter code is imported into the CSD process at any stage.

Hosted CI is necessary but does not replace owner-local Windows verification. The actual Windows account, filesystem ACLs, Python runtime location, and endpoint security configuration must be tested on the target machine before enabling live ingestion.

## 8. Reference documentation

- Microsoft, [Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer): AppContainer profile, capabilities, and process launch via extended startup attributes.
- Microsoft, [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute): `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES` creates an AppContainer process.
- Microsoft, [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects): process-tree lifecycle and resource limits.
- Bubblewrap, [project documentation](https://github.com/containers/bubblewrap): mount, user, PID, IPC, UTS, and network namespace isolation.
- Debian manpages, [bubblewrap(1)](https://manpages.debian.org/trixie/bubblewrap/bwrap.1.en.html): namespace and filesystem construction semantics.

These references describe OS mechanisms; they are not evidence that this repository has implemented or verified them.

## 9. Windows security review addendum — integrity labels and verification

The initial implementation checklist must account for Mandatory Integrity Control (MIC), not only DACLs:

- AppContainer processes run at Low Integrity. A newly-created host temp directory normally inherits the host's Medium Integrity label. Granting the AppContainer package SID write access in its DACL is therefore insufficient: MIC's default no-write-up rule still blocks the worker.
- The host must set and verify a Low Integrity mandatory label on the dedicated per-invocation temp directory (and only that directory), with the intended no-write-up policy. Do not lower the integrity label of the runtime, project, user profile, or any parent directory.
- The temp directory DACL must separately grant the exact AppContainer package SID only the minimum create/read/write/delete rights needed for that invocation. The runtime/adapter tree remains read/execute only. Both the DACL and mandatory label must be checked after applying them; any mismatch is a launch failure.
- Prefer the Windows security APIs for composing and applying ACL/SACL entries while preserving unrelated existing entries. Do not replace a directory's entire DACL/SACL with an incomplete hand-built list.
- Treat AppContainer network isolation as a capability boundary: the worker receives an empty capability list, with no InternetClient, InternetClientServer, PrivateNetworkClientServer, or other network capability. The worker still must run adversarial socket tests against loopback, private, link-local, metadata, and public destinations; the implementation must not infer denial solely from an empty list.
- Process creation must use an explicit application path and a writable command-line buffer. Handle inheritance must be restricted to the exact pipe handles via STARTUPINFOEX's handle-list attribute; unrelated host handles must not be inherited.
- Job Object policy must include kill-on-close, active-process limit 1, no breakaway flags, and a finite memory limit. Timeout and output overflow terminate the job, not just the primary process.
- Windows CI is useful for API/structure and behavioral regression coverage, but it does not establish compatibility with the user's installed DSH/Python layout or endpoint-security configuration. Do not enable live adapters on CI evidence alone.

Additional Microsoft references:
- [Mandatory Integrity Control](https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control): low-integrity processes cannot write to medium-integrity objects even when the DACL grants write access.
- [SYSTEM_MANDATORY_LABEL_ACE](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_mandatory_label_ace): the SACL ACE that carries the integrity label and policy.
- [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation): filesystem, network, and process isolation model.
- [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw): explicit application path and inherited-handle controls.

This addendum is a design correction, not an implementation or test result.

The command-based probes consume the bounded request line before attempting their operation. This keeps them aligned with the worker protocol and avoids confusing an intentional early stdin close with a filesystem/network denial result.

### 3.10 First Windows adversarial results

Run #630 passed the current adversarial cases on GitHub's Windows runner: host-user-temp and repository-root marker reads were denied, a host loopback listener was unreachable, child process creation was blocked by the active-process limit, and a bounded wall-clock timeout terminated the worker. Stdout overflow and the positive stdio round trip also passed.

These are important initial results, not a complete isolation certification. Explicit private/link-local/metadata/public network attempts, broader filesystem traversal checks, and verification on the actual target Windows/DSH environment remain outstanding. The Linux backend has not yet been implemented.

The filesystem adversarial suite now also includes a positive/negative write boundary: a worker-created file inside the dedicated temp directory must exist and contain its marker, while an attempted write into a separate host-user temp directory must leave no file behind. This test is pending Windows CI.

### 3.10.1 Dedicated temp write boundary verified

Run #631 passed the positive/negative write test: the worker created a file in its dedicated temp directory, while the host-user temp target remained absent after the worker's write attempt. This supplements the host-file read denial checks; it does not prove denial for every filesystem namespace or device path.

The Windows Job Object adversarial suite now includes a kill-on-close test: a running worker is left blocked on stdin, the host closes the Job Object handle, and the test requires the worker process handle to become signaled. This is pending CI.

Run #632 verified kill-on-close against a live process: the worker was launched and left waiting on stdin, the host closed the Job Object handle, and the process handle became signaled. This is stronger than the earlier configuration-only read-back test.

A private-interface network probe has been added: the host first proves it can connect to a listener bound to its own private IPv4 address, then the AppContainer worker attempts the same TCP connection. The worker must fail and the server must receive no second connection. This test is pending Windows CI.

### 3.10.2 Private-interface network denial verified

Run #633 passed the private-interface test with a host positive control: the host connected to a listener bound to its own private IPv4 address, while the AppContainer worker could not establish the same connection. Loopback denial remains separately covered. Link-local/cloud metadata and public destinations are still not tested.

### 3.11 Recursive runtime ACL hardening

The runtime grant no longer relies on directory inheritance alone. It enumerates all existing entries, rejects reparse points from the runtime root's ancestors and descendants, then applies and reads back an explicit read/execute ACE for each existing file and directory. Directory ACEs are inheritable for future runtime contents; file ACEs are direct. Enumeration is capped at 100,000 entries. The new nested-file and symlink tests are pending CI.

Run #634 passed the recursive runtime ACL descriptor suite on both matrix platforms. The Windows test used pre-existing nested directories and files. The reparse-point test is conditional on symlink creation being enabled on the runner; do not assume it executed if the test was skipped.

Run #635 exercised the copied runtime executable successfully, including the read/execute-only runtime directory test. Two unrelated tests failed due to stale four-value tuple unpacking after the test helper began returning the runtime directory as a fifth value; this also interrupted cleanup. The fixture has been corrected, but the full test suite must pass in a new run.

### 3.11.1 Runtime executable launched under recursive ACLs

Run #636 passed an end-to-end test that copied `cmd.exe` into a separate runtime directory, applied recursive read/execute ACLs, and launched that copied binary as the AppContainer worker. The worker could execute it, could not create a file in the runtime directory, and could write to the distinct Low-Integrity temp directory. This verifies the runtime ACL path for a representative existing executable; it does not yet verify the full Python runtime or a production WorkerExecutor.

### 3.12 Ephemeral AppContainer profile lifecycle

Production worker invocations should use a fresh AppContainer profile rather than the persistent named CI profile. `EphemeralAppContainerProfile.create()` creates a UUID-backed unique profile, retrieves its AppContainer SID and `GetAppContainerFolderPath` result, and owns `DeleteAppContainerProfile` cleanup. The process/job/pipe owners must be closed before the profile is deleted. This prevents the AppContainer's LocalAppData from becoming persistent cross-run storage. The new lifecycle test is pending CI.

Run #637 passed the ephemeral profile lifecycle test on Windows: unique profile/SID creation, LocalAppData resolution, profile deletion, folder removal, and closed-owner behavior. The existing process integration still uses the persistent CI profile; switching it to the ephemeral owner is the next integration step.

The Windows process integration now uses `EphemeralAppContainerProfile` for each worker session and closes it only after the process/job/startup/pipe owners have unwound. This replaces the persistent CI profile in the process-launch tests; the integrated lifecycle is pending CI.

### 3.12.1 Ephemeral profile integrated into process tests

Run #638 passed the full Windows process integration suite with a fresh AppContainer profile per session. The process, Job Object, startup attributes, and pipes are closed before the profile owner deletes the AppContainer profile and its LocalAppData folder. This validates the cleanup ordering in the test harness, though production WorkerExecutor integration remains future work.


## Next implementation sequence after the first Windows launch

The first Windows AppContainer process launch is no longer the blocker. The remaining path is: (1) complete safe link-local/metadata/public network probes, (2) verify the actual Python runtime tree and interpreter behavior under recursive read/execute ACLs, (3) implement the host-owned production `WindowsAppContainerWorkerExecutor` against the existing WorkerHost/WorkerExecutor contract, (4) adversarially test that exact Python worker, (5) implement Linux Bubblewrap parity, and only then (6) resume SurfCore live ingress. Do not enable untrusted adapter code or real platform transport before these steps pass.

Profile cleanup follows Microsoft's documented behavior: if `DeleteAppContainerProfile` fails, the profile state is indeterminate and the API should be called again. The ephemeral owner now retries once and only marks itself closed after success. See [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile).

Run #639 passed the profile-deletion retry tests and the full Windows/Ubuntu matrix. The ephemeral owner now retries once after a failed HRESULT and fails closed if the second attempt also fails. Microsoft notes that a failed deletion leaves profile state indeterminate and recommends another call to complete deletion.


## 3.13 Python runtime integration probe

The next Windows integration test now copies a minimal CPython runtime into the dedicated worker runtime tree: base executable, top-level DLL dependencies, standard-library `Lib`, extension-module `DLLs`, and optional versioned stdlib zip/`._pth` files. It launches that interpreter with `-I -S -B` inside the existing AppContainer/Job/pipe/ACL harness.

The probe checks request stdin, standard-library and native-extension imports (`ssl`, `sqlite3`), isolated/no-site/no-bytecode flags, `sys.path` containment within the copied runtime, absence of a parent-only environment secret, denied writes to the runtime, and successful writes only to the dedicated temp directory. This is test coverage only; a production `WindowsAppContainerWorkerExecutor` remains unimplemented. CI pending.


### 3.13.1 Run #640 finding and correction

The first Python runtime integration run proved that CPython 3.12 and the selected stdlib/native extensions load inside the AppContainer, but the test failed when writing to `TEMP`: Windows exposed an AppContainer-scoped temp path under the ephemeral profile and the directory did not yet exist. The probe now creates that OS-managed temp directory, verifies it is contained within the profile's `LOCALAPPDATA`, and independently tests the host-provisioned ACL-granted temp directory. The request-line CRLF comparison was corrected. Run #641 is required before marking the Python runtime integration as verified.
