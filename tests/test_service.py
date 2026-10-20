import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import service

TOKEN="test-only-token-"+"a"*40
def request(application,path="/api/health",method="GET",token=TOKEN,host="localhost:8080",**extra):
    path,_,query=path.partition("?")
    env={"REQUEST_METHOD":method,"PATH_INFO":path,"QUERY_STRING":query,"HTTP_HOST":host,
         "REMOTE_ADDR":"127.0.0.1","wsgi.url_scheme":"http","wsgi.input":io.BytesIO(),"CONTENT_LENGTH":""}
    if token is not None:env["HTTP_AUTHORIZATION"]="Bearer "+token
    env.update(extra);response={}
    def start(status,headers):response.update(status=int(status.split()[0]),headers=dict(headers))
    response["body"]=b"".join(application(env,start))
    return response
def application(**kwargs):
    return service.Application(service.Settings(("localhost","127.0.0.1"),TOKEN,**kwargs))

class ProductionService(unittest.TestCase):
    def test_configuration_fails_closed(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaises(ValueError):service.Settings.from_env()
        with self.assertRaises(ValueError):service.Settings(("*",),TOKEN).validate()
        with self.assertRaises(ValueError):service.Settings(("localhost",),"short").validate()
    def test_real_startup_and_readiness(self):
        app=application()
        self.assertTrue(app.ready)
        self.assertEqual(request(app,"/readyz",token=None)["status"],200)
        self.assertEqual(request(app,"/healthz",token=None)["status"],200)
        app.ready=False
        self.assertEqual(request(app,"/readyz",token=None)["status"],503)
    def test_auth_and_public_static_config(self):
        app=application()
        for token in (None,"bad"):
            result=request(app,token=token)
            self.assertEqual(result["status"],401)
            self.assertEqual(result["headers"]["WWW-Authenticate"],"Bearer")
        config=request(app,"/api/config",token=None)
        self.assertTrue(json.loads(config["body"])["auth_required"])
        self.assertEqual(request(app,"/",token=None)["status"],200)
        self.assertEqual(request(app)["status"],200)
        self.assertNotIn(TOKEN,request(app)["body"].decode())
    def test_explicit_public_mode(self):
        app=application(public_demo=True)
        self.assertEqual(request(app,token=None)["status"],200)
    def test_host_origin_and_cross_site_rejection(self):
        app=application()
        for values in ({"host":"evil.example"},{"HTTP_ORIGIN":"https://evil.example"},{"HTTP_SEC_FETCH_SITE":"cross-site"}):
            with self.subTest(values=values):self.assertEqual(request(app,**values)["status"],403)
    def test_rate_limits_and_retry_after(self):
        app=application(requests_per_minute=2)
        self.assertEqual(request(app)["status"],200)
        self.assertEqual(request(app)["status"],200)
        third=request(app);self.assertEqual(third["status"],429);self.assertEqual(third["headers"]["Retry-After"],"60")
        self.assertEqual(request(app,"/readyz",token=None)["status"],200)
    def test_global_limit_and_expiry(self):
        now=[0.]
        limiter=service.RateLimiter(10,2,clock=lambda:now[0])
        self.assertTrue(limiter.allow("a"));self.assertTrue(limiter.allow("b"));self.assertFalse(limiter.allow("c"))
        now[0]=61
        self.assertTrue(limiter.allow("c"))
    def test_request_boundaries_and_methods(self):
        app=application(max_steps=5)
        self.assertEqual(request(app,"/api/life?board=1&steps=6")["status"],400)
        self.assertEqual(request(app,"/api/life?board=1&steps=1")["status"],200)
        self.assertEqual(request(app,"/../.env")["status"],404)
        self.assertEqual(request(app,"/api/rpc","POST",CONTENT_LENGTH="1")["status"],400)
        self.assertEqual(request(app,"/api/health","DELETE")["status"],405)
        self.assertEqual(request(app,"/api/health","HEAD")["body"],b"")
    def test_security_headers_and_request_ids(self):
        result=request(application(),**{"wsgi.url_scheme":"https"})
        self.assertEqual(result["headers"]["Referrer-Policy"],"no-referrer")
        self.assertIn("Strict-Transport-Security",result["headers"])
        self.assertEqual(len(result["headers"]["X-Request-ID"]),32)
        self.assertNotIn("unsafe-eval",result["headers"]["Content-Security-Policy"])
    def test_no_secrets_in_errors_or_logs(self):
        app=application()
        with patch("app.core",side_effect=RuntimeError("secret-value")),self.assertLogs("qmoosa",level="INFO") as logs:
            result=request(app,"/api/pqc?private-token=secret-value")
        self.assertEqual(result["status"],503)
        self.assertNotIn("secret-value",result["body"].decode()+"".join(logs.output))
        self.assertNotIn(TOKEN,"".join(logs.output))
    def test_limiter_memory_bound(self):
        limiter=service.RateLimiter(1,100,max_clients=3)
        for index in range(10):limiter.allow(str(index))
        self.assertEqual(len(limiter.clients),3)

if __name__=="__main__":unittest.main()
