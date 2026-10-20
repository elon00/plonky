#!/usr/bin/env python3
"""Bounded production WSGI service for the stateless QMoosa workbench."""
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
from http import HTTPStatus
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import uuid
from urllib.parse import urlsplit
import app

LOG=logging.getLogger("qmoosa")
CSP="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
SAFE_METHODS={"GET","HEAD"}
@dataclass(frozen=True)
class Settings:
    allowed_hosts:tuple[str,...]
    token:str=""
    public_demo:bool=False
    requests_per_minute:int=120
    global_per_minute:int=600
    max_steps:int=1000
    require_rpc:bool=False
    @classmethod
    def from_env(cls):
        hosts=tuple(x.strip().lower() for x in os.environ.get("QMOOSA_ALLOWED_HOSTS","127.0.0.1,localhost").split(",") if x.strip())
        token=os.environ.get("QMOOSA_ACCESS_TOKEN","")
        public=os.environ.get("QMOOSA_PUBLIC_DEMO","false").lower()=="true"
        settings=cls(hosts,token,public,int(os.environ.get("QMOOSA_RATE_LIMIT","120")),
            int(os.environ.get("QMOOSA_GLOBAL_RATE_LIMIT","600")),int(os.environ.get("QMOOSA_MAX_STEPS","1000")),
            os.environ.get("QMOOSA_REQUIRE_RPC","false").lower()=="true")
        settings.validate()
        return settings
    def validate(self):
        if not self.allowed_hosts or any("*" in host or "/" in host or ":" in host for host in self.allowed_hosts):
            raise ValueError("Set explicit QMOOSA_ALLOWED_HOSTS without schemes or ports")
        if not self.public_demo and len(self.token)<32:
            raise ValueError("Protected mode requires QMOOSA_ACCESS_TOKEN of at least 32 characters")
        if not (1<=self.requests_per_minute<=10000 and 1<=self.global_per_minute<=100000):
            raise ValueError("Invalid request limits")
        if not 1<=self.max_steps<=10000:
            raise ValueError("Invalid step limit")

class RateLimiter:
    """Single-instance limits; bounded memory; never trusts forwarded client headers."""
    def __init__(self,per_client,global_limit,max_clients=10000,clock=time.monotonic):
        self.per_client=per_client;self.global_limit=global_limit;self.max_clients=max_clients
        self.clients=OrderedDict();self.global_requests=deque();self.lock=threading.Lock();self.clock=clock
    def allow(self,key):
        now=self.clock()
        with self.lock:
            while self.global_requests and self.global_requests[0]<=now-60:self.global_requests.popleft()
            queue=self.clients.pop(key,deque())
            while queue and queue[0]<=now-60:queue.popleft()
            self.clients[key]=queue
            while len(self.clients)>self.max_clients:self.clients.popitem(last=False)
            if len(queue)>=self.per_client or len(self.global_requests)>=self.global_limit:return False
            queue.append(now);self.global_requests.append(now)
            return True

