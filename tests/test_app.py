import contextlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

@contextlib.contextmanager
def serve(handler):
    server=ThreadingHTTPServer(("127.0.0.1",0),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)

def rpc_handler(mode="valid"):
    class RPC(BaseHTTPRequestHandler):
        calls=[]
        def log_message(self,*args): pass
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.calls.append(request)
            if mode=="redirect":
                self.send_response(302);self.send_header("Location","https://example.invalid/token");self.end_headers();return
            self.send_response(401 if mode=="unauthorized" else 200);self.end_headers()
            result="0xaa36a7" if request["method"]=="eth_chainId" else "0x12345"
            reply={"jsonrpc":"2.0","id":request["id"],"result":result}
            if mode=="error": reply["error"]={"code":-32000,"message":"secret-token"}
            if mode=="bad_id": reply["id"]=999
            if mode=="boolean_id": reply["id"]=True
            if mode=="bad_hex": reply["result"]="not-a-number"
            if mode=="leading_zero": reply["result"]="0x01"
            raw=b"x"*(app.BODY_LIMIT+2) if mode=="oversized" else json.dumps(reply).encode()
            self.wfile.write(raw)
    return RPC

class RPCChecks(unittest.TestCase):
    def test_missing_config_is_not_success(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(app.rpc_probe()["status"],"not_configured")
    def test_actual_http_probe_and_expected_chain(self):
        handler=rpc_handler()
        with serve(handler) as url:
            result=app.rpc_probe(url,"11155111")
        self.assertEqual(result["status"],"connected")
        self.assertEqual(result["chain_id"],11155111)
        self.assertEqual(result["block_number"],0x12345)
        self.assertEqual([x["method"] for x in handler.calls],["eth_chainId","eth_blockNumber"])
    def test_wrong_chain_fails(self):
        with serve(rpc_handler()) as url:
            self.assertEqual(app.rpc_probe(url,"1")["status"],"failed")
    def test_errors_malformed_large_and_redirects_fail(self):
        for mode in ("error","bad_id","boolean_id","bad_hex","leading_zero","oversized","redirect","unauthorized"):
            with self.subTest(mode=mode),serve(rpc_handler(mode)) as url:
                result=app.rpc_probe(url)
                self.assertEqual(result["status"],"failed")
                self.assertNotIn("secret-token",json.dumps(result))
    def test_unsafe_urls_fail_without_network(self):
        for url in ("http://example.com","file:///etc/passwd","https://u:password@example.com","https://example.com/#token"):
            with self.subTest(url=url):
                self.assertEqual(app.rpc_probe(url)["status"],"failed")
    def test_connection_failure_is_not_success(self):
        with patch("app.build_opener") as factory:
            factory.return_value.open.side_effect=TimeoutError("secret endpoint")
            result=app.rpc_probe("https://example.invalid/private-token")
        self.assertEqual(result["status"],"failed")
        self.assertNotIn("private-token",json.dumps(result))
    def test_invalid_expected_chain_fails(self):
        for value in ("nope","0","-1"):
            self.assertEqual(app.rpc_probe("https://example.invalid",value)["status"],"failed")

class InputChecks(unittest.TestCase):
    def test_valid_large_board_keeps_64bit_precision(self):
        self.assertEqual(app.life_input("board=ffffffffffffffff&steps=0"),("ffffffffffffffff","0"))
    def test_invalid_input(self):
        for query in ("board=-1","board=10000000000000000","steps=10001","steps=-1","board=1&board=2","other=1","steps=x"):
            with self.subTest(query=query),self.assertRaises(ValueError):
                app.life_input(query)
    def test_core_real_cli_and_bad_input(self):
        if not app.executable().is_file():
            self.fail("Build core before running API integration tests")
        result=app.core("life","000000001c000000","2")
        self.assertEqual(result["board"],"000000001c000000")
        self.assertTrue(app.core("pqc")["payload_tamper_rejected"])
        with self.assertRaises(ValueError): app.core("life","zz","1")

class HTTPChecks(unittest.TestCase):
    def test_health_static_and_security_headers(self):
        with serve(app.Handler) as url:
            with urlopen(url+"/api/health") as reply:
                result=json.load(reply)
                self.assertEqual(result["status"],"ok")
                self.assertEqual(result["agents"],"not implemented")
                self.assertEqual(reply.headers["X-Content-Type-Options"],"nosniff")
                self.assertIn("frame-ancestors 'none'",reply.headers["Content-Security-Policy"])
            for path,needle in (("/","Conway engine"),("/app.js","BigInt"),("/style.css","--accent")):
                with urlopen(url+path) as reply:
                    self.assertIn(needle,reply.read().decode())
    def test_life_and_pqc_end_to_end(self):
        with serve(app.Handler) as url:
            with urlopen(url+"/api/life?board=1&steps=1") as reply:
                self.assertEqual(json.load(reply)["board"],"0000000000000000")
            with urlopen(url+"/api/pqc") as reply:
                self.assertTrue(json.load(reply)["shared_secret_match"])
    def test_bad_input_and_traversal(self):
        with serve(app.Handler) as url:
            for path,expected in (("/api/life?steps=10001",400),("/../.env",404),("/missing",404)):
                with self.subTest(path=path),self.assertRaises(HTTPError) as error:
                    urlopen(url+path)
                self.assertEqual(error.exception.code,expected)
                error.exception.close()
    def test_host_and_origin_checks(self):
        with serve(app.Handler) as url:
            for headers in ({"Host":"evil.example"},{"Origin":"https://evil.example"},{"Sec-Fetch-Site":"cross-site"}):
                with self.subTest(headers=headers),self.assertRaises(HTTPError) as error:
                    urlopen(Request(url+"/api/health",headers=headers))
                self.assertEqual(error.exception.code,403)
                error.exception.close()
    def test_rpc_post_is_explicit_and_accepts_no_url(self):
        with patch.dict(os.environ,{"QMOOSA_RPC_URL":""}),serve(app.Handler) as url:
            with urlopen(Request(url+"/api/rpc",method="POST")) as reply:
                self.assertEqual(json.load(reply)["status"],"not_configured")
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url+"/api/rpc",data=b'{"url":"https://evil.example"}',method="POST"))
            self.assertEqual(error.exception.code,400)
            error.exception.close()

if __name__=="__main__": unittest.main()
