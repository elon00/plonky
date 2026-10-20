import importlib.util
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
            with patch.object(publish.fleet,"FILES",["managed.txt"]),patch.object(publish.fleet,"verify_one",return_value={"status":"verified"}):
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
if __name__=="__main__":unittest.main()
