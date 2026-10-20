"""Resolve immutable CI references and the hash-locked production dependency."""
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
ACTIONS={
 "actions/checkout":"v7","actions/setup-python":"v7","actions/setup-node":"v7",
 "dtolnay/rust-toolchain":"stable","foundry-rs/foundry-toolchain":"v1",
 "github/codeql-action":"v4","actions/configure-pages":"v5",
 "actions/upload-pages-artifact":"v4","actions/deploy-pages":"v4",
 "actions/upload-artifact":"v6"
}
def api(path):
    return json.loads(subprocess.check_output(["gh","api",path],text=True))
def main():
    refs={}
    for repo,tag in ACTIONS.items():
        value=api(f"repos/{repo}/git/ref/tags/{tag}")["object"] if repo!="dtolnay/rust-toolchain" else api(f"repos/{repo}/git/ref/heads/stable")["object"]
        while value["type"]=="tag":value=api(f"repos/{repo}/git/tags/{value['sha']}")["object"]
        assert value["type"]=="commit" and len(value["sha"])==40
        refs[repo]={"tag":tag,"sha":value["sha"]}
    path=ROOT/"ci/action-pins.json";path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(refs,indent=2)+"\n")
    with urlopen("https://pypi.org/pypi/waitress/3.0.2/json") as response:data=json.load(response)
    hashes=[item["digests"]["sha256"] for item in data["urls"]]
    (ROOT/"requirements.txt").write_text("waitress==3.0.2"+"".join(" \\\n    --hash=sha256:"+value for value in hashes)+"\n")
    print("Resolved",len(refs),"immutable CI action refs and Waitress wheel/source hashes")
if __name__=="__main__":main()
