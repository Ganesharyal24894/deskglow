#!/usr/bin/env python3
"""Fail if any Python file is longer than the line limit.

Usage: python scripts/check_lines.py [--limit N] [--root DIR] [PATH ...]

PATHs are directories or files relative to --root (default: the parent of
this scripts/ directory). Missing paths are ignored, so optional files such
as hatch_build.py only count when they exist. Stdlib only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_LIMIT = 200
DEFAULT_PATHS = ("deskglow", "tests", "scripts", "tools", "hatch_build.py")
SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules"}


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def iter_py_files(root: Path, paths: list[str]) -> list[Path]:
    """Every .py file under ``paths`` (relative to ``root``), sorted."""
    found: set[Path] = set()
    for rel in paths:
        target = root / rel
        if target.is_file():
            if target.suffix == ".py":
                found.add(target)
            continue
        if not target.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
            for name in filenames:
                if name.endswith(".py"):
                    found.add(Path(dirpath) / name)
    return sorted(found)


def count_lines(path: Path) -> int:
    with open(path, "rb") as fh:
        data = fh.read()
    return len(data.splitlines())


def find_violations(root: Path, paths: list[str], limit: int) -> tuple[list[str], int]:
    """Return (["rel/path.py:NNN", ...], files_checked)."""
    files = iter_py_files(root, paths)
    bad = []
    for path in files:
        n = count_lines(path)
        if n > limit:
            bad.append(f"{path.relative_to(root).as_posix()}:{n}")
    return bad, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", default=list(DEFAULT_PATHS),
                        help="directories/files to check, relative to --root")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"maximum lines per file (default {DEFAULT_LIMIT})")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository root (default: parent of scripts/)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    bad, checked = find_violations(root, args.paths, args.limit)
    if bad:
        print(f"check_lines: {len(bad)} file(s) over {args.limit} lines:")
        for item in bad:
            print(f"  {item}")
        return 1
    print(f"check_lines: OK ({checked} files, limit {args.limit})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
