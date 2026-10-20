"""Compatibility entrypoint: executes actual tests, and exits nonzero on failure."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    ["cargo","test","--workspace","--locked"],
    ["cargo","run","--quiet","--locked","--","self-check"],
    [sys.executable,"-m","unittest","discover","-s","tests","-p","test_*.py","-v"],
]
def main():
    for command in COMMANDS:
        print("RUN:", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    print("Local Rust and Python checks passed. RPC and contract tests are separate checks.")
    return 0
if __name__ == "__main__":
    sys.exit(main())
