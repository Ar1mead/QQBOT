"""Bounded verification and per-invocation staging for worker runtime bundles.

The bundle root must be owned and protected by the trusted host. This module
verifies the exact manifest-listed file set, stages only those files into a
fresh per-invocation runtime tree, and verifies the staged bytes. It does not
apply AppContainer ACLs or launch a process.
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


@dataclass(frozen=True)
class TrustedRuntimeBundle:
    """A verified bundle whose exact manifest bytes match a host-owned digest pin."""

    verified_bundle: VerifiedRuntimeBundle
    manifest_sha256: str


@dataclass(frozen=True)
class StagedRuntimeBundle:
    """Per-invocation copy of a bundle; trust pin and ACL hardening remain explicit."""

    root_path: str
    interpreter_path: str
    entrypoint_path: str
    manifest: RuntimeBundleManifest
    trusted_manifest_sha256: str | None = None


def _hash_regular_file(path: str, expected_size: int, expected_digest: str) -> None:
    before = _safe_lstat(path, directory=False)
    if before.st_size != expected_size:
        raise RuntimeBundleError(f"staged runtime file size mismatch: {path}")
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev, opened.st_ino, opened.st_size
            ) != (before.st_dev, before.st_ino, before.st_size):
                raise RuntimeBundleError(f"staged runtime file changed during open: {path}")
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            after = os.fstat(stream.fileno())
    except RuntimeBundleError:
        raise
    except OSError as exc:
        raise RuntimeBundleError(f"cannot read staged runtime file: {path}") from exc
    if (
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
    ):
        raise RuntimeBundleError(f"staged runtime file changed while hashing: {path}")
    if digest.hexdigest() != expected_digest:
        raise RuntimeBundleError(f"staged runtime SHA-256 mismatch: {path}")


def _copy_verified_file(source: str, destination: str, entry: RuntimeBundleFile) -> None:
    before = _safe_lstat(source, directory=False)
    if before.st_size != entry.size:
        raise RuntimeBundleError(f"source runtime file size changed: {entry.path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(source, flags)
    except OSError as exc:
        raise RuntimeBundleError(f"cannot open source runtime file: {entry.path}") from exc
    destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    destination_fd = None
    digest = hashlib.sha256()
    copied = 0
    try:
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or (
            opened.st_dev, opened.st_ino, opened.st_size
        ) != (before.st_dev, before.st_ino, before.st_size):
            raise RuntimeBundleError(f"source runtime file changed during open: {entry.path}")
        destination_fd = os.open(destination, destination_flags, 0o600)
        with os.fdopen(source_fd, "rb", closefd=True) as source_stream:
            source_fd = -1
            with os.fdopen(destination_fd, "wb", closefd=True) as destination_stream:
                destination_fd = None
                while True:
                    chunk = source_stream.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > entry.size:
                        raise RuntimeBundleError(f"source runtime file grew during copy: {entry.path}")
                    digest.update(chunk)
                    destination_stream.write(chunk)
                destination_stream.flush()
                os.fsync(destination_stream.fileno())
            after = os.fstat(source_stream.fileno())
        current = _safe_lstat(source, directory=False)
        if (
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
            or (current.st_dev, current.st_ino, current.st_size)
            != (opened.st_dev, opened.st_ino, opened.st_size)
        ):
            raise RuntimeBundleError(f"source runtime file changed during copy: {entry.path}")
        if copied != entry.size or digest.hexdigest() != entry.sha256:
            raise RuntimeBundleError(f"source runtime file digest mismatch during copy: {entry.path}")
        _hash_regular_file(destination, entry.size, entry.sha256)
    except RuntimeBundleError:
        raise
    except OSError as exc:
        raise RuntimeBundleError(f"failed to stage runtime file: {entry.path}") from exc
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)


def _remove_tree_no_follow(path: str) -> None:
    info = _safe_lstat(path)
    if stat.S_ISDIR(info.st_mode):
        for entry in os.scandir(path):
            child_info = _safe_lstat(entry.path)
            if stat.S_ISDIR(child_info.st_mode):
                _remove_tree_no_follow(entry.path)
            elif stat.S_ISREG(child_info.st_mode):
                os.unlink(entry.path)
            else:
                raise RuntimeBundleError(f"refusing to remove unexpected staged object: {entry.path}")
        os.rmdir(path)
    elif stat.S_ISREG(info.st_mode):
        os.unlink(path)
    else:
        raise RuntimeBundleError(f"refusing to remove unexpected staged object: {path}")


def stage_runtime_bundle(
    bundle: VerifiedRuntimeBundle | TrustedRuntimeBundle,
    destination_root: str,
) -> StagedRuntimeBundle:
    """Copy only manifest-listed files into a newly created per-run directory.

    Source bytes are re-hashed while copying, destination files are created
    exclusively, and every staged file is read back and verified. The returned
    tree is not launchable until the caller applies and verifies AppContainer
    read/execute ACLs and Low Integrity scratch policy separately.
    """
    if isinstance(bundle, TrustedRuntimeBundle):
        verified = bundle.verified_bundle
        trusted_manifest_sha256 = bundle.manifest_sha256
        if not _SHA256_RE.fullmatch(trusted_manifest_sha256):
            raise RuntimeBundleError("trusted bundle manifest pin is invalid")
    elif isinstance(bundle, VerifiedRuntimeBundle):
        verified = bundle
        trusted_manifest_sha256 = None
    else:
        raise TypeError("bundle must be a VerifiedRuntimeBundle or TrustedRuntimeBundle")
    if not isinstance(destination_root, str) or not destination_root:
        raise ValueError("destination_root must be a non-empty path")
    source_root = os.path.abspath(verified.root_path)
    destination = os.path.abspath(destination_root)
    try:
        common = os.path.commonpath((source_root, destination))
    except ValueError as exc:
        raise RuntimeBundleError("source and destination must be on the same filesystem volume") from exc
    if common in {source_root, destination}:
        raise RuntimeBundleError("staging destination must be outside and separate from the source bundle")
    parent = os.path.dirname(destination)
    _safe_lstat(parent, directory=True)
    if os.path.lexists(destination):
        raise RuntimeBundleError("staging destination must not already exist")

    # Revalidate the source at staging time, then verify every source file again
    # while copying to close the gap between initial verification and use.
    verify_runtime_bundle(source_root, verified.manifest)
    try:
        os.mkdir(destination, 0o700)
        _safe_lstat(destination, directory=True)
        for entry in verified.manifest.files:
            parts = entry.path.split("/")
            current = destination
            for component in parts[:-1]:
                current = os.path.join(current, component)
                if not os.path.exists(current):
                    os.mkdir(current, 0o700)
                _safe_lstat(current, directory=True)
            source = os.path.join(source_root, *parts)
            target = os.path.join(destination, *parts)
            _copy_verified_file(source, target, entry)

        staged_files = _walk_bundle_files(destination)
        expected_files = {entry.path for entry in verified.manifest.files}
        if staged_files != expected_files:
            raise RuntimeBundleError("staged runtime file set does not match the manifest")
        for entry in verified.manifest.files:
            _hash_regular_file(
                os.path.join(destination, *entry.path.split("/")),
                entry.size,
                entry.sha256,
            )
        return StagedRuntimeBundle(
            root_path=destination,
            interpreter_path=os.path.join(destination, *verified.manifest.interpreter_path.split("/")),
            entrypoint_path=os.path.join(destination, *verified.manifest.entrypoint_path.split("/")),
            manifest=verified.manifest,
            trusted_manifest_sha256=trusted_manifest_sha256,
        )
    except Exception as exc:
        try:
            if os.path.lexists(destination):
                _remove_tree_no_follow(destination)
        except Exception as cleanup_error:
            raise RuntimeBundleError(
                f"runtime staging failed and cleanup also failed: {cleanup_error}"
            ) from exc
        if isinstance(exc, RuntimeBundleError):
            raise
        raise RuntimeBundleError(f"runtime bundle staging failed: {type(exc).__name__}") from exc


def verify_staged_runtime(staged: StagedRuntimeBundle) -> StagedRuntimeBundle:
    """Recheck the exact staged file set and every digest immediately before launch."""
    if not isinstance(staged, StagedRuntimeBundle):
        raise TypeError("staged must be a StagedRuntimeBundle")
    root = os.path.abspath(staged.root_path)
    _safe_lstat(root, directory=True)
    expected_files = {entry.path for entry in staged.manifest.files}
    actual_files = _walk_bundle_files(root)
    if actual_files != expected_files:
        raise RuntimeBundleError("staged runtime file set does not match the manifest")
    for entry in staged.manifest.files:
        _hash_regular_file(
            os.path.join(root, *entry.path.split("/")),
            entry.size,
            entry.sha256,
        )
    expected_interpreter = os.path.abspath(
        os.path.join(root, *staged.manifest.interpreter_path.split("/"))
    )
    expected_entrypoint = os.path.abspath(
        os.path.join(root, *staged.manifest.entrypoint_path.split("/"))
    )
    if (
        os.path.abspath(staged.interpreter_path) != expected_interpreter
        or os.path.abspath(staged.entrypoint_path) != expected_entrypoint
    ):
        raise RuntimeBundleError("staged runtime executable metadata does not match the manifest")
    return staged


def cleanup_staged_runtime(staged: StagedRuntimeBundle) -> None:
    """Remove a staged runtime without following links or reparse points."""
    if not isinstance(staged, StagedRuntimeBundle):
        raise TypeError("staged must be a StagedRuntimeBundle")
    _remove_tree_no_follow(staged.root_path)


def _read_runtime_manifest_bytes(root_path: str) -> tuple[str, bytes]:
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
    return absolute_root, raw


def load_runtime_bundle(root_path: str) -> VerifiedRuntimeBundle:
    """Verify manifest/file consistency only; this does not authenticate origin."""
    absolute_root, raw = _read_runtime_manifest_bytes(root_path)
    manifest = parse_runtime_bundle_manifest(raw)
    verified = verify_runtime_bundle(absolute_root, manifest)
    return TrustedRuntimeBundle(
        verified_bundle=verified,
        manifest_sha256=actual_digest,
    )


def load_trusted_runtime_bundle(
    root_path: str,
    *,
    expected_manifest_sha256: str,
) -> TrustedRuntimeBundle:
    """Load a bundle only when its exact manifest bytes match a host-pinned digest.

    The expected digest must come from trusted host configuration, not from the
    bundle itself. This authenticates the manifest identity under that pin; the
    caller must still protect the source bundle root from untrusted writes.
    """
    if not isinstance(expected_manifest_sha256, str) or not _SHA256_RE.fullmatch(
        expected_manifest_sha256
    ):
        raise ValueError("expected_manifest_sha256 must be 64 lowercase hexadecimal characters")
    absolute_root, raw = _read_runtime_manifest_bytes(root_path)
    actual_digest = hashlib.sha256(raw).hexdigest()
    if actual_digest != expected_manifest_sha256:
        raise RuntimeBundleError("runtime bundle manifest does not match the host-pinned SHA-256")
    manifest = parse_runtime_bundle_manifest(raw)
    return verify_runtime_bundle(absolute_root, manifest)
