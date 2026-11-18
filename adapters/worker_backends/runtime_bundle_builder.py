"""Deterministic builder for the pinned, offline SurfCore QQ Worker bundle.

Run on Windows with a trusted CPython 3.12 runtime:
    python -m adapters.worker_backends.runtime_bundle_builder
        --python-runtime-root C:\\Python312
        --output-root E:\\QQBOT\\worker-bundle

The CLI probes the runtime executable itself. The resulting manifest SHA-256
must be provisioned separately into trusted host configuration.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

from .runtime_bundle import (
    MANIFEST_FILENAME,
    RuntimeBundleError,
    load_runtime_bundle,
)


BUNDLE_ID = "qqbot-worker-cpython312-surfcore-qq-v1"
ADAPTER_BINDINGS = [{
    "adapter_id": "surfcore.qq.readonly",
    "adapter_version": "0.1.0",
    "operation": "observe_batch",
    "dispatch_key": "surfcore_qq_batch",
}]
WORKER_SOURCE_FILES = (
    "adapters/contracts/observation.py",
    "adapters/platforms/surfcore/__init__.py",
    "adapters/platforms/surfcore/mapping.py",
    "adapters/platforms/surfcore/worker_result.py",
    "adapters/worker_protocol.py",
)
OPTIONAL_PACKAGE_FILES = (
    "adapters/__init__.py",
    "adapters/contracts/__init__.py",
    "adapters/platforms/__init__.py",
)
WORKER_ENTRYPOINT_SOURCE = "adapters/worker_entrypoint.py"
RUNTIME_REQUIRED_FILES = ("python.exe", "python312.dll")
RUNTIME_REQUIRED_DIRS = ("DLLs", "Lib")
RUNTIME_ROOT_OPTIONAL_FILES = ("python312.zip", "python312._pth")
_EXCLUDED_DIRS = frozenset({"__pycache__", "site-packages", "test", "tests"})
_EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})
_PYTHON_VERSION_RE = re.compile(r"3\.12\.[0-9]+\\Z")


class RuntimeBundleBuildError(RuntimeError):
    """Raised when the reviewed runtime/package inputs cannot be built safely."""


@dataclass(frozen=True)
class RuntimeBundleBuildResult:
    output_root: str
    bundle_id: str
    python_version: str
    manifest_sha256: str
    file_count: int
    total_bytes: int


def _is_reparse_or_symlink(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x0400
    )


def _checked_regular_file(root: str, relative: str) -> str:
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or parsed.as_posix() != relative or any(
        part in {"", ".", ".."} for part in relative.split("/")
    ):
        raise RuntimeBundleBuildError("package source path is not canonical")
    current = root
    for index, part in enumerate(relative.split("/")):
        current = os.path.join(current, part)
        try:
            info = os.lstat(current)
        except OSError as exc:
            raise RuntimeBundleBuildError(f"required package file is missing: {relative}") from exc
        if _is_reparse_or_symlink(info):
            raise RuntimeBundleBuildError(f"package source contains a link/reparse point: {relative}")
        if index < len(relative.split("/")) - 1 and not stat.S_ISDIR(info.st_mode):
            raise RuntimeBundleBuildError(f"package source parent is not a directory: {relative}")
        if index == len(relative.split("/")) - 1 and not stat.S_ISREG(info.st_mode):
            raise RuntimeBundleBuildError(f"package source is not a regular file: {relative}")
    return current


def _copy_file(source: str, destination: str) -> tuple[int, str]:
    before = os.lstat(source)
    if _is_reparse_or_symlink(before) or not stat.S_ISREG(before.st_mode):
        raise RuntimeBundleBuildError(f"refusing non-regular package source: {source}")
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with open(source, "rb") as src, open(destination, "xb") as dst:
            opened = os.fstat(src.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev, before.st_ino, before.st_size
            ):
                raise RuntimeBundleBuildError("package source changed before copy")
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            dst.flush()
            os.fsync(dst.fileno())
            after = os.fstat(src.fileno())
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
                opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns
            ):
                raise RuntimeBundleBuildError("package source changed during copy")
    except RuntimeBundleBuildError:
        raise
    except OSError as exc:
        raise RuntimeBundleBuildError(f"cannot copy package source: {source}") from exc
    return size, digest.hexdigest()


def _runtime_files(runtime_root: str) -> list[tuple[str, str]]:
    for name in RUNTIME_REQUIRED_FILES:
        _checked_regular_file(runtime_root, name)
    for name in RUNTIME_REQUIRED_DIRS:
        path = os.path.join(runtime_root, name)
        info = os.lstat(path)
        if _is_reparse_or_symlink(info) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeBundleBuildError(f"Python runtime directory is invalid: {name}")

    selected: dict[str, str] = {}
    for name in RUNTIME_REQUIRED_FILES:
        selected[name] = os.path.join(runtime_root, name)
    for name in os.listdir(runtime_root):
        if name.casefold().endswith(".dll"):
            selected[name] = _checked_regular_file(runtime_root, name)
    for name in RUNTIME_ROOT_OPTIONAL_FILES:
        path = os.path.join(runtime_root, name)
        if os.path.lexists(path):
            selected[name] = _checked_regular_file(runtime_root, name)

    for directory in RUNTIME_REQUIRED_DIRS:
        base = os.path.join(runtime_root, directory)
        for current, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
            kept = []
            for dirname in sorted(dirnames):
                path = os.path.join(current, dirname)
                info = os.lstat(path)
                if _is_reparse_or_symlink(info) or not stat.S_ISDIR(info.st_mode):
                    raise RuntimeBundleBuildError("Python runtime tree contains a link/reparse point")
                if dirname.casefold() not in _EXCLUDED_DIRS:
                    kept.append(dirname)
            dirnames[:] = kept
            for filename in sorted(filenames):
                if Path(filename).suffix.casefold() in _EXCLUDED_SUFFIXES:
                    continue
                path = os.path.join(current, filename)
                info = os.lstat(path)
                if _is_reparse_or_symlink(info) or not stat.S_ISREG(info.st_mode):
                    raise RuntimeBundleBuildError("Python runtime tree contains a non-regular file")
                relative = os.path.relpath(path, runtime_root).replace(os.sep, "/")
                selected[relative] = path

    if "python312._pth" in selected:
        pth_text = Path(selected["python312._pth"]).read_text(encoding="utf-8")
        for raw_line in pth_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in {"python312.zip", ".", "Lib", "DLLs"}:
                raise RuntimeBundleBuildError("python312._pth contains an unapproved path or directive")
        if "python312.zip" in pth_text and "python312.zip" not in selected:
            raise RuntimeBundleBuildError("python312._pth requires python312.zip but it is missing")

    return sorted(selected.items())


def _worker_source_files(repository_root: str) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    required = list(WORKER_SOURCE_FILES) + [WORKER_ENTRYPOINT_SOURCE]
    for relative in required:
        source = _checked_regular_file(repository_root, relative)
        target = (
            "app/worker_entrypoint.py"
            if relative == WORKER_ENTRYPOINT_SOURCE
            else "app/" + relative
        )
        selected.append((target, source))
    for relative in OPTIONAL_PACKAGE_FILES:
        path = os.path.join(repository_root, *relative.split("/"))
        if os.path.lexists(path):
            selected.append(("app/" + relative, _checked_regular_file(repository_root, relative)))
    return selected


def probe_python_runtime(runtime_root: str) -> str:
    """Execute the supplied interpreter in isolated mode and return CPython 3.12.x."""
    executable = _checked_regular_file(runtime_root, "python.exe")
    probe = (
        "import json,sys; "
        "print(json.dumps({'implementation':sys.implementation.name,"
        "'version':'.'.join(str(x) for x in sys.version_info[:3])}))"
    )
    try:
        completed = subprocess.run(
            [executable, "-I", "-S", "-B", "-c", probe],
            cwd=runtime_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeBundleBuildError("could not execute the supplied Python runtime") from exc
    if completed.returncode != 0:
        raise RuntimeBundleBuildError("Python runtime probe failed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeBundleBuildError("Python runtime probe returned invalid metadata") from exc
    if result.get("implementation") != "cpython":
        raise RuntimeBundleBuildError("worker runtime must be CPython")
    version = result.get("version")
    if not isinstance(version, str) or not _PYTHON_VERSION_RE.fullmatch(version):
        raise RuntimeBundleBuildError("worker runtime must be CPython 3.12.x")
    return version


def build_worker_runtime_bundle(
    *,
    repository_root: str,
    python_runtime_root: str,
    output_root: str,
    python_version: str,
) -> RuntimeBundleBuildResult:
    """Build the exact offline Worker package and write a canonical manifest."""
    if not isinstance(python_version, str) or not _PYTHON_VERSION_RE.fullmatch(python_version):
        raise ValueError("python_version must be a CPython 3.12.x version")
    repository_root = os.path.abspath(repository_root)
    python_runtime_root = os.path.abspath(python_runtime_root)
    output_root = os.path.abspath(output_root)
    for root in (repository_root, python_runtime_root):
        info = os.lstat(root)
        if _is_reparse_or_symlink(info) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeBundleBuildError("source roots must be real directories")
        try:
            common = os.path.commonpath((root, output_root))
        except ValueError:
            common = None
        if common in {root, output_root}:
            raise RuntimeBundleBuildError("output must be separate from repository and Python source roots")
    parent = os.path.dirname(output_root)
    parent_info = os.lstat(parent)
    if _is_reparse_or_symlink(parent_info) or not stat.S_ISDIR(parent_info.st_mode):
        raise RuntimeBundleBuildError("output parent must be a real directory")
    if os.path.lexists(output_root):
        raise RuntimeBundleBuildError("output directory must not already exist")

    runtime_sources = _runtime_files(python_runtime_root)
    worker_sources = _worker_source_files(repository_root)
    all_sources = [
        ("python/" + relative.replace(os.sep, "/"), source)
        for relative, source in runtime_sources
    ] + worker_sources
    target_paths = [target for target, _ in all_sources]
    if len(target_paths) != len(set(target_paths)):
        raise RuntimeBundleBuildError("runtime bundle contains duplicate target paths")

    try:
        os.mkdir(output_root, 0o700)
        file_entries: list[dict[str, Any]] = []
        total_bytes = 0
        for target_relative, source in sorted(all_sources):
            destination = os.path.join(output_root, *target_relative.split("/"))
            size, digest = _copy_file(source, destination)
            total_bytes += size
            file_entries.append({"path": target_relative, "size": size, "sha256": digest})

        manifest = {
            "schema_version": 1,
            "bundle_id": BUNDLE_ID,
            "python_implementation": "CPython",
            "python_version": python_version,
            "interpreter_path": "python/python.exe",
            "entrypoint_path": "app/worker_entrypoint.py",
            "files": file_entries,
            "adapters": ADAPTER_BINDINGS,
        }
        manifest_bytes = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        manifest_path = os.path.join(output_root, MANIFEST_FILENAME)
        with open(manifest_path, "xb") as stream:
            stream.write(manifest_bytes)
            stream.flush()
            os.fsync(stream.fileno())

        verified = load_runtime_bundle(output_root)
        return RuntimeBundleBuildResult(
            output_root=output_root,
            bundle_id=verified.manifest.bundle_id,
            python_version=verified.manifest.python_version,
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            file_count=len(verified.manifest.files),
            total_bytes=verified.manifest.total_bytes,
        )
    except Exception as exc:
        try:
            if os.path.lexists(output_root):
                shutil.rmtree(output_root)
        except Exception as cleanup_error:
            raise RuntimeBundleBuildError(
                f"bundle build failed and output cleanup failed: {cleanup_error}"
            ) from exc
        if isinstance(exc, (RuntimeBundleBuildError, RuntimeBundleError, ValueError)):
            raise
        raise RuntimeBundleBuildError(f"bundle build failed: {type(exc).__name__}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the pinned offline SurfCore QQ Worker runtime bundle")
    parser.add_argument("--repository-root", default=os.getcwd())
    parser.add_argument("--python-runtime-root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    version = probe_python_runtime(args.python_runtime_root)
    result = build_worker_runtime_bundle(
        repository_root=args.repository_root,
        python_runtime_root=args.python_runtime_root,
        output_root=args.output_root,
        python_version=version,
    )
    print(json.dumps({
        "bundle_id": result.bundle_id,
        "python_version": result.python_version,
        "manifest_sha256": result.manifest_sha256,
        "file_count": result.file_count,
        "total_bytes": result.total_bytes,
        "output_root": result.output_root,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
