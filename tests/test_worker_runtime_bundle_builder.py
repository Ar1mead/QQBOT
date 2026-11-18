import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from adapters.worker_backends.runtime_bundle import (
    MANIFEST_FILENAME,
    load_runtime_bundle,
    load_trusted_runtime_bundle,
)
from adapters.worker_backends.runtime_bundle_builder import (
    RuntimeBundleBuildError,
    WORKER_ENTRYPOINT_SOURCE,
    WORKER_SOURCE_FILES,
    build_worker_runtime_bundle,
)


class RuntimeBundleBuilderTests(unittest.TestCase):
    def make_inputs(self, root):
        repository = Path(root, "repository")
        runtime = Path(root, "python-runtime")
        repository.mkdir()
        runtime.mkdir()

        for relative in (*WORKER_SOURCE_FILES, WORKER_ENTRYPOINT_SOURCE):
            target = Path(repository, *relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# reviewed worker source: " + relative + "\n", encoding="utf-8")
        # These files are deliberately not in the fixed Worker dependency closure.
        Path(repository, "core").mkdir()
        Path(repository, "core", "secret_module.py").write_text("SHOULD_NOT_BE_PACKAGED", encoding="utf-8")

        Path(runtime, "python.exe").write_bytes(b"fake-cpython-executable")
        Path(runtime, "python312.dll").write_bytes(b"fake-cpython-runtime")
        Path(runtime, "python312.zip").write_bytes(b"fake-stdlib-zip")
        Path(runtime, "python312._pth").write_text("python312.zip\n.\n", encoding="utf-8")
        Path(runtime, "DLLs").mkdir()
        Path(runtime, "DLLs", "_ssl.pyd").write_bytes(b"native-extension")
        Path(runtime, "Lib").mkdir()
        Path(runtime, "Lib", "json").mkdir()
        Path(runtime, "Lib", "json", "__init__.py").write_text("# stdlib fixture\n", encoding="utf-8")
        Path(runtime, "Lib", "site-packages").mkdir()
        Path(runtime, "Lib", "site-packages", "untrusted.py").write_text("bad", encoding="utf-8")
        Path(runtime, "Lib", "test").mkdir()
        Path(runtime, "Lib", "test", "test_bad.py").write_text("bad", encoding="utf-8")
        Path(runtime, "Lib", "__pycache__").mkdir()
        Path(runtime, "Lib", "__pycache__", "bad.pyc").write_bytes(b"bad")
        return repository, runtime

    def test_builds_deterministic_fixed_package_and_host_pin(self):
        with tempfile.TemporaryDirectory() as root:
            repository, runtime = self.make_inputs(root)
            first = build_worker_runtime_bundle(
                repository_root=str(repository),
                python_runtime_root=str(runtime),
                output_root=str(Path(root, "bundle-one")),
                python_version="3.12.16",
            )
            second = build_worker_runtime_bundle(
                repository_root=str(repository),
                python_runtime_root=str(runtime),
                output_root=str(Path(root, "bundle-two")),
                python_version="3.12.16",
            )
            self.assertEqual(first.manifest_sha256, second.manifest_sha256)
            self.assertEqual(
                Path(first.output_root, MANIFEST_FILENAME).read_bytes(),
                Path(second.output_root, MANIFEST_FILENAME).read_bytes(),
            )
            verified = load_runtime_bundle(first.output_root)
            paths = {entry.path for entry in verified.manifest.files}
            self.assertIn("app/worker_entrypoint.py", paths)
            self.assertIn("app/adapters/platforms/surfcore/mapping.py", paths)
            self.assertIn("python/python.exe", paths)
            self.assertIn("python/python312.dll", paths)
            self.assertIn("python/DLLs/_ssl.pyd", paths)
            self.assertIn("python/Lib/json/__init__.py", paths)
            pth = Path(first.output_root, "python", "python312._pth").read_text(encoding="utf-8")
            self.assertEqual(pth.splitlines(), ["python312.zip", ".", "DLLs", "Lib"])
            self.assertNotIn("python/Lib/site-packages/untrusted.py", paths)
            self.assertNotIn("python/Lib/test/test_bad.py", paths)
            self.assertFalse(any(path.startswith("core/") or "/core/" in path for path in paths))
            pinned = load_trusted_runtime_bundle(
                first.output_root,
                expected_manifest_sha256=first.manifest_sha256,
            )
            self.assertEqual(pinned.manifest_sha256, first.manifest_sha256)

    def test_rejects_non_312_python_version_and_output_inside_source(self):
        with tempfile.TemporaryDirectory() as root:
            repository, runtime = self.make_inputs(root)
            with self.assertRaisesRegex(ValueError, "CPython 3.12"):
                build_worker_runtime_bundle(
                    repository_root=str(repository),
                    python_runtime_root=str(runtime),
                    output_root=str(Path(root, "bad-version")),
                    python_version="3.13.0",
                )
            with self.assertRaisesRegex(RuntimeBundleBuildError, "separate"):
                build_worker_runtime_bundle(
                    repository_root=str(repository),
                    python_runtime_root=str(runtime),
                    output_root=str(Path(repository, "inside")),
                    python_version="3.12.16",
                )

    def test_rejects_unapproved_python_pth_directive(self):
        with tempfile.TemporaryDirectory() as root:
            repository, runtime = self.make_inputs(root)
            Path(runtime, "python312._pth").write_text("python312.zip\nimport site\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeBundleBuildError, "unapproved"):
                build_worker_runtime_bundle(
                    repository_root=str(repository),
                    python_runtime_root=str(runtime),
                    output_root=str(Path(root, "bad-pth")),
                    python_version="3.12.16",
                )

    def test_rejects_symlinked_runtime_file(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            repository, runtime = self.make_inputs(root)
            external = Path(outside, "python.exe")
            external.write_bytes(b"outside")
            Path(runtime, "python.exe").unlink()
            try:
                Path(runtime, "python.exe").symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is not permitted on this runner")
            with self.assertRaisesRegex(RuntimeBundleBuildError, "link/reparse|link"):
                build_worker_runtime_bundle(
                    repository_root=str(repository),
                    python_runtime_root=str(runtime),
                    output_root=str(Path(root, "bad-link")),
                    python_version="3.12.16",
                )


if __name__ == "__main__":
    unittest.main()
