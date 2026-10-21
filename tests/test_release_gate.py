import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_gate", ROOT / "tools/release_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class ReleaseGateTests(unittest.TestCase):
    def results(self):
        return {name: {"result": "success"} for name in gate.REQUIRED_JOBS}

    def test_all_required_dependencies_must_succeed(self):
        self.assertTrue(gate.evaluate(self.results()))
        for result in ("failure", "skipped", "cancelled", "neutral", None, True):
            for name in gate.REQUIRED_JOBS:
                with self.subTest(name=name, result=result):
                    needs = self.results()
                    needs[name]["result"] = result
                    self.assertFalse(gate.evaluate(needs))

    def test_missing_extra_and_malformed_jobs_fail(self):
        needs = self.results()
        del needs["codeql"]
        self.assertFalse(gate.evaluate(needs))
        needs = self.results()
        needs["unexpected"] = {"result": "success"}
        self.assertFalse(gate.evaluate(needs))
        for value in (None, [], {}, True, "success"):
            self.assertFalse(gate.evaluate(value))
        needs = self.results()
        needs["core"] = "success"
        self.assertFalse(gate.evaluate(needs))

    def test_command_returns_nonzero_and_writes_failure_for_invalid_metadata(self):
        for metadata in ("", "{", "x" * 65537, json.dumps({"core": {"result": "success"}})):
            with self.subTest(length=len(metadata)), tempfile.TemporaryDirectory() as temp:
                report = Path(temp) / "gate.json"
                env = dict(os.environ, NEEDS_JSON=metadata)
                result = subprocess.run([sys.executable, str(ROOT / "tools/release_gate.py"),
                                         "--report", str(report)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(report.read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
