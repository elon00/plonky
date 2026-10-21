"""Require every named CI dependency to succeed; skipped checks never pass."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

REQUIRED_JOBS = frozenset(("core", "contracts", "security", "credentials", "container", "web", "codeql"))


def evaluate(needs):
    if not isinstance(needs, dict) or set(needs) != REQUIRED_JOBS:
        return False
    return all(isinstance(value, dict) and value.get("result") == "success"
               for value in needs.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("reports/release-gate.json"))
    args = parser.parse_args()
    raw = os.environ.get("NEEDS_JSON", "")
    try:
        if len(raw) > 65536:
            raise ValueError("Oversized dependency metadata")
        needs = json.loads(raw)
    except (ValueError, TypeError):
        needs = None
    passed = evaluate(needs)
    report = {
        "status": "passed" if passed else "failed",
        "required_jobs": sorted(REQUIRED_JOBS),
        "results": {name: item.get("result") if isinstance(item, dict) else "invalid"
                    for name, item in needs.items()} if isinstance(needs, dict) else None,
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "CI dependencies only; not a production or market certification",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Required release gate: " + report["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
