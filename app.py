#!/usr/bin/env python3
"""Local demo host and explicit EVM RPC probe. Python 3.11+, standard library only."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
BODY_LIMIT = 65536
CORE_SLOTS = threading.BoundedSemaphore(4)
HEX_BOARD = re.compile(r"(?:0x)?[0-9a-fA-F]{1,16}\Z")
HEX_QUANTITY = re.compile(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)\Z")

def load_env():
    """Load simple KEY=value entries only. Never evaluate shell syntax."""
    path = ROOT / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            key, sep, value = raw.partition("=")
            if sep and re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))

def project():
    return json.loads((ROOT / "project.json").read_text(encoding="utf-8"))

def executable():
    explicit = os.environ.get("QMOOSA_CORE_BIN")
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else ROOT/path
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target"))
    if not target.is_absolute():
        target = ROOT / target
    return target / "debug" / ("qmoosa-app.exe" if os.name == "nt" else "qmoosa-app")

def build():
    subprocess.run(["cargo", "build", "--locked", "--workspace"], cwd=ROOT, check=True)

def core(*args):
    binary = executable()
    if not binary.is_file():
        raise RuntimeError("Core is not built. Run cargo build --locked first.")
    if not CORE_SLOTS.acquire(blocking=False):
        raise RuntimeError("Core is busy. Try again shortly.")
    try:
        result = subprocess.run([str(binary), *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise ValueError(result.stderr.strip()[:300] or "Core command failed")
        return json.loads(result.stdout)
    finally:
        CORE_SLOTS.release()

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def rpc_probe(url=None, expected_chain=None, timeout=5):
    endpoint = url if url is not None else os.environ.get("QMOOSA_RPC_URL", "")
    expected = expected_chain if expected_chain is not None else os.environ.get("QMOOSA_EXPECTED_CHAIN_ID", "")
    if not endpoint:
        return {"status":"not_configured","message":"Set QMOOSA_RPC_URL in .env to probe an EVM JSON-RPC endpoint."}
    try:
        parsed = urlsplit(endpoint)
        if parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
            raise ValueError("invalid endpoint")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1","localhost","::1")):
            raise ValueError("HTTPS required except on loopback")
        if expected:
            expected = int(str(expected), 0)
            if expected <= 0:
                raise ValueError("invalid chain id")
    except (ValueError, TypeError):
        return {"status":"failed","message":"Invalid RPC configuration. Use HTTPS or a loopback HTTP URL and a positive chain id."}

    opener = build_opener(NoRedirect())
    values = {}
    for idx, method in enumerate(("eth_chainId","eth_blockNumber"), 1):
        payload = json.dumps({"jsonrpc":"2.0","id":idx,"method":method,"params":[]}).encode()
        request = Request(endpoint, data=payload, headers={"Content-Type":"application/json"}, method="POST")
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(BODY_LIMIT + 1)
                if len(raw) > BODY_LIMIT:
                    raise ValueError("RPC response too large")
                reply = json.loads(raw)
            if not isinstance(reply, dict) or reply.get("jsonrpc") != "2.0" or type(reply.get("id")) is not int or reply["id"] != idx or "error" in reply:
                raise ValueError("invalid JSON-RPC reply")
            value = reply.get("result")
            if not isinstance(value, str) or not HEX_QUANTITY.fullmatch(value):
                raise ValueError("invalid hex quantity")
            values[method] = int(value, 16)
        except HTTPError as error:
            error.close()
            return {"status":"failed","message":f"RPC returned HTTP {error.code}."}
        except (URLError, TimeoutError, OSError):
            return {"status":"failed","message":"RPC request failed or timed out. Check endpoint credentials and connectivity."}
        except (ValueError, TypeError):
            return {"status":"failed","message":"RPC returned an invalid or oversized JSON-RPC response."}
    chain_id = values["eth_chainId"]
    if chain_id <= 0 or (expected and chain_id != expected):
        return {"status":"failed","message":"RPC chain id does not match configuration.","chain_id":chain_id}
    return {"status":"connected","chain_id":chain_id,"block_number":values["eth_blockNumber"],
            "message":"Two live read-only EVM RPC calls succeeded.","scope":"single configured endpoint; no transactions sent"}

def life_input(query):
    values = parse_qs(query, strict_parsing=True)
    if set(values) - {"board","steps"} or any(len(v) != 1 for v in values.values()):
        raise ValueError("Use one board and one steps parameter")
    board = values.get("board", ["000000001c000000"])[0]
    steps = values.get("steps", ["1"])[0]
    if not HEX_BOARD.fullmatch(board):
        raise ValueError("board must contain 1 to 16 hex digits")
    if not re.fullmatch(r"[0-9]{1,5}", steps) or int(steps) > 10000:
        raise ValueError("steps must be an integer between 0 and 10000")
    return board, steps

class Handler(BaseHTTPRequestHandler):
    server_version = "QMoosa"
    sys_version = ""
    def log_message(self, format, *args):
        # Never log URLs, tokens or query strings.
        return

    def respond(self, status, body, kind="application/json"):
        if kind == "application/json":
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}",f"localhost:{port}"):
            self.respond(403, {"error":"Invalid host"})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.respond(403, {"error":"Cross-site request blocked"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            self.respond(403, {"error":"Invalid origin"})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        try:
            if len(self.path) > 2048:
                raise ValueError("URL too long")
            route = urlsplit(self.path)
            static = {"/":("index.html","text/html"),"/app.js":("app.js","text/javascript"),"/style.css":("style.css","text/css")}
            if route.path in static:
                name, kind = static[route.path]
                self.respond(200, (ROOT/"web"/name).read_bytes(), kind)
            elif route.path == "/api/config":
                self.respond(200, {"auth_required":False,"name":project()["name"],"core_version":"0.3.0"})
            elif route.path == "/api/health":
                self.respond(200, {"status":"ok","project":project(),"core_built":executable().is_file(),
                                  "rpc":"configured; not yet probed" if os.environ.get("QMOOSA_RPC_URL") else "not configured",
                                  "agents":"not implemented","contracts":"local test reference; not deployed"})
            elif route.path == "/api/life":
                self.respond(200, core("life", *life_input(route.query)))
            elif route.path == "/api/pqc":
                self.respond(200, core("pqc"))
            else:
                self.respond(404, {"error":"Route not found"})
        except ValueError as error:
            self.respond(400, {"error":str(error)})
        except subprocess.TimeoutExpired:
            self.respond(504, {"error":"Core execution timed out"})
        except RuntimeError as error:
            self.respond(503, {"error":str(error)})
        except Exception:
            self.respond(500, {"error":"Internal error; run the verification command for details"})

    def do_POST(self):
        if not self.allowed():
            return
        # This endpoint accepts no body or user-supplied URL.
        if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Length","0") != "0":
            self.close_connection = True
            self.respond(400, {"error":"Request body not accepted"})
            return
        if self.path == "/api/rpc":
            result = rpc_probe()
            self.respond(200 if result["status"] != "failed" else 502, result)
        else:
            self.respond(404, {"error":"Route not found"})

def main():
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve","check","rpc"), nargs="?", default="serve")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "rpc":
        result = rpc_probe()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "connected" else 1
    build()
    if args.command == "check":
        print(json.dumps(core("self-check"), indent=2))
        return 0
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1",args.port), Handler)
    server.daemon_threads = True
    server.timeout = 10
    print(f"{project()['name']} demo: http://127.0.0.1:{args.port}", flush=True)
    print("Local development host. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"Build failed: {error}. Install Rust with Cargo and rerun.", file=sys.stderr)
        sys.exit(1)
