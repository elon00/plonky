#!/usr/bin/env python3
"""Inventory, back up, apply and verify ONE shared release across a repository fleet.
Never stages, commits, pushes, deletes repositories, or edits Git internals.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading

SOURCE=Path(__file__).resolve().parents[1]
FILES=[
 "Cargo.toml","Cargo.lock","src/main.rs","src/lib.rs","src/engine.rs","src/index.ts","tsconfig.json","sdk-tests/client.test.mjs","qmoosa-core/Cargo.toml","qmoosa-core/src/lib.rs",
 "app.py","project.json","web/index.html","web/style.css","web/app.js",
 "tests/reality_check_harness.py","tests/test_app.py","tests/test_fleet.py","tools/browser_check.py","contracts/LaunchpadToken.sol",
 "contract-tests/LaunchpadToken.t.sol","foundry.toml","package.json","package-lock.json",
 ".env.example",".gitignore",".github/workflows/ci-cd-pipeline.yml",
 ".github/workflows/codeql.yml","README.md","ARCHITECTURE_BOOK.md","PRODUCTION_GAPS.md",
 "DEMO_GUIDE.md","SECURITY.md","tools/fleet.py","tools/verify.py"
]
# Old unconfigured MCP claims are replaced by an empty, non-connecting configuration.
FILES.append("mcp.json")
FILES.extend(["src/chain-upgrades.ts","sdk-tests/chain-upgrades.test.mjs","tools/chain-upgrades.mjs","CHAIN_UPGRADES.md"])
FILES.extend(['service.py', 'Dockerfile', '.dockerignore', '.gitattributes', 'deploy/compose.yml', '.env.production.example', 'qmoosa-wasm/Cargo.toml', 'qmoosa-wasm/src/lib.rs', 'web/bootstrap.js', 'tools/build_web.py', 'tools/prepare_release_dependencies.py', 'ci/action-pins.json', 'requirements.txt', 'requirements-browser.txt', 'tests/test_service.py', 'tools/web_check.py', 'qmoosa-core/tests/nist_kat.rs', 'qmoosa-core/tests/fixtures/nist-mlkem768.json', 'tools/dependency_audit.py', 'tools/container_check.py', 'script/DeployLaunchpad.s.sol', 'DEPLOYMENT.md', 'AUDIT_PACKET.md', 'RELEASE_PLAN.md', 'tools/fleet_publish.py', 'tests/test_publish.py'])

def digest(data): return hashlib.sha256(data).hexdigest()
def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    atomic(path,(json.dumps(data,indent=2)+"\n").encode())
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as file:
        temporary=Path(file.name);file.write(data)
    try:
        os.chmod(temporary,stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644)
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()
def safe(repo,relative):
    target=repo/relative
    if not target.resolve().is_relative_to(repo.resolve()):
        raise ValueError(f"Path escapes repository: {target}")
    return target
def repositories(root):
    if not root.is_dir(): raise ValueError("Fleet root does not exist")
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and (p/".git").exists())
def scan_instructions(repo):
    # Ignore dependencies and generated output when discovering local instructions.
    found=[]
    for folder,dirs,files in os.walk(repo):
        dirs[:]=[d for d in dirs if d not in {".git","target","node_modules","out","cache","__pycache__"}]
        if "AGENTS.md" in files: found.append(str(Path(folder)/"AGENTS.md"))
    return found
def inventory(root):
    repos=repositories(root); variants={name:Counter() for name in FILES}; rows=[]; instructions=[]
    for scan_index,repo in enumerate(repos,1):
        if scan_index%100==0: print(f"Inventory {scan_index}/{len(repos)}",flush=True)
        hashes={}
        for relative in FILES:
            path=safe(repo,relative)
            if path.is_file():
                raw=path.read_bytes();hashes[relative]=digest(raw)
                normalized=raw.replace(repo.name.encode(),b"{project}")
                variants[relative][digest(normalized)]+=1
        instructions.extend(scan_instructions(repo))
        rows.append({"name":repo.name,"files":hashes})
    return {"root":str(root),"count":len(rows),"instructions":instructions,"repositories":rows,
            "variant_counts":{key:dict(value) for key,value in variants.items() if value}}
def payloads(name):
    data={}
    for relative in FILES:
        raw=(SOURCE/relative).read_bytes()
        if relative=="project.json":
            meta=json.loads(raw);meta["name"]=name;raw=(json.dumps(meta,indent=2)+"\n").encode()
        data[relative]=raw
    return data
def apply_one(repo,snapshot,backup):
    expected=snapshot["files"];data=payloads(repo.name)
    # Refuse to clobber work changed since the reviewed inventory.
    for relative in FILES:
        path=safe(repo,relative)
        actual=digest(path.read_bytes()) if path.is_file() else None
        if actual!=expected.get(relative):
            raise ValueError(f"{repo.name}/{relative}: changed since inventory; re-inventory first")
    before={};after={}
    for relative,raw in data.items():
        target=safe(repo,relative)
        old=target.read_bytes() if target.is_file() else None
        if old is not None:
            old_path=backup/repo.name/relative;old_path.parent.mkdir(parents=True,exist_ok=True);old_path.write_bytes(old)
        before[relative]=digest(old) if old is not None else None
        after[relative]=digest(raw)
    # Journal exists before mutation, allowing recovery after an interrupted write.
    journal=backup/repo.name/"RESTORE.json"
    write_json(journal,{"repo":str(repo),"before":before,"after":after})
    for relative,raw in data.items(): atomic(safe(repo,relative),raw)
    write_json(repo/".qmoosa-release.json",{"version":"0.3.0","files":after,"backup":str(journal)})
    return {"name":repo.name,"status":"updated","files":len(data)}
def verify_one(repo,build,cache):
    expected=payloads(repo.name)
    bad=[relative for relative,raw in expected.items() if not safe(repo,relative).is_file() or digest(safe(repo,relative).read_bytes())!=digest(raw)]
    if bad: return {"name":repo.name,"status":"failed","mismatches":bad}
    result={"name":repo.name,"status":"verified","files":len(expected)}
    if build:
        env=dict(os.environ)
        env["CARGO_TARGET_DIR"]=str(cache)
        env["CARGO_INCREMENTAL"]="0"
        env["CARGO_PROFILE_DEV_DEBUG"]="0"
        run=subprocess.run(["cargo","build","--workspace","--locked","--offline"],cwd=repo,env=env,capture_output=True,text=True,timeout=180)
        if run.returncode:
            result.update(status="failed",error=run.stderr[-4000:]);return result
        binary=cache/"debug"/("qmoosa-app.exe" if os.name=="nt" else "qmoosa-app")
        check=subprocess.run([str(binary),"self-check"],cwd=repo,capture_output=True,text=True,timeout=30)
        if check.returncode:
            result.update(status="failed",error=check.stderr[-1000:]);return result
        output=json.loads(check.stdout)
        if output["pqc"]["status"]!="passed" or output["life"]["board"]!="000000001c000000":
            result.update(status="failed",error="unexpected core output");return result
        result.update(build="passed",self_check="passed")
    return result
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("inventory","apply","verify","rollback"))
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--report",type=Path,default=SOURCE/"reports"/"fleet.json")
    parser.add_argument("--snapshot",type=Path)
    parser.add_argument("--backup-root",type=Path)
    parser.add_argument("--expected-count",type=int,default=925)
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--workers",type=int,default=2)
    args=parser.parse_args()
    root=args.root.resolve();repos=repositories(root)
    if len(repos)!=args.expected_count: parser.error(f"Expected {args.expected_count} repositories, found {len(repos)}")
    if args.action=="inventory":
        result=inventory(root);write_json(args.report,result)
        print(json.dumps({"count":result["count"],"instructions":result["instructions"],"variant_counts":result["variant_counts"],"report":str(args.report)},indent=2))
        return 0
    if args.action=="apply":
        if not args.snapshot or not args.backup_root: parser.error("apply requires --snapshot and --backup-root")
        snapshot=json.loads(args.snapshot.read_text(encoding="utf-8"))
        if snapshot["root"]!=str(root) or snapshot["count"]!=len(repos): parser.error("Snapshot root/count mismatch")
        if snapshot["instructions"]: parser.error("Review listed AGENTS.md instructions before adapting this updater")
        backup=args.backup_root.resolve()/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        if backup.is_relative_to(root): parser.error("Use a backup directory outside the repository fleet")
        backup.mkdir(parents=True,exist_ok=False)
        snapshots={row["name"]:row for row in snapshot["repositories"]}
        results=[]
        for index,repo in enumerate(repos,1):
            try: results.append(apply_one(repo,snapshots[repo.name],backup))
            except Exception as error: results.append({"name":repo.name,"status":"failed","error":str(error)})
            if index%25==0 or index==len(repos): print(f"Applied {index}/{len(repos)}",flush=True)
        result={"root":str(root),"backup":str(backup),"results":results}
    elif args.action=="verify":
        # Each worker has its own cache: parallel Cargo processes must not overwrite
        # the binary between a build and that repository's self-check.
        results=[];completed_rows=[];progress_lock=threading.Lock();workers=max(1,min(args.workers,4))
        caches=[SOURCE/"target"/f"fleet-{i}" for i in range(workers)]
        groups=[repos[i::workers] for i in range(workers)]
        def group_run(group,cache):
            rows=[]
            for repo in group:
                try: row=verify_one(repo,args.build,cache)
                except Exception as error: row={"name":repo.name,"status":"failed","error":str(error)}
                rows.append(row)
                with progress_lock:
                    completed_rows.append(row)
                    if len(completed_rows)%25==0 or len(completed_rows)==len(repos):
                        write_json(args.report,{"root":str(root),"complete":False,"built":args.build,"completed":len(completed_rows),"results":list(completed_rows)})
                if args.build: print(f"{repo.name}: {row['status']}",flush=True)
            return rows
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(group_run,group,cache) for group,cache in zip(groups,caches)]
            for future in as_completed(futures):
                results.extend(future.result())
                pass  # each worker persists progress under the shared lock
        result={"root":str(root),"complete":True,"built":args.build,"results":sorted(results,key=lambda x:x["name"])}
    else:
        if not args.backup_root: parser.error("rollback requires --backup-root pointing to a timestamped backup")
        backup=args.backup_root.resolve();results=[]
        for repo in repos:
            journal_path=backup/repo.name/"RESTORE.json"
            if not journal_path.is_file(): continue
            journal=json.loads(journal_path.read_text(encoding="utf-8"))
            if Path(journal["repo"]).resolve()!=repo.resolve(): raise ValueError("Backup repository mismatch")
            if set(journal["before"])!=set(FILES) or set(journal["after"])!=set(FILES):
                raise ValueError("Rollback journal must contain exactly the managed files")
            # Verify all targets and backups before changing anything in this repo.
            for relative,old_hash in journal["before"].items():
                target=safe(repo,relative)
                current=digest(target.read_bytes()) if target.is_file() else None
                if current not in (old_hash,journal["after"][relative]): raise ValueError(f"New changes in {target}; rollback refused")
                if old_hash is not None and digest(safe(backup/repo.name,relative).read_bytes())!=old_hash: raise ValueError("Backup corrupted")
            for relative,old_hash in journal["before"].items():
                target=safe(repo,relative)
                if old_hash is None:
                    if target.exists(): target.unlink()
                else: atomic(target,safe(backup/repo.name,relative).read_bytes())
            marker=repo/".qmoosa-release.json"
            if marker.is_file(): marker.unlink()
            results.append({"name":repo.name,"status":"restored"})
        result={"root":str(root),"results":results}
    write_json(args.report,result)
    counts=Counter(row["status"] for row in result["results"])
    print(json.dumps({"counts":dict(counts),"report":str(args.report),"backup":result.get("backup")},indent=2),flush=True)
    return 1 if counts["failed"] else 0
if __name__=="__main__":
    sys.exit(main())
