#!/usr/bin/env python3
"""Check every import in the package against the allow-list in layers.json.

Each package file belongs to one layer (longest ``paths`` prefix wins). Every
import anywhere in it (nested, relative, importlib.import_module / __import__
with a literal) must be allowed by the layer's ``internal`` layers or its
``modules`` allow-list (stdlib too). Exit 0 = OK, 1 = violations, 2 = bad config.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

LAYER_KEYS = ("paths", "internal", "modules")
ROOT_LAYER = "app"  # layer for the bare package root when no path claims it
DYNAMIC_FUNCS = {"__import__", "import_module"}


class ConfigError(Exception):
    pass


def load_config(path: Path) -> dict:
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot load {path}: {exc}") from None
    if not isinstance(cfg, dict):
        raise ConfigError(f"{path}: top level must be an object")
    if not isinstance(cfg.get("package"), str) or not cfg["package"]:
        raise ConfigError(f"{path}: missing or invalid key 'package' (string)")
    layers = cfg.get("layers")
    if not isinstance(layers, dict) or not layers:
        raise ConfigError(f"{path}: missing or empty key 'layers' (object)")
    for name, spec in layers.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"{path}: layer '{name}' must be an object")
        for key in LAYER_KEYS:
            val = spec.get(key)
            if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
                raise ConfigError(f"{path}: layer '{name}' missing or invalid key "
                                  f"'{key}' (list of strings)")
        unknown = [n for n in spec["internal"] if n not in layers]
        if unknown:
            raise ConfigError(f"{path}: layer '{name}' lists unknown internal "
                              f"layer(s): {', '.join(unknown)}")
    return cfg


def layer_for_path(rel: str, cfg: dict) -> str | None:
    """Layer owning repo-relative posix path ``rel``; longest prefix wins."""
    best, best_len = None, -1
    for name, spec in cfg["layers"].items():
        for prefix in spec["paths"]:
            prefix = prefix.rstrip("/")
            if (rel == prefix or rel.startswith(prefix + "/")) and len(prefix) > best_len:
                best, best_len = name, len(prefix)
    return best


def layer_for_module(module: str, cfg: dict) -> str | None:
    rel = module.replace(".", "/")
    for cand in (rel, rel + ".py", rel + "/__init__.py"):
        layer = layer_for_path(cand, cfg)
        if layer is not None:
            return layer
    return ROOT_LAYER if module == cfg["package"] else None


def file_package(rel: str) -> list[str]:
    """Dotted package a file lives in (for __init__.py, the package itself)."""
    return rel[:-3].split("/")[:-1]


def resolve_relative(pkg: list[str], level: int, module: str | None) -> str | None:
    if level - 1 >= len(pkg):
        return None
    base = pkg[: len(pkg) - (level - 1)]
    return ".".join(base + ([module] if module else []))


def _dynamic_arg(call: ast.Call) -> ast.expr | None:
    return call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "name"), None)


def collect_imports(tree: ast.AST, pkg: list[str]):
    """Yield (lineno, module, names) for every import; module is None for an
    unresolvable import and names is None for a non-literal dynamic import."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, ()
        elif isinstance(node, ast.ImportFrom):
            mod = resolve_relative(pkg, node.level, node.module) if node.level else node.module
            yield node.lineno, mod, tuple(a.name for a in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            fname = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if fname not in DYNAMIC_FUNCS:
                continue
            arg = _dynamic_arg(node)
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                name = arg.value
                if name.startswith("."):
                    level = len(name) - len(name.lstrip("."))
                    yield node.lineno, resolve_relative(pkg, level, name[level:] or None), ()
                else:
                    yield node.lineno, name, ()
            else:
                yield node.lineno, fname, None


def check_import(layer: str, module: str, names: tuple, cfg: dict) -> list[str]:
    """Return the offending module names for one import statement."""
    spec = cfg["layers"][layer]
    package = cfg["package"]
    if module.split(".")[0] != package:
        top = module.split(".")[0]
        return [] if top in spec["modules"] else [module]
    targets = []
    if module == package and names:
        for name in names:
            if name == "__version__":
                continue
            sub = f"{package}.{name}"
            targets.append((sub, layer_for_module(sub, cfg) or layer_for_module(package, cfg)))
    else:
        targets.append((module, layer_for_module(module, cfg)))
    return [m for m, t in targets if t is None or t not in spec["internal"]]


def check_file(path: Path, rel: str, cfg: dict) -> list[str]:
    layer = layer_for_path(rel, cfg)
    if layer is None:
        return [f"{rel}:1: file is not assigned to any layer in layers.json"]
    try:
        tree = ast.parse(path.read_bytes(), filename=rel)
    except SyntaxError as exc:
        return [f"{rel}:{exc.lineno or 1}: syntax error: {exc.msg}"]
    out = []
    for lineno, module, names in collect_imports(tree, file_package(rel)):
        if names is None:
            if layer != "app":
                out.append(f"{rel}:{lineno}: [{layer}] dynamic import via {module}() "
                           f"with a non-literal name (cannot be checked)")
        elif module is None:
            out.append(f"{rel}:{lineno}: [{layer}] relative import beyond the package root")
        else:
            for bad in check_import(layer, module, names, cfg):
                out.append(f"{rel}:{lineno}: [{layer}] imports '{bad}' (not allowed)")
    return out


def iter_package_files(root: Path, package: str) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root / package):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__" and d[0] != ".")
        files.extend(Path(dirpath) / f for f in sorted(filenames) if f.endswith(".py"))
    return files


def run(root: Path, config: Path) -> int:
    try:
        cfg = load_config(config)
    except ConfigError as exc:
        print(f"check_layers: config error: {exc}")
        return 2
    if not (root / cfg["package"]).is_dir():
        print(f"check_layers: package directory '{cfg['package']}/' not found under {root}")
        return 2
    files = iter_package_files(root, cfg["package"])
    problems = []
    for path in files:
        problems.extend(check_file(path, path.relative_to(root).as_posix(), cfg))
    if problems:
        print("\n".join(problems))
        print(f"check_layers: {len(problems)} violation(s) in {len(files)} files")
        return 1
    print(f"check_layers: OK ({len(files)} files, {len(cfg['layers'])} layers)")
    return 0


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=here.parent,
                        help="repository root (default: parent of scripts/)")
    parser.add_argument("--config", type=Path, default=here / "layers.json",
                        help="layers.json path (default: scripts/layers.json)")
    args = parser.parse_args(argv)
    return run(args.root.resolve(), args.config)


if __name__ == "__main__":
    sys.exit(main())
