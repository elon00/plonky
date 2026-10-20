import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"tools"))
import fleet_publish as publish

def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],text=True).strip()
class PublishSafety(unittest.TestCase):
    def repo(self,home):
        remote=home/"remote.git";repo=home/"example"
        subprocess.run(["git","init","--bare",str(remote)],capture_output=True,check=True)
        subprocess.run(["git","clone",str(remote),str(repo)],capture_output=True,check=True)
        git(repo,"config","user.name","Release test");git(repo,"config","user.email","test@example.invalid")
        git(repo,"checkout","-b","main")
        (repo/"managed.txt").write_text("before");(repo/"private.env").write_text("never publish")
        git(repo,"add","managed.txt");git(repo,"commit","-m","baseline");git(repo,"push","origin","main")
        (repo/"managed.txt").write_text("release")
        return repo,remote
    def test_publishes_managed_file_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,remote=self.repo(Path(temporary))
            with patch.object(publish.fleet,"FILES",["managed.txt"]),patch.object(publish.fleet,"payloads",return_value={"managed.txt":b"release"}),patch.object(publish.fleet,"verify_one",return_value={"status":"verified"}):
                result=publish.publish_one(repo,"unused",True,git(repo,"remote","get-url","origin"))
            self.assertEqual(result["status"],"published")
            self.assertEqual(git(repo,"ls-tree","--name-only","HEAD"),"managed.txt")
            self.assertEqual(git(repo,"rev-parse","HEAD"),subprocess.check_output(["git","--git-dir",str(remote),"rev-parse","main"],text=True).strip())
    def test_unrelated_staged_file_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,remote=self.repo(Path(temporary));git(repo,"add","private.env")
            with patch.object(publish.fleet,"FILES",["managed.txt"]),self.assertRaisesRegex(ValueError,"Unrelated staged"):
                publish.validate_staging(repo)
    def test_wrong_origin_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,_=self.repo(Path(temporary))
            with patch.object(publish.fleet,"verify_one",return_value={"status":"verified"}),self.assertRaisesRegex(ValueError,"Unexpected origin"):
                publish.publish_one(repo,"elon00",True)

    def test_prior_private_commit_cannot_hide_behind_release_subject(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,remote=self.repo(Path(temporary))
            git(repo,"add","private.env");git(repo,"commit","-m","local private work")
            git(repo,"add","managed.txt");git(repo,"commit","-m","feat: publish verified QMoosa shared workbench 0.3")
            with patch.object(publish.fleet,"FILES",["managed.txt"]),patch.object(publish.fleet,"verify_one",return_value={"status":"verified"}):
                with self.assertRaisesRegex(ValueError,"Unexpected unpublished commits"):
                    publish.publish_one(repo,"unused",True,str(remote))
            self.assertNotEqual(git(repo,"rev-parse","HEAD"),git(repo,"rev-parse","origin/main"))

    def test_unpushed_release_retry_is_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,remote=self.repo(Path(temporary))
            git(repo,"add","managed.txt");git(repo,"commit","-m","feat: publish verified QMoosa shared workbench 0.3")
            with patch.object(publish.fleet,"FILES",["managed.txt"]),patch.object(publish.fleet,"payloads",return_value={"managed.txt":b"release"}),patch.object(publish.fleet,"verify_one",return_value={"status":"verified"}):
                self.assertEqual(publish.publish_one(repo,"unused",True,str(remote))["status"],"published")

    def test_proof_is_bound_to_commit_and_canonical_workflow(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);repo,remote=self.repo(home)
            git(repo,"add","managed.txt");git(repo,"commit","-m","candidate")
            git(repo,"remote","set-url","origin","https://github.com/elon00/plonky.git")
            commit=git(repo,"rev-parse","HEAD")
            proof={"status":"passed","commit":commit,"run_id":1,"source_manifest":{"managed.txt":hashlib.sha256(b"release").hexdigest()}}
            path=home/"proof.json";path.write_text(json.dumps(proof),encoding="utf-8")
            run={"head_sha":commit,"status":"completed","conclusion":"success","head_branch":"main","path":".github/workflows/ci-cd-pipeline.yml","repository":{"full_name":"elon00/plonky"}}
            real=publish.subprocess.check_output
            def output(args,**kwargs):
                return json.dumps(run) if args[0]=="gh" else real(args,**kwargs)
            with patch.object(publish,"SOURCE",repo),patch.object(publish.fleet,"FILES",["managed.txt"]),patch.object(publish.subprocess,"check_output",side_effect=output):
                self.assertEqual(publish.check_proof(path)["commit"],commit)
                for key,value in (("path",".github/workflows/codeql.yml"),("head_branch","unreviewed")):
                    original=run[key];run[key]=value
                    with self.assertRaisesRegex(ValueError,"canonical main"):publish.check_proof(path)
                    run[key]=original
                (repo/"managed.txt").write_text("unverified edit")
                with self.assertRaisesRegex(ValueError,"uncommitted"):publish.check_proof(path)
                proof["source_manifest"]["managed.txt"]=hashlib.sha256(b"unverified edit").hexdigest()
                path.write_text(json.dumps(proof),encoding="utf-8")
                git(repo,"add","managed.txt");git(repo,"commit","-m","unverified")
                with self.assertRaisesRegex(ValueError,"HEAD"):publish.check_proof(path)
                proof["commit"]=git(repo,"rev-parse","HEAD");run["head_sha"]=proof["commit"]
                proof["source_manifest"]["managed.txt"]=hashlib.sha256(b"forged").hexdigest()
                path.write_text(json.dumps(proof),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"verified Git commit"):publish.check_proof(path)
if __name__=="__main__":unittest.main()

