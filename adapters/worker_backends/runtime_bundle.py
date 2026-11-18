"""Bounded, fail-closed manifest parsing and verification for worker runtime bundles.

This module does not stage files or launch processes. The bundle root must be
owned and protected by the trusted host; a later staging layer copies only the
verified manifest-listed files into a per-invocation runtime tree.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
from typing import Any


MAX_MANIFEST_BYTES = 1 * 1024 * 1024
MAX_BUNDLE_FILES = 10_000
MAX_BUNDLE_FILE_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ADAPTER_BINDINGS = 256
MANIFEST_FILENAME = "bundle-manifest.json"
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_DISPATCH_KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class RuntimeBundleError(ValueError):
    """Raised when a runtime bundle is malformed, unsafe, or fails integrity checks."""


@dataclass(frozen=True)
class RuntimeBundleFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class RuntimeAdapterBinding:
    adapter_id: str
    adapter_version: str
    operation: str
    dispatch_key: str


@dataclass(frozen=True)
class RuntimeBundleManifest:
    bundle_id: str
    python_implementation: str
    python_version: str
    interpreter_path: str
    entrypoint_path: str
    files: tuple[RuntimeBundleFile, ...]
    adapters: tuple[RuntimeAdapterBinding, ...]
    total_bytes: int
    schema_version: int = 1


@dataclass(frozen=True)
class VerifiedRuntimeBundle:
    root_path: str
    manifest: RuntimeBundleManifest


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeBundleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise RuntimeBundleError(f"non-standard JSON constant is not allowed: {value}")


def _bounded_text(value: Any, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise RuntimeBundleError(f"{field} must be a non-empty string of at most {maximum} characters")
    if any(ord(char) < 32 for char in value):
        raise RuntimeBundleError(f"{field} must not contain control characters")
    return value


def _canonical_relative_path(value: Any, field: str) -> str:
    path = _bounded_text(value, field, 512)
    if "\\" in path or ":" in path or path.startswith("/"):
        raise RuntimeBundleError(f"{field} must be a canonical relative POSIX path")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or parsed.as_posix() != path:
        raise RuntimeBundleError(f"{field} must be a canonical relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise RuntimeBundleError(f"{field} must not contain empty, dot, or parent path segments")
    if path == MANIFEST_FILENAME:
        raise RuntimeBundleError("manifest file must not list itself")
    return path


def parse_runtime_bundle_manifest(raw: bytes | str) -> RuntimeBundleManifest:
    """Parse an exact, bounded manifest without touching the filesystem."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_MANIFEST_BYTES:
            raise RuntimeBundleError("runtime bundle manifest exceeds the size limit")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RuntimeBundleError("runtime bundle manifest must be UTF-8") from exc
    elif isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise RuntimeBundleError("runtime bundle manifest exceeds the size limit")
        text = raw
    else:
        raise TypeError("runtime bundle manifest must be bytes or str")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except RuntimeBundleError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise RuntimeBundleError("runtime bundle manifest is not valid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeBundleError("runtime bundle manifest root must be an object")

    expected = {
        "schema_version", "bundle_id", "python_implementation", "python_version",
        "interpreter_path", "entrypoint_path", "files", "adapters",
    }
    if set(value) != expected:
        raise RuntimeBundleError("runtime bundle manifest fields do not match the exact schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise RuntimeBundleError("unsupported runtime bundle manifest schema_version")

    bundle_id = _bounded_text(value["bundle_id"], "bundle_id", 128)
    python_implementation = _bounded_text(value["python_implementation"], "python_implementation", 32)
    python_version = _bounded_text(value["python_version"], "python_version", 32)
    interpreter_path = _canonical_relative_path(value["interpreter_path"], "interpreter_path")
    entrypoint_path = _canonical_relative_path(value["entrypoint_path"], "entrypoint_path")

    raw_files = value["files"]
    if not isinstance(raw_files, list) or not 1 <= len(raw_files) <= MAX_BUNDLE_FILES:
        raise RuntimeBundleError("files must be a non-empty array within the bundle file-count limit")
    files: list[RuntimeBundleFile] = []
    prior_path = ""
    total_bytes = 0
    for raw_file in raw_files:
        if not isinstance(raw_file, dict) or set(raw_file) != {"path", "size", "sha256"}:
            raise RuntimeBundleError("each bundle file must have exactly path, size, and sha256")
        path = _canonical_relative_path(raw_file["path"], "file.path")
        if path <= prior_path:
            raise RuntimeBundleError("bundle file paths must be unique and sorted lexicographically")
        prior_path = path
        size = raw_file["size"]
        if type(size) is not int or not 0 <= size <= MAX_BUNDLE_FILE_BYTES:
            raise RuntimeBundleError("bundle file size is outside the allowed bounds")
        digest = raw_file["sha256"]
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise RuntimeBundleError("bundle file sha256 must be 64 lowercase hexadecimal characters")
        total_bytes += size
        if total_bytes > MAX_BUNDLE_TOTAL_BYTES:
            raise RuntimeBundleError("runtime bundle exceeds the total size limit")
        files.append(RuntimeBundleFile(path, size, digest))

    file_paths = {item.path for item in files}
    if interpreter_path not in file_paths or entrypoint_path not in file_paths:
        raise RuntimeBundleError("interpreter_path and entrypoint_path must be listed in files")

    raw_adapters = value["adapters"]
    if not isinstance(raw_adapters, list) or not 1 <= len(raw_adapters) <= MAX_ADAPTER_BINDINGS:
        raise RuntimeBundleError("adapters must be a non-empty bounded array")
    adapters: list[RuntimeAdapterBinding] = []
    prior_binding: tuple[str, str, str] | None = None
    dispatch_keys: set[str] = set()
    for raw_adapter in raw_adapters:
        if not isinstance(raw_adapter, dict) or set(raw_adapter) != {
            "adapter_id", "adapter_version", "operation", "dispatch_key",
        }:
            raise RuntimeBundleError("each adapter binding must have exactly four fields")
        adapter_id = _bounded_text(raw_adapter["adapter_id"], "adapter_id", 128)
        adapter_version = _bounded_text(raw_adapter["adapter_version"], "adapter_version", 64)
        operation = _bounded_text(raw_adapter["operation"], "operation", 64)
        dispatch_key = _bounded_text(raw_adapter["dispatch_key"], "dispatch_key", 64)
        if not _DISPATCH_KEY_RE.fullmatch(dispatch_key):
            raise RuntimeBundleError("dispatch_key must be a fixed lowercase identifier, not a module path")
        binding_key = (adapter_id, adapter_version, operation)
        if prior_binding is not None and binding_key <= prior_binding:
            raise RuntimeBundleError("adapter bindings must be unique and sorted")
        prior_binding = binding_key
        if dispatch_key in dispatch_keys:
            raise RuntimeBundleError("adapter dispatch_key values must be unique")
        dispatch_keys.add(dispatch_key)
        adapters.append(RuntimeAdapterBinding(*binding_key, dispatch_key))

    return RuntimeBundleManifest(
        bundle_id=bundle_id,
        python_implementation=python_implementation,
        python_version=python_version,
        interpreter_path=interpreter_path,
        entrypoint_path=entrypoint_path,
        files=tuple(files),
        adapters=tuple(adapters),
        total_bytes=total_bytes,
    )


def _is_reparse_or_symlink(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _safe_lstat(path: str, *, directory: bool | None = None) -> os.stat_result:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise RuntimeBundleError(f"cannot inspect bundle path: {path}") from exc
    if _is_reparse_or_symlink(info):
        raise RuntimeBundleError(f"bundle path must not be a symlink or reparse point: {path}")
    if directory is True and not stat.S_ISDIR(info.st_mode):
        raise RuntimeBundleError(f"bundle path must be a directory: {path}")
    if directory is False and not stat.S_ISREG(info.st_mode):
        raise RuntimeBundleError(f"bundle path must be a regular file: {path}")
    return info


def _walk_bundle_files(root: str) -> set[str]:
    found: set[str] = set()

    def visit(directory: str, relative: str) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise RuntimeBundleError(f"cannot enumerate bundle directory: {directory}") from exc
        for entry in entries:
            rel = f"{relative}/{entry.name}" if relative else entry.name
            info = _safe_lstat(entry.path)
            if stat.S_ISDIR(info.st_mode):
                visit(entry.path, rel)
            elif stat.S_ISREG(info.st_mode):
                found.add(rel.replace(os.sep, "/"))
            else:
                raise RuntimeBundleError(f"bundle contains a non-regular file: {rel}")

    visit(root, "")
    return found


def verify_runtime_bundle(root_path: str, manifest: RuntimeBundleManifest) -> VerifiedRuntimeBundle:
    """Verify the exact on-disk file set, sizes, and digests listed in a manifest.

    The root must be host-owned and not writable by untrusted principals while
    verification occurs. This function rejects symlinks/reparse points and
    checks file identity/metadata before and after hashing, but is not a
    substitute for protected ACLs against a concurrent privileged writer.
    """
    if not isinstance(manifest, RuntimeBundleManifest):
        raise TypeError("manifest must be a RuntimeBundleManifest")
    if not isinstance(root_path, str) or not root_path:
        raise ValueError("root_path must be a non-empty path")
    absolute_root = os.path.abspath(root_path)
    root_info = _safe_lstat(absolute_root, directory=True)
    if not stat.S_ISDIR(root_info.st_mode):
        raise RuntimeBundleError("runtime bundle root must be a directory")

    actual_files = _walk_bundle_files(absolute_root)
    expected_files = {item.path for item in manifest.files} | {MANIFEST_FILENAME}
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise RuntimeBundleError(f"runtime bundle file set mismatch; missing={missing}, extra={extra}")

    for item in manifest.files:
        components = item.path.split("/")
        current = absolute_root
        for component in components[:-1]:
            current = os.path.join(current, component)
            _safe_lstat(current, directory=True)
        target = os.path.join(absolute_root, *components)
        before = _safe_lstat(target, directory=False)
        if before.st_size != item.size:
            raise RuntimeBundleError(f"runtime bundle file size mismatch: {item.path}")
        digest = hashlib.sha256()
        try:
            with open(target, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (
                    opened.st_dev, opened.st_ino, opened.st_size
                ) != (before.st_dev, before.st_ino, before.st_size):
                    raise RuntimeBundleError(f"runtime bundle file changed during open: {item.path}")
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                after = os.fstat(stream.fileno())
        except RuntimeBundleError:
            raise
        except OSError as exc:
            raise RuntimeBundleError(f"cannot read runtime bundle file: {item.path}") from exc
        if (
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        ):
            raise RuntimeBundleError(f"runtime bundle file changed while hashing: {item.path}")
        if digest.hexdigest() != item.sha256:
            raise RuntimeBundleError(f"runtime bundle SHA-256 mismatch: {item.path}")

    return VerifiedRuntimeBundle(absolute_root, manifest)


def load_runtime_bundle(root_path: str) -> VerifiedRuntimeBundle:
    """Load and verify bundle-manifest.json and every listed file."""
    if not isinstance(root_path, str) or not root_path:
        raise ValueError("root_path must be a non-empty path")
    absolute_root = os.path.abspath(root_path)
    _safe_lstat(absolute_root, directory=True)
    manifest_path = os.path.join(absolute_root, MANIFEST_FILENAME)
    info = _safe_lstat(manifest_path, directory=False)
    if info.st_size > MAX_MANIFEST_BYTES:
        raise RuntimeBundleError("runtime bundle manifest exceeds the size limit")
    try:
        with open(manifest_path, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev, opened.st_ino, opened.st_size
            ) != (info.st_dev, info.st_ino, info.st_size):
                raise RuntimeBundleError("runtime bundle manifest changed during open")
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except RuntimeBundleError:
        raise
    except OSError as exc:
        raise RuntimeBundleError("cannot read runtime bundle manifest") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise RuntimeBundleError("runtime bundle manifest exceeds the size limit")
    manifest = parse_runtime_bundle_manifest(raw)
    return verify_runtime_bundle(absolute_root, manifest)
