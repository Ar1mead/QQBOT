import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from adapters.worker_backends.runtime_bundle import (
    MANIFEST_FILENAME,
    RuntimeBundleError,
    load_runtime_bundle,
    parse_runtime_bundle_manifest,
    verify_runtime_bundle,
)


class RuntimeBundleManifestTests(unittest.TestCase):
    def make_manifest(self, files=None, adapters=None, **changes):
        file_bytes = {
            "app/worker_entrypoint.py": b"print('worker')\n",
            "python/python.exe": b"fake-python-runtime",
        }
        if files is not None:
            file_bytes = files
        file_entries = [
            {"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for path, data in sorted(file_bytes.items())
        ]
        value = {
            "schema_version": 1,
            "bundle_id": "qqbot-worker-test",
            "python_implementation": "CPython",
            "python_version": "3.12.16",
            "interpreter_path": "python/python.exe",
            "entrypoint_path": "app/worker_entrypoint.py",
            "files": file_entries,
            "adapters": adapters or [{
                "adapter_id": "surfcore.qq.readonly",
                "adapter_version": "0.1.0",
                "operation": "observe_batch",
                "dispatch_key": "surfcore_qq_batch",
            }],
        }
        value.update(changes)
        return value, file_bytes

    def write_bundle(self, root, value, file_bytes):
        for path, data in file_bytes.items():
            target = Path(root, *path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        Path(root, MANIFEST_FILENAME).write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def test_parse_accepts_exact_sorted_manifest_and_pins_adapter_dispatch(self):
        value, _ = self.make_manifest()
        manifest = parse_runtime_bundle_manifest(json.dumps(value))
        self.assertEqual(manifest.bundle_id, "qqbot-worker-test")
        self.assertEqual(manifest.python_version, "3.12.16")
        self.assertEqual(manifest.total_bytes, sum(item["size"] for item in value["files"]))
        self.assertEqual(manifest.adapters[0].dispatch_key, "surfcore_qq_batch")

    def test_parse_rejects_unknown_fields_and_duplicate_json_keys(self):
        value, _ = self.make_manifest()
        value["arbitrary_command"] = "whoami"
        with self.assertRaisesRegex(RuntimeBundleError, "exact schema"):
            parse_runtime_bundle_manifest(json.dumps(value))
        with self.assertRaisesRegex(RuntimeBundleError, "duplicate JSON key"):
            parse_runtime_bundle_manifest('{"schema_version":1,"schema_version":1}')

    def test_parse_rejects_noncanonical_or_escaping_paths(self):
        for path in ("../outside.py", "/absolute.py", "C:/outside.py", "app\\worker.py", "app//worker.py", "./worker.py"):
            value, _ = self.make_manifest()
            value["files"][0]["path"] = path
            with self.subTest(path=path):
                with self.assertRaises(RuntimeBundleError):
                    parse_runtime_bundle_manifest(json.dumps(value))

    def test_parse_rejects_unsorted_duplicate_or_unlisted_entrypoint(self):
        value, _ = self.make_manifest()
        value["files"].reverse()
        with self.assertRaisesRegex(RuntimeBundleError, "sorted"):
            parse_runtime_bundle_manifest(json.dumps(value))
        value, _ = self.make_manifest()
        value["files"][1]["path"] = value["files"][0]["path"]
        with self.assertRaisesRegex(RuntimeBundleError, "sorted"):
            parse_runtime_bundle_manifest(json.dumps(value))
        value, _ = self.make_manifest()
        value["entrypoint_path"] = "app/missing.py"
        with self.assertRaisesRegex(RuntimeBundleError, "must be listed"):
            parse_runtime_bundle_manifest(json.dumps(value))

    def test_parse_rejects_invalid_dispatch_key_or_duplicate_dispatch_key(self):
        value, _ = self.make_manifest(adapters=[{
            "adapter_id": "a", "adapter_version": "1", "operation": "observe",
            "dispatch_key": "adapters.module:run",
        }])
        with self.assertRaisesRegex(RuntimeBundleError, "dispatch_key"):
            parse_runtime_bundle_manifest(json.dumps(value))
        value, _ = self.make_manifest(adapters=[
            {"adapter_id": "a", "adapter_version": "1", "operation": "one", "dispatch_key": "fixed_one"},
            {"adapter_id": "a", "adapter_version": "1", "operation": "two", "dispatch_key": "fixed_one"},
        ])
        with self.assertRaisesRegex(RuntimeBundleError, "unique"):
            parse_runtime_bundle_manifest(json.dumps(value))

    def test_parse_rejects_bad_size_digest_and_oversized_bundle(self):
        value, _ = self.make_manifest()
        value["files"][0]["size"] = True
        with self.assertRaises(RuntimeBundleError):
            parse_runtime_bundle_manifest(json.dumps(value))
        value, _ = self.make_manifest()
        value["files"][0]["sha256"] = "A" * 64
        with self.assertRaises(RuntimeBundleError):
            parse_runtime_bundle_manifest(json.dumps(value))
        value, _ = self.make_manifest()
        value["files"][0]["size"] = 256 * 1024 * 1024 + 1
        with self.assertRaisesRegex(RuntimeBundleError, "size"):
            parse_runtime_bundle_manifest(json.dumps(value))

    def test_verify_checks_exact_file_set_size_and_digest(self):
        value, file_bytes = self.make_manifest()
        with tempfile.TemporaryDirectory() as root:
            self.write_bundle(root, value, file_bytes)
            verified = load_runtime_bundle(root)
            self.assertEqual(verified.manifest.bundle_id, "qqbot-worker-test")
            Path(root, "unlisted.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeBundleError, "file set mismatch"):
                load_runtime_bundle(root)

    def test_verify_rejects_digest_and_size_mismatch(self):
        value, file_bytes = self.make_manifest()
        with tempfile.TemporaryDirectory() as root:
            self.write_bundle(root, value, file_bytes)
            Path(root, "app", "worker_entrypoint.py").write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeBundleError, "size mismatch|SHA-256 mismatch"):
                load_runtime_bundle(root)

    def test_verify_rejects_symlinks_and_reparse_points(self):
        value, file_bytes = self.make_manifest()
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            self.write_bundle(root, value, file_bytes)
            external = Path(outside, "external.py")
            external.write_text("external", encoding="utf-8")
            link = Path(root, "app", "external.py")
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this runner")
            with self.assertRaisesRegex(RuntimeBundleError, "symlink or reparse"):
                load_runtime_bundle(root)

    def test_load_rejects_missing_or_oversized_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(RuntimeBundleError):
                load_runtime_bundle(root)
            Path(root, MANIFEST_FILENAME).write_bytes(b" " * (1024 * 1024 + 1))
            with self.assertRaisesRegex(RuntimeBundleError, "size limit"):
                load_runtime_bundle(root)


if __name__ == "__main__":
    unittest.main()
