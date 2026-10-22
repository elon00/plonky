"""Fail for high/critical CodeQL security findings, errors or invalid SARIF."""
import argparse
import json
import math
from pathlib import Path

EXPECTED_LANGUAGES = frozenset(("python", "javascript"))
SUPPORTED_LANGUAGES = EXPECTED_LANGUAGES | frozenset(("rust", "actions"))


def inspect(folder, expected_languages=EXPECTED_LANGUAGES):
    languages = set()
    blocking = 0
    for path in sorted(folder.glob("*.sarif")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("version") != "2.1.0" or not isinstance(document.get("runs"), list) or not document["runs"]:
            raise ValueError("Invalid SARIF document")
        for run in document["runs"]:
            if any(item.get("executionSuccessful") is False for item in run.get("invocations", [])):
                raise ValueError("Incomplete CodeQL execution")
            driver = run["tool"]["driver"]
            name = driver["name"]
            if name not in ("CodeQL", "CodeQL Command Line Toolchain"):
                raise ValueError("Unexpected analysis tool")
            rule_list = driver.get("rules", [])
            for extension in run["tool"].get("extensions", []):
                rule_list = rule_list + extension.get("rules", [])
            rules = {rule["id"]: rule for rule in rule_list}
            language = run.get("automationDetails", {}).get("id", "")
            if "python" in language:
                languages.add("python")
            elif "javascript" in language:
                languages.add("javascript")
            elif "rust" in language:
                languages.add("rust")
            elif "actions" in language:
                languages.add("actions")
            else:
                # CodeQL emits language-named files when no category is supplied.
                if path.stem in SUPPORTED_LANGUAGES:
                    languages.add(path.stem)
                else:
                    raise ValueError("Unidentified CodeQL language")
            results = run.get("results")
            if not isinstance(results, list):
                raise ValueError("Missing SARIF result list")
            for result in results:
                rule = rules.get(result.get("ruleId"))
                if not isinstance(rule, dict):
                    raise ValueError("Unknown SARIF rule")
                severity = rule.get("properties", {}).get("security-severity")
                if severity is not None:
                    score = float(severity)
                    if not math.isfinite(score) or not 0 <= score <= 10:
                        raise ValueError("Invalid security severity")
                else:
                    score = 0
                level = result.get("level", rule.get("defaultConfiguration", {}).get("level", "warning"))
                # Existing findings and SARIF suppressions do not bypass this release policy.
                if score >= 7 or level == "error":
                    blocking += 1
                    print("Blocking CodeQL rule: " + str(result.get("ruleId", ""))[:160])
    if languages != expected_languages:
        raise ValueError("All configured language analyses are required")
    return blocking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("reports/codeql"))
    parser.add_argument("--languages", nargs="+", choices=("python", "javascript-typescript", "rust", "actions"),
                        default=("python", "javascript-typescript"))
    args = parser.parse_args()
    try:
        expected = frozenset(value.replace("-typescript", "") for value in args.languages)
        count = inspect(args.directory, expected)
    except (OSError, ValueError, TypeError, KeyError):
        print("CodeQL gate failed: incomplete or invalid analysis evidence")
        return 1
    print("CodeQL blocking findings: " + str(count))
    return 1 if count else 0


if __name__ == "__main__":
    raise SystemExit(main())
