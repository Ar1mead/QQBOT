import ctypes
import unittest

from adapters.worker_backends.windows_environment import (
    MAX_ENVIRONMENT_CHARACTERS,
    build_worker_environment,
)


class WorkerEnvironmentTests(unittest.TestCase):
    def valid_values(self):
        return {
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
            "LOCALAPPDATA": r"C:\WorkerLocalAppData",
            "TEMP": r"C:\WorkerTemp",
            "TMP": r"C:\WorkerTemp",
            "PATH": r"C:\PythonRuntime",
            "PYTHONHOME": r"C:\PythonRuntime",
        }

    def test_builds_sorted_double_nul_terminated_environment(self):
        env = build_worker_environment(self.valid_values())
        self.assertTrue(env.block_text.endswith("\x00\x00"))
        self.assertEqual(env.block_text.count("="), len(env.values))
        keys = [key for key, _ in env.values]
        self.assertEqual(keys, sorted(keys, key=str.casefold))
        mapping = dict(env.values)
        self.assertEqual(mapping["PYTHONNOUSERSITE"], "1")
        self.assertEqual(mapping["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(mapping["PYTHONSAFEPATH"], "1")
        self.assertEqual(
            ctypes.sizeof(env.buffer) // ctypes.sizeof(ctypes.c_wchar),
            len(env.block_text),
        )

    def test_rejects_unknown_parent_environment_keys(self):
        values = self.valid_values()
        values["AWS_SECRET_ACCESS_KEY"] = "secret"
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            build_worker_environment(values)

    def test_rejects_case_duplicate_and_invalid_names(self):
        values = self.valid_values()
        values["systemroot"] = r"C:\Windows"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_worker_environment(values)
        for key in ("=C:", "BAD=NAME", "BAD\x00NAME"):
            with self.subTest(key=key):
                values = self.valid_values()
                values[key] = "x"
                with self.assertRaises(ValueError):
                    build_worker_environment(values)

    def test_rejects_missing_or_nonabsolute_required_paths(self):
        values = self.valid_values()
        del values["TMP"]
        with self.assertRaisesRegex(ValueError, "missing required"):
            build_worker_environment(values)
        values = self.valid_values()
        values["TEMP"] = "relative"
        with self.assertRaisesRegex(ValueError, "absolute Windows path"):
            build_worker_environment(values)
        values = self.valid_values()
        values["LOCALAPPDATA"] = "relative"
        with self.assertRaisesRegex(ValueError, "LOCALAPPDATA"):
            build_worker_environment(values)

    def test_rejects_nul_values_and_bad_python_flags(self):
        values = self.valid_values()
        values["PATH"] = "C:\\Python\x00Runtime"
        with self.assertRaisesRegex(ValueError, "NUL-free"):
            build_worker_environment(values)
        values = self.valid_values()
        values["PYTHONSAFEPATH"] = "0"
        with self.assertRaisesRegex(ValueError, "exactly 1"):
            build_worker_environment(values)

    def test_rejects_oversized_environment(self):
        values = self.valid_values()
        values["PATH"] = r"C:\\" + "x" * MAX_ENVIRONMENT_CHARACTERS
        with self.assertRaisesRegex(ValueError, "exceeds"):
            build_worker_environment(values)


if __name__ == "__main__":
    unittest.main()
