"""Optional browser QA: requires Playwright and a local Chromium/Edge installation."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
def main():
    from playwright.sync_api import sync_playwright, expect
    reports=ROOT/"reports";reports.mkdir(exist_ok=True)
    log=(reports/"browser-server.log").open("w")
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    process=subprocess.Popen([sys.executable,"app.py","serve","--port","8767"],cwd=ROOT,stdout=log,stderr=log,creationflags=flags)
    try:
        for _ in range(300):
            if process.poll() is not None:raise RuntimeError("Demo server failed; see browser-server.log")
            try:
                with urlopen("http://127.0.0.1:8767/api/health",timeout=1):break
            except OSError:time.sleep(.2)
        else:raise RuntimeError("Demo startup timed out")
        with sync_playwright() as runtime:
            edge=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser=runtime.chromium.launch(headless=True,**({"executable_path":str(edge)} if edge.exists() else {}))
            page=browser.new_page(viewport={"width":1440,"height":1060},device_scale_factor=1)
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto("http://127.0.0.1:8767",wait_until="networkidle")
            page.locator("#step").click();expect(page.locator("#generation")).to_have_text("1")
            page.locator("#step").click();expect(page.locator("#generation")).to_have_text("2")
            page.locator("#pqc").click();expect(page.locator("#pqc-status")).to_have_text(re.compile(r"^Exchange completed"))
            first=json.loads(page.locator("#evidence").inner_text())["pqc"]["result"]["ciphertext_sha256"]
            page.locator("#pqc").click();expect(page.locator("#pqc-status")).to_have_text(re.compile(r"^Exchange completed"))
            evidence=json.loads(page.locator("#evidence").inner_text())
            assert first!=evidence["pqc"]["result"]["ciphertext_sha256"]
            assert evidence["conway"]["result"]["board"]=="000000001c000000"
            assert evidence["pqc"]["result"]["payload_tamper_rejected"] is True
            page.locator("#rpc").click()
            expect(page.locator("#rpc")).to_be_enabled()
            assert page.locator("#chain-title").inner_text() in ("Not configured","Connected","Probe failed")
            page.screenshot(path=str(reports/"demo-desktop.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(reports/"demo-mobile.png"),full_page=True)
            assert not errors,errors
            browser.close()
        (reports/"browser-check.json").write_text(json.dumps({"status":"passed","checks":["blinker UI steps","real PQC roundtrip","fresh randomness","explicit RPC state","mobile layout","no browser exceptions"]},indent=2))
        print("Browser QA passed; desktop and mobile screenshots saved.")
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill()
        log.close()
if __name__=="__main__":main()
