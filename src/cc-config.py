#!/usr/bin/env python3
"""
cc-config.py — tiny state mutator for the menu-bar plugin's interactive actions.

Called by SwiftBar menu items (never by Claude Code). Subcommands:

    cc-config.py pin <project>        toggle which project is featured in the bar
    cc-config.py filter               toggle "show pinned project only"
    cc-config.py clear <session_id>   delete one session's state file
    cc-config.py clearstale [seconds] delete sessions idle longer than N (def 1800)

Config lives at ~/.claude/status/config.json and is read by claude.2s.py.
"""
import sys
import os
import json
import time
import glob
import subprocess

STATUS_DIR = os.path.expanduser("~/.claude/status")
CONFIG = os.path.join(STATUS_DIR, "config.json")


def load():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return {}


def save(cfg):
    os.makedirs(STATUS_DIR, exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f)
    os.replace(tmp, CONFIG)


def safe_name(name):
    return "".join(c for c in name if c.isalnum() or c in "-_")


def clear_stale(threshold):
    now = time.time()
    for path in glob.glob(os.path.join(STATUS_DIR, "*.json")):
        if os.path.basename(path) == "config.json":
            continue
        try:
            with open(path) as f:
                s = json.load(f)
        except Exception:
            continue
        if now - s.get("updated_at", 0) > threshold:
            try:
                os.unlink(path)
            except OSError:
                pass


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    cfg = load()

    if cmd == "pin":
        cfg["primary"] = "" if cfg.get("primary") == arg else arg
    elif cmd == "filter":
        cfg["filter"] = not cfg.get("filter", False)
    elif cmd == "clear" and arg:
        path = os.path.join(STATUS_DIR, f"{safe_name(arg)}.json")
        try:
            os.unlink(path)
        except OSError:
            pass
    elif cmd == "clearstale":
        try:
            threshold = int(arg)
        except (ValueError, TypeError):
            threshold = 1800
        clear_stale(threshold)

    save(cfg)

    # Nudge SwiftBar so the change shows instantly instead of on the next tick.
    try:
        subprocess.run(
            ["/usr/bin/open", "swiftbar://refreshplugin?name=claude"],
            timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