class Application:
    def __init__(self,settings,verify_startup=True):
        settings.validate();self.settings=settings
        self.limiter=RateLimiter(settings.requests_per_minute,settings.global_per_minute)
        self.ready=False;self.started=time.monotonic()
        if verify_startup:
            expected=os.environ.get("QMOOSA_CORE_SHA256","")
            binary=app.executable()
            if expected and not hmac.compare_digest(hashlib.sha256(binary.read_bytes()).hexdigest(),expected):
                raise RuntimeError("Core binary integrity check failed")
            check=app.core("self-check")
            if check.get("pqc",{}).get("status")!="passed" or check.get("life",{}).get("board")!="000000001c000000":
                raise RuntimeError("Core startup verification failed")
            if settings.require_rpc and app.rpc_probe().get("status")!="connected":
                raise RuntimeError("Required RPC startup check failed")
            self.ready=True
    def __call__(self,environ,start_response):
        started=time.monotonic();request_id=uuid.uuid4().hex
        method=environ.get("REQUEST_METHOD","GET")
        path=environ.get("PATH_INFO","/")
        headers=[]
        try:
            status,body,kind,headers=self.route(environ)
        except ValueError:
            status,body,kind=400,{"error":"Invalid request"},"application/json"
        except subprocess.TimeoutExpired:
            status,body,kind=504,{"error":"Core execution timed out"},"application/json"
        except RuntimeError:
            status,body,kind=503,{"error":"Core is unavailable or busy"},"application/json"
        except Exception:
            # Do not serialize exceptions: they may include provider credentials.
            LOG.error(json.dumps({"event":"internal_error","request_id":request_id}))
            status,body,kind=500,{"error":"Internal server error"},"application/json"
        if kind=="application/json":body=json.dumps(body,separators=(",",":")).encode()
        common=[("Content-Type",kind+"; charset=utf-8"),("Content-Length",str(len(body))),
            ("Cache-Control","no-store"),("X-Content-Type-Options","nosniff"),("X-Frame-Options","DENY"),
            ("Content-Security-Policy",CSP),("Referrer-Policy","no-referrer"),("Permissions-Policy","camera=(), microphone=(), geolocation=()"),
            ("X-Request-ID",request_id)]
        # TLS termination is the reverse proxy's responsibility.
        if environ.get("wsgi.url_scheme")=="https":common.append(("Strict-Transport-Security","max-age=31536000"))
        start_response(f"{status} {HTTPStatus(status).phrase}",common+headers)
        # Route labels only: never log query strings, headers, tokens, peer IPs or payloads.
        label=path if path in {"/","/app.js","/style.css","/healthz","/readyz","/api/config","/api/health","/api/life","/api/pqc","/api/rpc"} else "unknown"
        LOG.info(json.dumps({"event":"request","request_id":request_id,"method":method if method in {"GET","HEAD","POST"} else "other",
            "route":label,"status":status,"duration_ms":round((time.monotonic()-started)*1000,2)}))
        return [b"" if method=="HEAD" else body]
    def route(self,environ):
        method=environ.get("REQUEST_METHOD","GET");path=environ.get("PATH_INFO","/")
        if path in {"/healthz","/readyz"} and method in SAFE_METHODS:
            ready=path=="/healthz" or self.ready
            return (200 if ready else 503),{"status":"ok" if ready else "not_ready","version":"0.3.0"},"application/json",[]
        host=environ.get("HTTP_HOST","")
        parsed=urlsplit("//"+host)
        if parsed.username or parsed.password or parsed.path or parsed.hostname not in self.settings.allowed_hosts:
            return 403,{"error":"Invalid host"},"application/json",[]
        if len(path)+len(environ.get("QUERY_STRING",""))>2048:
            return 414,{"error":"Request target too long"},"application/json",[]
        if method not in {"GET","HEAD","POST"}:
            return 405,{"error":"Method not allowed"},"application/json",[("Allow","GET, HEAD, POST")]
        if environ.get("HTTP_SEC_FETCH_SITE")=="cross-site":
            return 403,{"error":"Cross-site request blocked"},"application/json",[]
        origin=environ.get("HTTP_ORIGIN")
        if origin:
            value=urlsplit(origin)
            if value.scheme not in {"http","https"} or value.netloc.lower()!=host.lower():
                return 403,{"error":"Invalid origin"},"application/json",[]
        if path.startswith("/api/") and not self.limiter.allow(environ.get("REMOTE_ADDR","unknown")):
            return 429,{"error":"Request limit exceeded; try again shortly"},"application/json",[("Retry-After","60")]
        if path=="/api/config" and method in SAFE_METHODS:
            return 200,{"auth_required":not self.settings.public_demo,"name":app.project()["name"],"core_version":"0.3.0"},"application/json",[]
        if path.startswith("/api/") and not self.settings.public_demo:
            supplied=environ.get("HTTP_AUTHORIZATION","")
            if not hmac.compare_digest(supplied,"Bearer "+self.settings.token):
                return 401,{"error":"Access token required"},"application/json",[("WWW-Authenticate","Bearer")]
        if method=="POST":
            if environ.get("HTTP_TRANSFER_ENCODING") or environ.get("CONTENT_LENGTH","") not in ("","0"):
                return 400,{"error":"Request body not accepted"},"application/json",[]
            if path!="/api/rpc":
                return 405,{"error":"Method not allowed"},"application/json",[("Allow","GET, HEAD")]
            result=app.rpc_probe()
            return (502 if result["status"]=="failed" else 200),result,"application/json",[]
        static={"/":("index.html","text/html"),"/app.js":("app.js","text/javascript"),"/style.css":("style.css","text/css")}
        if path in static:
            name,kind=static[path]
            return 200,(app.ROOT/"web"/name).read_bytes(),kind,[]
        if path=="/api/health":
            return 200,{"status":"ok","project":app.project(),"core_built":self.ready,
                "rpc":"configured; not yet probed" if os.environ.get("QMOOSA_RPC_URL") else "not configured",
                "agents":"not implemented","contracts":"local/testnet reference; deployment receipt required"},"application/json",[]
        if not self.ready:return 503,{"error":"Core is not ready"},"application/json",[]
        if path=="/api/life":
            board,steps=app.life_input(environ.get("QUERY_STRING",""))
            if int(steps)>self.settings.max_steps:raise ValueError("step limit")
            return 200,app.core("life",board,steps),"application/json",[]
        if path=="/api/pqc":return 200,app.core("pqc"),"application/json",[]
        return 404,{"error":"Route not found"},"application/json",[]

def create_app():
    app.load_env()
    return Application(Settings.from_env())

def shutdown_server(server):
    """Close persistent channels as well as the listener, then stop worker threads."""
    # Schedule socket closure on Waitress's event loop. Closing descriptors from
    # another thread can race with select() while a keep-alive channel is open.
    server.trigger.pull_trigger(lambda: server.asyncore.close_all(map=server._map))
    server.task_dispatcher.shutdown()

def main():
    from waitress import create_server
    logging.basicConfig(level=logging.INFO,format="%(message)s")
    application=create_app()
    port=int(os.environ.get("PORT","8080"))
    server=create_server(application,host=os.environ.get("QMOOSA_BIND","127.0.0.1"),port=port,threads=8,
        connection_limit=100,channel_timeout=30,cleanup_interval=5,max_request_header_size=8192,
        max_request_body_size=1024,clear_untrusted_proxy_headers=True,expose_tracebacks=False)
    def stop(*_):
        application.ready=False
        threading.Thread(target=shutdown_server,args=(server,),daemon=False).start()
    signal.signal(signal.SIGTERM,stop)
    try:
        LOG.info(json.dumps({"event":"startup","version":"0.3.0","mode":"public_demo" if application.settings.public_demo else "protected"}))
        server.run()
    except KeyboardInterrupt:stop()
    finally:server.close()

if __name__=="__main__":main()
