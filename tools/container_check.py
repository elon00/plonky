#!/usr/bin/env python3
"""Smoke, access-control, bounded-load and shutdown checks for our own test container."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import http.client
import os
from pathlib import Path
import re
import secrets
import statistics
import subprocess
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
def docker(*args,env=None):
    return subprocess.check_output(["docker",*args],env=env,text=True,stderr=subprocess.STDOUT).strip()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--image",default="qmoosa:local");args=parser.parse_args()
    run=secrets.token_hex(8);token=secrets.token_urlsafe(32);env=dict(os.environ);env["QMOOSA_ACCESS_TOKEN"]=token;cid=None
    try:
        cid=docker("run","-d","--label","qmoosa.test-run="+run,"--read-only","--tmpfs","/tmp:size=16m,noexec,nosuid",
            "--cap-drop","ALL","--security-opt","no-new-privileges","--memory","256m","--cpus","1","--pids-limit","64",
            "-p","127.0.0.1::8080","-e","QMOOSA_ACCESS_TOKEN","-e","QMOOSA_ALLOWED_HOSTS=workbench.test",
            "-e","QMOOSA_RATE_LIMIT=500","-e","QMOOSA_GLOBAL_RATE_LIMIT=1000",args.image,env=env)
        if not re.fullmatch(r"[0-9a-f]{64}",cid):raise RuntimeError("Unexpected container identifier")
        address=docker("port",cid,"8080/tcp").splitlines()[0];base="http://"+address
        def get(path,auth=True):
            started=time.monotonic();headers={"Host":"workbench.test"}
            if auth:headers["Authorization"]="Bearer "+token
            try:
                with urlopen(Request(base+path,headers=headers),timeout=20) as reply:
                    return reply.status,reply.read(),dict(reply.headers),(time.monotonic()-started)*1000
            except HTTPError as error:
                result=error.code,error.read(),dict(error.headers),(time.monotonic()-started)*1000;error.close();return result
        for _ in range(150):
            try:
                if get("/readyz",False)[0]==200:break
            except (URLError,OSError):pass
            time.sleep(.2)
        else:raise RuntimeError("Container did not become ready")
        assert get("/api/health",False)[0]==401
        assert get("/api/health")[0]==200
        assert get("/api/life?board=1&steps=10001")[0]==400
        code,raw,headers,_=get("/api/pqc")
        assert code==200 and json.loads(raw)["payload_tamper_rejected"]
        assert headers.get("X-Content-Type-Options")=="nosniff"
        with ThreadPoolExecutor(max_workers=8) as pool:
            samples=list(pool.map(lambda _:get("/api/life?board=1&steps=1"),range(24)))
        assert all(row[0] in (200,503) for row in samples)
        assert any(row[0]==200 for row in samples)
        assert get("/readyz",False)[0]==200
        for _ in range(120):
            if docker("inspect","--format","{{.State.Health.Status}}",cid)=="healthy":break
            time.sleep(.25)
        else:raise RuntimeError("Docker localhost health probe failed")
        persistent=http.client.HTTPConnection(address,timeout=15)
        persistent.request("GET","/api/health",headers={"Host":"workbench.test","Authorization":"Bearer "+token})
        reply=persistent.getresponse();assert reply.status==200;reply.read()
        assert persistent.sock is not None,"Test must leave a persistent channel open"
        shutdown=time.monotonic();docker("stop","--time","10",cid)
        persistent.close()
        exit_code=int(docker("inspect","--format","{{.State.ExitCode}}",cid))
        if exit_code!=0:raise RuntimeError(f"Non-graceful shutdown: exit {exit_code}\n"+docker("logs",cid).replace(token,"[redacted]"))
        result={"status":"passed","access_control":"passed","pqc":"passed","pressure_requests":len(samples),
            "successful":sum(x[0]==200 for x in samples),"busy_responses":sum(x[0]==503 for x in samples),
            "pressure_max_ms":round(max(x[3] for x in samples),2),"shutdown_seconds":round(time.monotonic()-shutdown,2),"exit_code":exit_code}
        report=ROOT/"reports/container-check.json";report.parent.mkdir(exist_ok=True);report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,indent=2))
    finally:
        if cid and re.fullmatch(r"[0-9a-f]{64}",cid):
            if docker("inspect","--format",'{{index .Config.Labels "qmoosa.test-run"}}',cid)==run:
                docker("rm","-f",cid)
if __name__=="__main__":main()
