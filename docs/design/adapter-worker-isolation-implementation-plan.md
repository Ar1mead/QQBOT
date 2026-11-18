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
