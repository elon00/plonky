import importlib.util
import json
import os
import stat
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/"tools"/"fleet.py"
spec=importlib.util.spec_from_file_location("fleet",MODULE)
fleet=importlib.util.module_from_spec(spec);spec.loader.exec_module(fleet)

class FleetSafety(unittest.TestCase):
    def test_backup_apply_verify_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);root=home/"repos";repo=root/"example";repo.mkdir(parents=True)
            (repo/".git").mkdir();(repo/"Cargo.toml").write_text("old manifest")
            (repo/"notes.txt").write_text("user work")
            snapshot=fleet.inventory(root)
            backup=home/"backups";backup.mkdir()
            result=fleet.apply_one(repo,snapshot["repositories"][0],backup)
            self.assertEqual(result["status"],"updated")
            self.assertEqual((backup/"example"/"Cargo.toml").read_text(),"old manifest")
            self.assertEqual((repo/"notes.txt").read_text(),"user work")
            self.assertEqual(fleet.verify_one(repo,False,home/"cache")["status"],"verified")
            report=home/"rollback.json"
            with patch("sys.argv",["fleet.py","rollback","--root",str(root),"--expected-count","1","--backup-root",str(backup),"--report",str(report)]):
                self.assertEqual(fleet.main(),0)
            self.assertEqual((repo/"Cargo.toml").read_text(),"old manifest")
            self.assertFalse((repo/"app.py").exists())
            self.assertEqual((repo/"notes.txt").read_text(),"user work")
    def test_changed_since_inventory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);repo=home/"repos"/"example";repo.mkdir(parents=True);(repo/".git").mkdir()
            path=repo/"Cargo.toml";path.write_text("before")
            snapshot=fleet.inventory(repo.parent)["repositories"][0]
            path.write_text("new user edit")
            with self.assertRaisesRegex(ValueError,"changed since inventory"):
                fleet.apply_one(repo,snapshot,home/"backup")
            self.assertEqual(path.read_text(),"new user edit")
    def test_instruction_discovery_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo=Path(temporary)/"repo";repo.mkdir();(repo/"AGENTS.md").write_text("local instructions")
            self.assertEqual(len(fleet.scan_instructions(repo)),1)
            with self.assertRaises(ValueError):fleet.safe(repo,"../../escape")
    def test_rollback_refuses_newer_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);root=home/"repos";repo=root/"example";repo.mkdir(parents=True);(repo/".git").mkdir()
            snapshot=fleet.inventory(root)["repositories"][0];backup=home/"backup";backup.mkdir()
            fleet.apply_one(repo,snapshot,backup);(repo/"app.py").write_text("new user edit")
            with patch("sys.argv",["fleet.py","rollback","--root",str(root),"--expected-count","1","--backup-root",str(backup)]):
                with self.assertRaisesRegex(ValueError,"New changes"):fleet.main()
            self.assertEqual((repo/"app.py").read_text(),"new user edit")

    def test_rollback_rejects_unmanaged_journal_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);root=home/"repos";repo=root/"example";repo.mkdir(parents=True);(repo/".git").mkdir()
            (repo/"notes.txt").write_text("user work")
            snapshot=fleet.inventory(root)["repositories"][0];backup=home/"backup";backup.mkdir()
            fleet.apply_one(repo,snapshot,backup)
            journal_path=backup/"example"/"RESTORE.json"
            journal=json.loads(journal_path.read_text(encoding="utf-8"))
            journal["before"]["notes.txt"]=None
            journal["after"]["notes.txt"]=fleet.digest(b"user work")
            journal_path.write_text(json.dumps(journal),encoding="utf-8")
            with patch("sys.argv",["fleet.py","rollback","--root",str(root),"--expected-count","1","--backup-root",str(backup)]):
                with self.assertRaisesRegex(ValueError,"exactly the managed files"):fleet.main()
            self.assertEqual((repo/"notes.txt").read_text(),"user work")

    def test_atomic_requests_owner_only_permissions_on_every_platform(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"managed.txt"
            chmod=os.chmod
            with patch.object(fleet.os,"chmod",wraps=chmod) as called:
                fleet.atomic(path,b"new")
                self.assertEqual(called.call_args.args[1],0o600)
            self.assertEqual(path.read_bytes(),b"new")

    @unittest.skipIf(os.name=="nt","POSIX file permissions")
    def test_atomic_writes_are_private_and_keep_owner_execute(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"managed.txt"
            fleet.atomic(path,b"new")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            path.chmod(0o640);fleet.atomic(path,b"update")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            path.chmod(0o700);fleet.atomic(path,b"executable")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o700)
if __name__=="__main__":unittest.main()

