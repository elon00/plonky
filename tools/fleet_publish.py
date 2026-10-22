#!/usr/bin/env python3
"""Publish only verified managed files after the canonical hosted CI passes."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import fleet

SOURCE=Path(__file__).resolve().parents[1]

REQUIRED_CI_JOBS=frozenset((
    "core (ubuntu-latest)", "core (windows-latest)", "contracts", "security",
    "credentials", "container", "web", "codeql / analyze (python)", "codeql / analyze (javascript-typescript)",
    "codeql / analyze (rust)", "codeql / analyze (actions)", "Required release gate", "deploy",
))
def git(repo,*args,check=True):
    result=subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True,timeout=120)
    if check and result.returncode:raise RuntimeError(result.stderr.strip()[:1200] or "Git command failed")
    return result
def validate_staging(repo):
    staged=set(git(repo,"diff","--cached","--name-only","-z").stdout.split("\0"))-{""}
    if staged-set(fleet.FILES):raise ValueError("Unrelated staged work exists; publishing refused")
def publish_one(repo,owner,publish,expected_origin=None):
    verification=fleet.verify_one(repo,False,SOURCE/"target")
    if verification["status"]!="verified":raise ValueError("Managed files do not match the release")
    if git(repo,"branch","--show-current").stdout.strip()!="main":raise ValueError("Expected main branch")
    origin=git(repo,"remote","get-url","origin").stdout.strip()
    expected=expected_origin or f"https://github.com/{owner}/{repo.name}.git"
    if origin.removesuffix(".git")!=expected.removesuffix(".git"):raise ValueError("Unexpected origin")
    validate_staging(repo)
    if not publish:return {"name":repo.name,"status":"ready","files":len(fleet.FILES)}
    git(repo,"fetch","--quiet","--no-tags","origin","main")
    head=git(repo,"rev-parse","HEAD").stdout.strip();remote=git(repo,"rev-parse","FETCH_HEAD").stdout.strip()
    if head!=remote:
        unpublished=git(repo,"rev-list",remote+".."+head).stdout.splitlines()
        if len(unpublished)!=1:raise ValueError("Unexpected unpublished commits; publishing refused")
        changed=set(git(repo,"diff-tree","--no-commit-id","--name-only","-r",head).stdout.splitlines())
        if changed-set(fleet.FILES):raise ValueError("Unpublished commit contains unexpected files; publishing refused")
        ancestor=git(repo,"merge-base","--is-ancestor",remote,head,check=False).returncode==0
        title=git(repo,"log","-1","--format=%s").stdout.strip()
        if not ancestor or title!="feat: publish verified QMoosa shared workbench 0.3":
            raise ValueError("Remote/local history diverged; publishing refused")
    git(repo,"add","--",*fleet.FILES)
    if git(repo,"diff","--cached","--quiet",check=False).returncode:
        git(repo,"commit","--only","-m","feat: publish verified QMoosa shared workbench 0.3","--",*fleet.FILES)
        changed=set(git(repo,"diff-tree","--no-commit-id","--name-only","-r","HEAD").stdout.splitlines())
        if changed-set(fleet.FILES):raise ValueError("Commit contains unexpected files; push refused")
    commit=git(repo,"rev-parse","HEAD").stdout.strip()
    for relative,expected in fleet.payloads(repo.name).items():
        content=subprocess.check_output(["git","-C",str(repo),"show",commit+":"+relative])
        if content!=expected:raise ValueError("Committed managed files do not match the release; push refused")
    if commit==remote:return {"name":repo.name,"status":"up_to_date","commit":commit}
    error=None
    for attempt in range(3):
        result=git(repo,"push","origin","HEAD:refs/heads/main",check=False)
        if result.returncode==0:return {"name":repo.name,"status":"published","commit":commit}
        error=result.stderr[-1200:];time.sleep(attempt+1)
    raise RuntimeError(error or "Push failed")
def check_proof(path,canonical=None):
    proof=json.loads(path.read_text(encoding="utf-8"))
    if proof.get("status")!="passed" or not re.fullmatch(r"[0-9a-f]{40}",proof.get("commit","")):
        raise ValueError("Canonical CI proof is invalid")
    canonical=canonical or SOURCE
    if git(canonical,"remote","get-url","origin").stdout.strip().removesuffix(".git")!="https://github.com/elon00/plonky":
        raise ValueError("Expected canonical Plonky repository")
    if git(canonical,"branch","--show-current").stdout.strip()!="main" or git(canonical,"rev-parse","HEAD").stdout.strip()!=proof["commit"]:
        raise ValueError("Canonical source HEAD does not match the CI proof")
    if git(canonical,"status","--porcelain","--",*fleet.FILES).stdout.strip():
        raise ValueError("Canonical managed source has uncommitted changes")
    run=json.loads(subprocess.check_output(["gh","api",f"repos/elon00/plonky/actions/runs/{int(proof['run_id'])}"],text=True,timeout=90))
    if run.get("head_sha")!=proof["commit"] or run.get("conclusion")!="success" or run.get("status")!="completed":
        raise ValueError("Canonical hosted CI has not passed for this commit")
    if run.get("head_branch")!="main" or run.get("path")!=".github/workflows/ci-cd-pipeline.yml" or run.get("repository",{}).get("full_name")!="elon00/plonky":
        raise ValueError("Expected the canonical main Verified core workflow")
    jobs=json.loads(subprocess.check_output(["gh","api",f"repos/elon00/plonky/actions/runs/{int(proof['run_id'])}/jobs?per_page=100&filter=latest"],text=True,timeout=90))
    rows=jobs.get("jobs")
    if not isinstance(rows,list) or jobs.get("total_count")!=len(rows) or len(rows)!=len(REQUIRED_CI_JOBS):
        raise ValueError("Canonical mandatory job evidence is incomplete")
    if {row.get("name") for row in rows}!=REQUIRED_CI_JOBS or any(
            row.get("status")!="completed" or row.get("conclusion")!="success" for row in rows):
        raise ValueError("Canonical mandatory jobs did not all pass; skipped or missing checks cannot publish")
    if set(proof["source_manifest"])!=set(fleet.FILES):raise ValueError("Proof does not cover the managed release")
    for relative,expected in proof["source_manifest"].items():
        committed=subprocess.check_output(["git","-C",str(canonical),"show",proof["commit"]+":"+relative])
        if hashlib.sha256(committed).hexdigest()!=expected:
            raise ValueError("Proof manifest does not match the verified Git commit")
        if hashlib.sha256((SOURCE/relative).read_bytes()).hexdigest()!=expected:
            raise ValueError("Source changed after canonical CI proof")
    if set(proof["source_manifest"])!=set(fleet.FILES):raise ValueError("Proof does not cover the managed release")
    return proof
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--proof",type=Path,required=True)
    parser.add_argument("--canonical-repo",type=Path,default=SOURCE)
    parser.add_argument("--report",type=Path,default=SOURCE/"reports/publish.json")
    parser.add_argument("--owner",default="elon00")
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--expected-count",type=int,default=925)
    parser.add_argument("--publish",action="store_true")
    args=parser.parse_args()
    proof=check_proof(args.proof,args.canonical_repo)
    repos=fleet.repositories(args.root.resolve())
    if len(repos)!=args.expected_count:parser.error("Repository count mismatch")
    results=[];lock=threading.Lock()
    def task(repo):
        try:return publish_one(repo,args.owner,args.publish)
        except Exception as error:return {"name":repo.name,"status":"failed","error":str(error)}
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,4))) as pool:
        futures=[pool.submit(task,repo) for repo in repos]
        for future in as_completed(futures):
            result=future.result();results.append(result);print(result["name"]+": "+result["status"],flush=True)
            if len(results)%10==0 or len(results)==len(repos):
                fleet.write_json(args.report,{"complete":False,"canonical_commit":proof["commit"],"results":results})
    fleet.write_json(args.report,{"complete":True,"canonical_commit":proof["commit"],"results":sorted(results,key=lambda x:x["name"])})
    failed=[row for row in results if row["status"]=="failed"]
    print(json.dumps({"repositories":len(results),"failed":len(failed),"published":sum(x["status"]=="published" for x in results),"up_to_date":sum(x["status"]=="up_to_date" for x in results)},indent=2))
    return 1 if failed else 0
if __name__=="__main__":sys.exit(main())
