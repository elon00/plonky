#!/usr/bin/env python3
"""Build the same Rust core for static HTTPS hosting. No server or secrets required."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
ROOT=Path(__file__).resolve().parents[1]
def run(args,env=None):
    print("RUN:"," ".join(args),flush=True)
    subprocess.run(args,cwd=ROOT,env=env,check=True)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-tools",action="store_true")
    args=parser.parse_args()
    lock=tomllib.loads((ROOT/"Cargo.lock").read_text(encoding="utf-8"))
    version=next(x["version"] for x in lock["package"] if x["name"]=="wasm-bindgen")
    if args.install_tools:
        run(["rustup","target","add","wasm32-unknown-unknown"])
        existing=subprocess.run(["wasm-bindgen","--version"],capture_output=True,text=True) if shutil.which("wasm-bindgen") else None
        if existing is None or existing.stdout.strip()!="wasm-bindgen "+version:
            run(["cargo","install","wasm-bindgen-cli","--version",version,"--locked"])
    run(["npm.cmd" if os.name=="nt" else "npm","run","build"])
    env=dict(os.environ)
    env["CARGO_TARGET_WASM32_UNKNOWN_UNKNOWN_RUSTFLAGS"]='--cfg getrandom_backend="wasm_js"'
    run(["cargo","build","--package","qmoosa-wasm","--release","--target","wasm32-unknown-unknown","--locked"],env)
    site=ROOT/"site";site.mkdir(exist_ok=True)
    for name in ("app.js","style.css","bootstrap.js"):shutil.copy2(ROOT/"web"/name,site/name)
    html=(ROOT/"web/index.html").read_text(encoding="utf-8")
    html=html.replace('src="./app.js" defer','src="./bootstrap.js" type="module"')
    # Browser-generated WASM is explicitly allowed; no general unsafe-eval.
    policy="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self' https://ethereum-sepolia-rpc.publicnode.com; img-src 'self'; base-uri 'none'; form-action 'none'"
    html=html.replace('<meta name="viewport"',f'<meta http-equiv="Content-Security-Policy" content="{policy}"><meta name="viewport"')
    (site/"index.html").write_text(html,encoding="utf-8")
    (site/".nojekyll").write_text("")
    shutil.copy2(ROOT/"project.json",site/"project.json")
    (site/"sdk").mkdir(exist_ok=True);shutil.copy2(ROOT/"dist/index.js",site/"sdk/index.js")
    shutil.copy2(ROOT/"dist/chain-upgrades.js",site/"sdk/chain-upgrades.js")
    target=Path(os.environ.get("CARGO_TARGET_DIR",ROOT/"target"))
    if not target.is_absolute():target=ROOT/target
    run(["wasm-bindgen","--target","web","--out-dir",str(site/"pkg"),str(target/"wasm32-unknown-unknown/release/qmoosa_wasm.wasm")])
    print("Static site built at",site,flush=True)
if __name__=="__main__":main()
