"""Exercise the browser-hosted Rust/WASM demo locally or at a published URL."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--live-rpc",action="store_true")
    args=parser.parse_args();server=None
    reports=ROOT/"reports";reports.mkdir(exist_ok=True)
    if not args.url:
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(SimpleHTTPRequestHandler,directory=str(ROOT/"site")))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        args.url=f"http://127.0.0.1:{server.server_port}/"
    try:
        with sync_playwright() as runtime:
            edge=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser=runtime.chromium.launch(headless=True,**({"executable_path":str(edge)} if edge.exists() else {}))
            page=browser.new_page(viewport={"width":1440,"height":1060})
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(args.url,wait_until="networkidle")
            expect(page.locator("#step")).to_be_enabled(timeout=30000)
            expect(page.locator(".context")).to_contain_text("PUBLIC DEMO")
            expect(page.locator("#step")).to_have_text("Step →")
            expect(page.locator(".brand")).to_have_text("Q·Moosa")
            page.locator("#step").click();expect(page.locator("#generation")).to_have_text("1")
            page.locator("#step").click();expect(page.locator("#generation")).to_have_text("2")
            page.locator("#pqc").click();expect(page.locator("#pqc-status")).to_have_text(re.compile("^Exchange completed"),timeout=30000)
            first=json.loads(page.locator("#evidence").inner_text())["pqc"]["result"]["ciphertext_sha256"]
            page.locator("#pqc").click();expect(page.locator("#pqc-status")).to_have_text(re.compile("^Exchange completed"),timeout=30000)
            data=json.loads(page.locator("#evidence").inner_text())
            assert data["pqc"]["result"]["ciphertext_sha256"]!=first
            assert data["pqc"]["result"]["payload_tamper_rejected"]
            assert data["conway"]["result"]["board"]=="000000001c000000"
            if args.live_rpc:
                page.locator("#rpc").click()
                expect(page.locator("#chain-title")).to_have_text("Connected",timeout=30000)
                assert page.locator("#chain-id").inner_text()=="11155111"
                data=json.loads(page.locator("#evidence").inner_text())
            page.screenshot(path=str(reports/"wasm-desktop.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(reports/"wasm-mobile.png"),full_page=True)
            assert not errors,errors
            browser.close()
        (reports/"wasm-browser.json").write_text(json.dumps({"status":"passed","url":args.url,"live_rpc_requested":args.live_rpc,"evidence":data},indent=2)+"\n",encoding="utf-8")
        print("Rust/WASM browser checks passed at",args.url)
    finally:
        if server:server.shutdown();server.server_close()
if __name__=="__main__":main()
