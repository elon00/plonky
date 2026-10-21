import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest
from unittest.mock import patch

WORK = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("security_guard", WORK / "tools/security_guard.py")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class CredentialGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="qmoosa-guard-test-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        guard.run(["git", "init", "-q", str(self.repo)])
        guard.git(self.repo, "config", "user.name", "Security fixture")
        guard.git(self.repo, "config", "user.email", "fixture@example.invalid")

    def tearDown(self):
        self.temp.cleanup()

    def commit(self):
        guard.git(self.repo, "add", "--all")
        guard.git(self.repo, "-c", "user.name=Security fixture", "-c", "user.email=fixture@example.invalid",
                  "commit", "-qm", "fixture")

    def assert_detected_without_disclosure(self, credential):
        report = self.root / "report.json"
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = guard.scan(self.repo, report)
        self.assertEqual(result, 1)
        self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["findings"])
        self.assertNotIn(credential, output.getvalue())
        self.assertNotIn(credential.encode(), report.read_bytes())
        self.assertNotIn('"Secret":', report.read_text(encoding="utf-8"))

    def test_deleted_credential_is_found_despite_repository_suppressions(self):
        credential = "ghp_" + secrets.token_hex(18)
        (self.repo / "config.js").write_text("const apiKey='" + credential + "'; // gitleaks:allow\n", encoding="utf-8")
        (self.repo / ".gitleaks.toml").write_text('[allowlist]\nregexes=[\'.*\']\n', encoding="utf-8")
        self.commit()
        (self.repo / "config.js").unlink()
        self.commit()
        self.assert_detected_without_disclosure(credential)

    def test_staged_credential_is_found_before_commit(self):
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.commit()
        credential = "ghp_" + secrets.token_hex(18)
        (self.repo / "config.js").write_text("const apiKey='" + credential + "';\n", encoding="utf-8")
        guard.git(self.repo, "add", "config.js")
        self.assert_detected_without_disclosure(credential)

    def test_shallow_history_is_rejected(self):
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.commit()
        clone = self.root / "shallow"
        guard.run(["git", "clone", "--depth", "1", self.repo.as_uri(), str(clone)])
        with self.assertRaisesRegex(RuntimeError, "Full history"):
            guard.scan(clone, self.root / "report.json")

    def test_credential_added_only_in_merge_commit_is_detected(self):
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.commit()
        initial = guard.git(self.repo, "branch", "--show-current").decode().strip()
        guard.git(self.repo, "checkout", "-qb", "other")
        (self.repo / "other.txt").write_text("branch\n", encoding="utf-8")
        self.commit()
        guard.git(self.repo, "checkout", initial)
        guard.git(self.repo, "merge", "--no-ff", "--no-commit", "other")
        credential = "ghp_" + secrets.token_hex(18)
        (self.repo / "config.js").write_text("const apiKey='" + credential + "';\n", encoding="utf-8")
        self.commit()
        (self.repo / "config.js").unlink()
        self.commit()
        self.assert_detected_without_disclosure(credential)

    def test_commit_message_credential_is_detected(self):
        credential = "ghp_" + secrets.token_hex(18)
        guard.git(self.repo, "-c", "user.name=Security fixture", "-c", "user.email=fixture@example.invalid",
                  "commit", "--allow-empty", "-qm", "api_key=" + credential)
        self.assert_detected_without_disclosure(credential)

    def test_annotated_tag_message_credential_is_detected(self):
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.commit()
        credential = "ghp_" + secrets.token_hex(18)
        guard.git(self.repo, "-c", "user.name=Security fixture", "-c", "user.email=fixture@example.invalid",
                  "tag", "-a", "fixture", "-m", "api_key=" + credential)
        self.assert_detected_without_disclosure(credential)

    def test_archive_tampering_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            guard.unpack(b"not the trusted archive")

    def test_installed_binary_tampering_is_rejected(self):
        suffix, _, executable = guard.asset()
        archive = (WORK / ".local/security" / suffix).read_bytes()
        cache = self.root / ".local/security"
        cache.mkdir(parents=True)
        (cache / suffix).write_bytes(archive)
        (cache / executable).write_bytes(b"untrusted executable fixture")
        with patch.object(guard, "WORK", self.root), self.assertRaisesRegex(RuntimeError, "differs"):
            guard.scanner()

    def test_fixture_review_requires_exact_file_content(self):
        path = self.repo / "negative-test.js"
        path.write_text("const url='https://" + "user:password" + "@example.com';\n", encoding="utf-8", newline="\n")
        self.commit()
        finding = {"RuleID": "qmoosa-credential-url", "File": path.name, "StartLine": 1,
                   "Commit": guard.git(self.repo, "rev-parse", "HEAD").decode().strip()}
        approvals = [{"rule": finding["RuleID"], "path": path.name, "line": 1,
                      "blob_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
        self.assertTrue(guard.reviewed(self.repo, finding, approvals, False))
        path.write_text(path.read_text(encoding="utf-8") + "// modified fixture\n", encoding="utf-8", newline="\n")
        self.commit()
        finding["Commit"] = guard.git(self.repo, "rev-parse", "HEAD").decode().strip()
        self.assertFalse(guard.reviewed(self.repo, finding, approvals, False))


if __name__ == "__main__":
    unittest.main()
