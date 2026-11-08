"""Run lint and every test suite (components, services, frontend) and summarise.

Each package runs in its own pytest process because every service has its own
import root. Components must keep line coverage >= 80%.

Usage (inside the tools container): ``python scripts/run_tests.py [--only NAME]``
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "docs" / "relatorio" / "generated" / "test-summary.json"
COMPONENT_MIN_COVERAGE = 80


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run ``cmd`` streaming its output; return exit code and captured text."""
    env = {**os.environ, "COVERAGE_FILE": "/tmp/.coverage", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    print(output)
    return proc.returncode, output


def parse_pytest(output: str) -> dict[str, object]:
    """Extract passed/failed counts and total coverage from pytest output."""
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    cover = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", output, re.MULTILINE)
    return {
        "passed": int(passed.group(1)) if passed else 0,
        "failed": int(failed.group(1)) if failed else 0,
        "coverage": int(cover.group(1)) if cover else None,
    }


def packages() -> list[tuple[str, str, Path]]:
    """List (kind, name, path) of every testable package."""
    found = [
        ("component", p.name, p)
        for p in sorted((ROOT / "components").iterdir())
        if (p / "tests").is_dir()
    ]
    found += [
        ("service", p.name, p)
        for p in sorted((ROOT / "services").iterdir())
        if (p / "tests").is_dir()
    ]
    web = ROOT / "frontend" / "web"
    if (web / "tests").is_dir():
        found.append(("frontend", "web-frontend", web))
    return found


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run a single package by name")
    parser.add_argument("--no-lint", action="store_true")
    args = parser.parse_args()

    results: list[dict[str, object]] = []
    failures = 0
    if not args.no_lint and not args.only:
        code_check, _ = run(["ruff", "check", "--no-cache", "."], ROOT)
        code_format, _ = run(["ruff", "format", "--no-cache", "--check", "."], ROOT)
        results.append({"kind": "lint", "name": "ruff", "ok": code_check == 0 and code_format == 0})
        failures += int(code_check != 0) + int(code_format != 0)

    for kind, name, path in packages():
        if args.only and args.only != name:
            continue
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        cmd += [f"--cov-config={ROOT / 'pyproject.toml'}"]
        if kind == "component":
            cmd += [
                f"--cov={name}",
                "--cov-report=term",
                f"--cov-fail-under={COMPONENT_MIN_COVERAGE}",
            ]
        else:
            module = name.replace("-", "_") if kind == "service" else "web_frontend"
            cmd += [f"--cov={module}", "--cov-report=term"]
        started = time.time()
        code, output = run(cmd, path)
        stats = parse_pytest(output)
        results.append(
            {
                "kind": kind,
                "name": name,
                "ok": code == 0,
                "seconds": round(time.time() - started, 1),
                **stats,
            }
        )
        failures += int(code != 0)

    print("\n=== Resumo ===")
    for r in results:
        mark = "OK " if r["ok"] else "FALHOU"
        extra = (
            f"{r.get('passed', '')} passed, cobertura {r.get('coverage')}%"
            if r["kind"] != "lint"
            else ""
        )
        print(f"[{mark}] {r['kind']:<9} {r['name']:<24} {extra}")
    if not args.only:
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
