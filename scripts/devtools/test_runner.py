"""Regression tests for exit codes, logs, timeouts and offline setup failures."""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "aegis_dev", Path(__file__).parents[1] / "dev.py"
)
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_child(self, code, timeout=10):
        return dev.run_logged(
            [sys.executable, "-c", code],
            self.root,
            self.root / "child.log",
            dict(os.environ),
            timeout,
        )

    def test_stderr_does_not_turn_success_into_failure(self):
        result = self.run_child("import sys; print('256 tests OK', file=sys.stderr)")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("256 tests OK", (self.root / "child.log").read_text())

    def test_failure_preserves_actual_code_and_full_output(self):
        result = self.run_child(
            "import sys; print('first detail'); print('last detail',file=sys.stderr); sys.exit(7)"
        )
        self.assertEqual(result["exit_code"], 7)
        log = (self.root / "child.log").read_text()
        self.assertIn("first detail", log)
        self.assertIn("last detail", log)

    def test_timeout_is_reported(self):
        result = self.run_child("import time; time.sleep(5)", timeout=0.05)
        self.assertEqual(result["exit_code"], 124)
        self.assertIn("timed out", (self.root / "child.log").read_text())

    def test_missing_executable_is_setup_failure(self):
        result = dev.run_logged(
            [str(self.root / "missing-executable")],
            self.root,
            self.root / "missing.log",
            dict(os.environ),
            5,
        )
        self.assertEqual(result["exit_code"], 127)

    def test_main_propagates_failure_and_writes_json(self):
        with (
            patch.object(dev, "new_report_dir", return_value=self.root),
            patch.object(dev, "discover", return_value={}),
            patch.object(
                dev,
                "suite_command",
                return_value=([sys.executable, "-c", "raise SystemExit(7)"], self.root),
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = dev.main(["test", "--suite", "tooling"])
        self.assertEqual(code, 7)
        report = json.loads((self.root / "summary.json").read_text())
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["exit_code"], 7)

    def test_credential_values_are_not_inherited(self):
        env = dev.child_env(
            {
                "PATH": "runtime",
                "OKX_SECRET": "secret",
                "EVREN_LLM_API_KEY": "secret",
                "AEGIS_API_KEY": "secret",
                "OPENAI_API_KEY": "secret",
            }
        )
        self.assertEqual(env, {"PATH": "runtime"})

    def test_ml_target_does_not_require_module_import_path(self):
        command, cwd = dev.suite_command(
            "ml", {"ml_python": sys.executable}, self.root, ["test_dataset.py"]
        )
        self.assertEqual(command[-3:], ["-p", "test_dataset.py", "-q"])
        self.assertEqual(cwd, self.root)

    def test_missing_runtime_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "runtime is missing"):
            dev.suite_command("backend", {}, self.root)

    def test_missing_vitest_does_not_trigger_install(self):
        with self.assertRaisesRegex(ValueError, "Vitest is missing"):
            dev.suite_command("frontend", {"node": "node"}, self.root)

    def test_integrity_reports_changed_bytes_without_rewriting(self):
        (self.root / ".gitattributes").write_text(
            "sample.txt text eol=lf\n", encoding="utf-8"
        )
        sample = self.root / "sample.txt"
        sample.write_bytes(b"changed\r\n")
        result = type("Result", (), {"returncode": 0, "stdout": b"committed\n"})()
        with (
            patch.object(dev, "discover", return_value={"git": "git"}),
            patch.object(dev.subprocess, "run", return_value=result),
        ):
            report = dev.integrity(self.root, {"PATH": ""})
        self.assertFalse(report["ok"])
        self.assertEqual(report["checked"], 1)
        self.assertEqual(sample.read_bytes(), b"changed\r\n")


if __name__ == "__main__":
    unittest.main()
