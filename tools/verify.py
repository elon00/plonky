#!/usr/bin/env python3
"""One command for the complete local release checks. Live RPC is opt-in."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-rpc",action="store_true")
    args=parser.parse_args()
    commands=[
        ["cargo","fmt","--all","--","--check"],
        ["cargo","clippy","--workspace","--all-targets","--locked","--","-D","warnings"],
        [sys.executable,"tests/reality_check_harness.py"],
        ["node","--check","web/app.js"],
        ["node","--check","web/bootstrap.js"],
        [sys.executable,"tools/dependency_audit.py"],
        ["npm.cmd" if os.name=="nt" else "npm","ci","--ignore-scripts"],
        ["npm.cmd" if os.name=="nt" else "npm","test"],
        ["forge","test","-vv"],
    ]
    if args.live_rpc:commands.append([sys.executable,"app.py","rpc"])
    rows=[]
    for command in commands:
        print("RUN:"," ".join(command),flush=True)
        try:run=subprocess.run(command,cwd=ROOT,timeout=600)
        except (OSError,subprocess.TimeoutExpired) as error:
            print(str(error),file=sys.stderr);return 1
        rows.append({"command":command,"exit_code":run.returncode})
        output=ROOT/"reports"/"verification.json";output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps({"checks":rows,"live_rpc_requested":args.live_rpc},indent=2)+"\n")
        if run.returncode:return run.returncode
    print("All requested checks passed. See PRODUCTION_GAPS.md for release limits.",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
