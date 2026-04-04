#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PYTHON_ROOT = Path(__file__).resolve().parents[2] / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.shared.bootstrap import bootstrap_app
from modules.shared.plugin_manager import PluginManager


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage LS runtime plugins")
    parser.add_argument("command", choices=["list", "load", "reload", "unload"], help="Plugin command")
    parser.add_argument("plugin", nargs="?", help="Plugin name for reload/unload")
    parser.add_argument("--path", dest="path", help="Plugin file path for load")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    ctx = bootstrap_app(__file__, "console")
    manager = PluginManager(ctx)

    if args.command == "list":
        loaded_now = manager.load_all()
        print("discovered+loaded:", ", ".join(loaded_now) if loaded_now else "<none>")
        print("loaded:", ", ".join(manager.list_loaded()) if manager.list_loaded() else "<none>")
        return 0

    if args.command == "load":
        if not args.path:
            parser.error("load requires --path <plugin_file>")
        name = manager.load_from_path(Path(args.path))
        print(f"loaded: {name}" if name else "load failed")
        return 0 if name else 1

    if args.command == "reload":
        if not args.plugin:
            parser.error("reload requires <plugin>")
        manager.load_all()
        result = manager.reload(args.plugin)
        print(f"reloaded: {result}" if result else "reload failed")
        return 0 if result else 1

    if args.command == "unload":
        if not args.plugin:
            parser.error("unload requires <plugin>")
        manager.load_all()
        manager.unload(args.plugin)
        print(f"unloaded: {args.plugin}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
