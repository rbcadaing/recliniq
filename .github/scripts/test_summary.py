"""Append test and coverage totals to the GitHub job summary (US-00.4).

    python3 .github/scripts/test_summary.py <title> <junit.xml> <coverage.xml>

Both files are optional: a missing file (e.g. a step failed earlier) is reported, not fatal.
Coverage files are Cobertura XML (pytest-cov and vitest both write it); totals come from the
root ``line-rate`` attribute. Uses only the standard library so it runs on a bare runner.
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def junit_totals(path: Path) -> str:
    if not path.exists():
        return "no test report (tests did not run)"
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = failures = errors = skipped = 0
    for suite in suites:
        total += int(suite.get("tests", 0))
        failures += int(suite.get("failures", 0))
        errors += int(suite.get("errors", 0))
        skipped += int(suite.get("skipped", 0))
    passed = total - failures - errors - skipped
    return f"{passed} passed, {failures + errors} failed, {skipped} skipped ({total} total)"


def line_coverage(path: Path) -> str:
    if not path.exists():
        return "no coverage report"
    rate = float(ET.parse(path).getroot().get("line-rate", 0))
    return f"{rate * 100:.1f}% lines"


def main() -> int:
    title, junit, coverage = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    lines = [
        f"### {title}",
        "",
        "| Tests | Coverage |",
        "|---|---|",
        f"| {junit_totals(junit)} | {line_coverage(coverage)} |",
        "",
    ]
    text = "\n".join(lines) + "\n"
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
