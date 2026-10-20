#!/usr/bin/env python3
"""Check resolved application dependencies against current OSV advisories. Fail closed."""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sys
import tomllib
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
def main():
    packages=set()
    lock=tomllib.loads((ROOT/"Cargo.lock").read_text(encoding="utf-8"))
    for item in lock["package"]:
        if str(item.get("source","")).startswith("registry+"):
            packages.add(("crates.io",item["name"],item["version"]))
    lock=json.loads((ROOT/"package-lock.json").read_text(encoding="utf-8"))
    for path,item in lock["packages"].items():
        if path:packages.add(("npm",path.split("node_modules/")[-1],item["version"]))
    for line in "\n".join(path.read_text(encoding="utf-8") for path in ROOT.glob("requirements*.txt")).splitlines():
        match=re.match(r"([a-zA-Z0-9_.-]+)==([^\s\\]+)",line)
        if match:packages.add(("PyPI",match[1],match[2]))
    packages=sorted(packages);pending=list(range(len(packages)));tokens={};findings=[]
    try:
        while pending:
            queries=[]
            for index in pending:
                ecosystem,name,version=packages[index]
                query={"package":{"ecosystem":ecosystem,"name":name},"version":version}
                if index in tokens:query["page_token"]=tokens[index]
                queries.append(query)
            request=Request("https://api.osv.dev/v1/querybatch",data=json.dumps({"queries":queries}).encode(),headers={"Content-Type":"application/json"},method="POST")
            with urlopen(request,timeout=45) as response:reply=json.load(response)
            if len(reply["results"])!=len(pending):raise ValueError("Incomplete advisory response")
            again=[]
            for index,result in zip(pending,reply["results"]):
                for vuln in result.get("vulns",[]):
                    findings.append({"package":packages[index],"id":vuln["id"]})
                if result.get("next_page_token"):tokens[index]=result["next_page_token"];again.append(index)
            pending=again
        report={"status":"passed" if not findings else "failed","checked_at":datetime.now(timezone.utc).isoformat(),"packages_checked":len(packages),"findings":findings,"source":"https://api.osv.dev/v1/querybatch"}
    except Exception as error:
        report={"status":"unavailable","message":type(error).__name__,"packages_checked":0,"findings":[]}
    out=ROOT/"reports/dependency-audit.json";out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["status"]=="passed" else 1
if __name__=="__main__":sys.exit(main())
