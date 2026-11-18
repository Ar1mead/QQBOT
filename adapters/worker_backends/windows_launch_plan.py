"""Build fixed Windows launch arguments from a staged, verified worker bundle.

Only host-compiled adapter bindings are accepted. The bundle manifest supplies
integrity metadata and file locations; it cannot introduce a new dispatch key,
module path, command, or adapter implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import stat

from .runtime_bundle import (
    RuntimeAdapterBinding,
    StagedRuntimeBundle,
    verify_staged_runtime,
)


SUPPORTED_PYTHON_IMPLEMENTATION = "CPython"
SUPPORTED_PYTHON_MAJOR_MINOR = (3, 12)
PINNED_INTERPRETER_PATH = "python/python.exe"
PINNED_ENTRYPOINT_PATH = "app/worker_entrypoint.py"


@dataclass(frozen=True)
class WindowsTrustedAdapterBinding:
    adapter_id: str
    adapter_version: str
    operation: str
    dispatch_key: str


# This is the host-owned allowlist. Adding another operation requires a reviewed
# code change here and a matching static handler in worker_entrypoint.py.
TRUSTED_WINDOWS_ADAPTER_BINDINGS = (
    WindowsTrustedAdapterBinding(
        adapter_id="surfcore.qq.readonly",
        adapter_version="0.1.0",
        operation="observe_batch",
        dispatch_key="surfcore_qq_batch",
    ),
)


@dataclass(frozen=True)
class WindowsWorkerLaunchPlan:
    adapter_id: str
    adapter_version: str
    operation: str
    dispatch_key: str
    python_version: str
    manifest_sha256: str
    application_path: str
    arguments: tuple[str, ...]
    current_directory: str


def _is_reparse_or_symlink(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x0400
    )


def _checked_staged_file(root: str, relative_path: str) -> str:
    """Resolve one manifest path while rejecting links at every path segment."""
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("staged runtime relative path is invalid")
    parts = relative_path.split("/")
    if any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in parts):
        raise ValueError("staged runtime path is not canonical")
    root_info = os.lstat(root)
    if _is_reparse_or_symlink(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ValueError("staged runtime root must be a real directory")

    current = root
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        info = os.lstat(current)
        if _is_reparse_or_symlink(info):
            raise ValueError("staged runtime path contains a link or reparse point")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ValueError("staged runtime parent path must be a directory")
        if index == len(parts) - 1 and not stat.S_ISREG(info.st_mode):
            raise ValueError("staged runtime target must be a regular file")

    root_real = os.path.realpath(root)
    target_real = os.path.realpath(current)
    try:
        if os.path.commonpath((root_real, target_real)) != root_real:
            raise ValueError("staged runtime path escapes its root")
    except ValueError as exc:
        raise ValueError("staged runtime path escapes its root") from exc
    return target_real


def build_windows_worker_launch_plan(
    staged: StagedRuntimeBundle,
    *,
    adapter_id: str,
    adapter_version: str,
    operation: str,
) -> WindowsWorkerLaunchPlan:
    """Return fixed interpreter/entrypoint/dispatch arguments for one allowlisted operation."""
    if not isinstance(staged, StagedRuntimeBundle):
        raise TypeError("staged must be a StagedRuntimeBundle")
    verify_staged_runtime(staged)
    manifest_pin = staged.trusted_manifest_sha256
    if (
        not isinstance(manifest_pin, str)
        or len(manifest_pin) != 64
        or any(char not in "0123456789abcdef" for char in manifest_pin)
    ):
        raise ValueError("staged runtime manifest is not authenticated by a host-pinned digest")

    trusted = next(
        (
            item for item in TRUSTED_WINDOWS_ADAPTER_BINDINGS
            if (item.adapter_id, item.adapter_version, item.operation)
            == (adapter_id, adapter_version, operation)
        ),
        None,
    )
    if trusted is None:
        raise ValueError("adapter operation is not in the host's trusted worker allowlist")

    expected_manifest_binding = RuntimeAdapterBinding(
        trusted.adapter_id,
        trusted.adapter_version,
        trusted.operation,
        trusted.dispatch_key,
    )
    if staged.manifest.adapters != (expected_manifest_binding,):
        raise ValueError("runtime bundle adapter bindings do not exactly match the host allowlist")

    if staged.manifest.python_implementation != SUPPORTED_PYTHON_IMPLEMENTATION:
        raise ValueError("runtime bundle Python implementation is not supported")
    version_parts = staged.manifest.python_version.split(".")
    if (
        len(version_parts) != 3
        or any(not part.isascii() or not part.isdigit() for part in version_parts)
        or tuple(int(part) for part in version_parts[:2]) != SUPPORTED_PYTHON_MAJOR_MINOR
    ):
        raise ValueError("runtime bundle Python version is outside the supported 3.12 series")

    if staged.manifest.interpreter_path != PINNED_INTERPRETER_PATH:
        raise ValueError("runtime bundle interpreter path does not match the pinned layout")
    if staged.manifest.entrypoint_path != PINNED_ENTRYPOINT_PATH:
        raise ValueError("runtime bundle entrypoint path does not match the pinned layout")

    root = os.path.abspath(staged.root_path)
    interpreter_path = _checked_staged_file(root, PINNED_INTERPRETER_PATH)
    entrypoint_path = _checked_staged_file(root, PINNED_ENTRYPOINT_PATH)

    expected_interpreter = os.path.abspath(
        os.path.join(root, *PINNED_INTERPRETER_PATH.split("/"))
    )
    expected_entrypoint = os.path.abspath(
        os.path.join(root, *PINNED_ENTRYPOINT_PATH.split("/"))
    )
    if os.path.normcase(interpreter_path) != os.path.normcase(expected_interpreter):
        raise ValueError("staged interpreter path does not match the verified manifest")
    if os.path.normcase(entrypoint_path) != os.path.normcase(expected_entrypoint):
        raise ValueError("staged entrypoint path does not match the verified manifest")
    if os.path.abspath(staged.interpreter_path) != expected_interpreter:
        raise ValueError("staged interpreter metadata does not match its pinned path")
    if os.path.abspath(staged.entrypoint_path) != expected_entrypoint:
        raise ValueError("staged entrypoint metadata does not match its pinned path")

    return WindowsWorkerLaunchPlan(
        adapter_id=trusted.adapter_id,
        adapter_version=trusted.adapter_version,
        operation=trusted.operation,
        dispatch_key=trusted.dispatch_key,
        python_version=staged.manifest.python_version,
        manifest_sha256=manifest_pin,
        application_path=interpreter_path,
        arguments=(
            "-I",
            "-S",
            "-B",
            entrypoint_path,
            "--dispatch-key",
            trusted.dispatch_key,
        ),
        current_directory=os.path.dirname(entrypoint_path),
    )
