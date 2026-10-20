import importlib.util
import json
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
if __name__=="__main__":unittest.main()
