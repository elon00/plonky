import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codeql_gate", ROOT / "tools/codeql_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class CodeQLGateTests(unittest.TestCase):
    def documents(self, folder, *, severity="8.0", level="warning", finding=True):
        for language in ("python", "javascript"):
            document = {"version": "2.1.0", "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": [{
                    "id": "example-rule", "properties": {"security-severity": severity},
                    "defaultConfiguration": {"level": level},
                }]}},
                "automationDetails": {"id": "/" + language + "/"},
                "results": [{"ruleId": "example-rule", "suppressions": [{"kind": "inSource"}]}] if finding else [],
            }]}
            (folder / (language + ".sarif")).write_text(json.dumps(document), encoding="utf-8")

    def test_both_real_analysis_outputs_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with self.assertRaises(ValueError):
                gate.inspect(folder)
            self.documents(folder, finding=False)
            self.assertEqual(gate.inspect(folder), 0)
            (folder / "python.sarif").unlink()
            with self.assertRaises(ValueError):
                gate.inspect(folder)

    def test_high_critical_and_error_findings_block_even_with_suppressions(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for severity, level, expected in (("7.0", "warning", 2), ("10.0", "note", 2),
                                               ("4.0", "error", 2), ("4.0", "warning", 0)):
                self.documents(folder, severity=severity, level=level)
                self.assertEqual(gate.inspect(folder), expected)

    def test_incomplete_tool_execution_does_not_pass_empty_results(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.documents(folder, finding=False)
            path = folder / "python.sarif"
            data = json.loads(path.read_text())
            data["runs"][0]["invocations"] = [{"executionSuccessful": False}]
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                gate.inspect(folder)

    def test_malformed_analysis_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for severity in ("NaN", "Infinity", "-1", "11", "invalid"):
                self.documents(folder, severity=severity)
                with self.assertRaises(ValueError):
                    gate.inspect(folder)
            self.documents(folder)
            path = folder / "python.sarif"
            data = json.loads(path.read_text())
            data["runs"][0]["results"][0]["ruleId"] = "unknown-rule"
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                gate.inspect(folder)


if __name__ == "__main__":
    unittest.main()
