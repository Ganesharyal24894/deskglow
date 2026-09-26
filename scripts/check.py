#!/usr/bin/env python3
"""Run every project check, then summarise. Work is not done until this passes.

Usage: python scripts/check.py [--fast]

Steps: line limit, layer allow-list, preset freshness, ruff, pytest. Every
step runs even if an earlier one fails; the exit code is 1 if any failed.
All sub-commands use the running interpreter (sys.executable), so this works
the same in any virtualenv on Linux, macOS and Windows.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple
from collections.abc import Callable

ROOT = Path(__file__).resolve().parent.parent


class Step(NamedTuple):
    name: str
    cmd: list | None  # None => skipped
    skip_reason: str = ""


class Result(NamedTuple):
    name: str
    status: str  # "PASS" | "FAIL" | "SKIPPED"
    detail: str = ""


def build_steps(root: Path = ROOT, fast: bool = False) -> list:
    py = sys.executable
    scripts = root / "scripts"
    steps = [
        Step("line limit", [py, str(scripts / "check_lines.py"), "--root", str(root)]),
        Step("layers", [py, str(scripts / "check_layers.py"), "--root", str(root)]),
    ]
    gen = scripts / "gen_presets.py"
    if gen.is_file():
        steps.append(Step("presets", [py, str(gen), "--check"]))
    else:
        steps.append(Step("presets", None, "not present"))
    steps.append(Step("ruff", [py, "-m", "ruff", "check", "."]))
    if fast:
        steps.append(Step("pytest", None, "--fast"))
    else:
        steps.append(Step("pytest", [py, "-m", "pytest", "-q"]))
    return steps


def _run_cmd(cmd: list, cwd: Path) -> int:
    try:
        return subprocess.run(cmd, cwd=str(cwd)).returncode
    except OSError as exc:
        print(f"  could not start {cmd[0]}: {exc}")
        return 127


def run_steps(steps: list, cwd: Path = ROOT,
              runner: Callable[[list, Path], int] = _run_cmd) -> list:
    results = []
    for step in steps:
        print(f"\n=== {step.name} ===", flush=True)
        if step.cmd is None:
            print(f"SKIPPED ({step.skip_reason})")
            results.append(Result(step.name, "SKIPPED", step.skip_reason))
            continue
        start = time.monotonic()
        code = runner(step.cmd, cwd)
        took = f"{time.monotonic() - start:.1f}s"
        status = "PASS" if code == 0 else "FAIL"
        detail = took if code == 0 else f"exit {code}, {took}"
        results.append(Result(step.name, status, detail))
    return results


def summarise(results: list) -> int:
    print("\n=== summary ===")
    width = max((len(r.name) for r in results), default=0)
    for r in results:
        extra = f" ({r.detail})" if r.detail else ""
        print(f"  {r.name.ljust(width)}  {r.status}{extra}")
    failed = [r.name for r in results if r.status == "FAIL"]
    if failed:
        print(f"check: FAILED ({', '.join(failed)})")
        return 1
    print("check: all steps passed")
    return 0


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="skip pytest")
    args = parser.parse_args(argv)
    return summarise(run_steps(build_steps(ROOT, fast=args.fast), ROOT))


if __name__ == "__main__":
    sys.exit(main())
