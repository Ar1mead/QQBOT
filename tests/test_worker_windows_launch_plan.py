import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from adapters.worker_backends.runtime_bundle import (
    MANIFEST_FILENAME,
    RuntimeBundleError,
    StagedRuntimeBundle,
    load_runtime_bundle,
    stage_runtime_bundle,
)
from adapters.worker_backends.windows_launch_plan import (
    PINNED_ENTRYPOINT_PATH,
    PINNED_INTERPRETER_PATH,
    build_windows_worker_launch_plan,
)


class WindowsWorkerLaunchPlanTests(unittest.TestCase):
    def make_staged(self, root):
        source = os.path.join(root, "source")
        destination = os.path.join(root, "staged")
        files = {
            PINNED_ENTRYPOINT_PATH: b"# pinned entrypoint fixture\n",
            PINNED_INTERPRETER_PATH: b"pinned interpreter fixture",
        }
        for relative, content in files.items():
            target = Path(source, *relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        manifest = {
            "schema_version": 1,
            "bundle_id": "windows-launch-plan-fixture",
            "python_implementation": "CPython",
            "python_version": "3.12.16",
            "interpreter_path": PINNED_INTERPRETER_PATH,
            "entrypoint_path": PINNED_ENTRYPOINT_PATH,
            "files": [
                {
                    "path": path,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for path, content in sorted(files.items())
            ],
            "adapters": [{
                "adapter_id": "surfcore.qq.readonly",
                "adapter_version": "0.1.0",
                "operation": "observe_batch",
                "dispatch_key": "surfcore_qq_batch",
            }],
        }
        Path(source, MANIFEST_FILENAME).write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        verified = load_runtime_bundle(source)
        return stage_runtime_bundle(verified, destination)

    def test_builds_exact_host_pinned_command_and_working_directory(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            plan = build_windows_worker_launch_plan(
                staged,
                adapter_id="surfcore.qq.readonly",
                adapter_version="0.1.0",
                operation="observe_batch",
            )
            self.assertEqual(plan.dispatch_key, "surfcore_qq_batch")
            self.assertEqual(plan.application_path, staged.interpreter_path)
            self.assertEqual(plan.arguments, (
                "-I", "-S", "-B", staged.entrypoint_path,
                "--dispatch-key", "surfcore_qq_batch",
            ))
            self.assertEqual(plan.current_directory, os.path.dirname(staged.entrypoint_path))

    def test_rejects_unknown_adapter_version_or_operation(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            for adapter_id, version, operation in (
                ("other.adapter", "0.1.0", "observe_batch"),
                ("surfcore.qq.readonly", "9.9.9", "observe_batch"),
                ("surfcore.qq.readonly", "0.1.0", "arbitrary"),
            ):
                with self.subTest(adapter_id=adapter_id, version=version, operation=operation):
                    with self.assertRaisesRegex(ValueError, "trusted worker allowlist"):
                        build_windows_worker_launch_plan(
                            staged,
                            adapter_id=adapter_id,
                            adapter_version=version,
                            operation=operation,
                        )

    def test_rejects_manifest_dispatch_key_not_in_host_code(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            wrong = staged.manifest.adapters[0]
            from dataclasses import replace
            forged_manifest = replace(
                staged.manifest,
                adapters=(replace(wrong, dispatch_key="other_fixed_key"),),
            )
            forged = replace_staged(staged, manifest=forged_manifest)
            with self.assertRaisesRegex(ValueError, "exactly match"):
                build_windows_worker_launch_plan(
                    forged,
                    adapter_id="surfcore.qq.readonly",
                    adapter_version="0.1.0",
                    operation="observe_batch",
                )

    def test_rejects_python_version_outside_supported_series(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            from dataclasses import replace
            forged = replace_staged(
                staged,
                manifest=replace(staged.manifest, python_version="3.13.0"),
            )
            with self.assertRaisesRegex(ValueError, "supported 3.12"):
                build_windows_worker_launch_plan(
                    forged,
                    adapter_id="surfcore.qq.readonly",
                    adapter_version="0.1.0",
                    operation="observe_batch",
                )

    def test_rejects_symlinked_interpreter_and_metadata_path_escape(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            interpreter = staged.interpreter_path
            os.unlink(interpreter)
            outside = Path(root, "outside-python.exe")
            outside.write_bytes(b"outside")
            try:
                os.symlink(outside, interpreter)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is not permitted on this runner")
            with self.assertRaisesRegex(ValueError, "link or reparse"):
                build_windows_worker_launch_plan(
                    staged,
                    adapter_id="surfcore.qq.readonly",
                    adapter_version="0.1.0",
                    operation="observe_batch",
                )

    def test_rechecks_staged_file_digests_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            Path(staged.entrypoint_path).write_bytes(b"tampered after staging")
            with self.assertRaisesRegex(RuntimeBundleError, "size mismatch|SHA-256 mismatch"):
                build_windows_worker_launch_plan(
                    staged,
                    adapter_id="surfcore.qq.readonly",
                    adapter_version="0.1.0",
                    operation="observe_batch",
                )

    def test_rejects_staged_metadata_that_points_outside_root(self):
        with tempfile.TemporaryDirectory() as root:
            staged = self.make_staged(root)
            forged = replace_staged(
                staged,
                interpreter_path=os.path.join(root, "outside.exe"),
            )
            with self.assertRaisesRegex(ValueError, "metadata"):
                build_windows_worker_launch_plan(
                    forged,
                    adapter_id="surfcore.qq.readonly",
                    adapter_version="0.1.0",
                    operation="observe_batch",
                )


def replace_staged(staged, **changes):
    from dataclasses import replace
    return replace(staged, **changes)


if __name__ == "__main__":
    unittest.main()
