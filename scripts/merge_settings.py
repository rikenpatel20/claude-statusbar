#!/usr/bin/env python3
"""
merge_settings.py — safely merge the claude-statusbar snippet into a user's
~/.claude/settings.json without clobbering existing config.

    merge_settings.py <settings.json> <snippet.json>

Rules:
  * A timestamped backup of the existing settings file is written first.
  * `statusLine` is only set if absent (we never replace a status line the user
    already configured — we warn instead).
  * Hook arrays are merged additively and de-duplicated by command string, so
    re-running the installer is idempotent.
"""
import sys
import os
import json
import time
import shutil


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def merge_hooks(existing, incoming):
    """Merge { event: [ {matcher?, hooks:[...]} ] } additively, de-duped."""
    out = dict(existing)
    for event, blocks in incoming.items():
        existing_cmds = set()
        for blk in out.get(event, []):
            for h in blk.get("hooks", []):
                existing_cmds.add(h.get("command"))
        merged = list(out.get(event, []))
        for blk in blocks:
            new_hooks = [h for h in blk.get("hooks", []) if h.get("command") not in existing_cmds]
            if new_hooks:
                merged.append({**blk, "hooks": new_hooks})
        out[event] = merged
    return out


def main():
    if len(sys.argv) != 3:
        print("usage: merge_settings.py <settings.json> <snippet.json>", file=sys.stderr)
        sys.exit(2)

    settings_path, snippet_path = sys.argv[1], sys.argv[2]
    settings = load(settings_path)
    snippet = load(snippet_path)

    if os.path.exists(settings_path):
        backup = f"{settings_path}.bak-{int(time.time())}"
        shutil.copy2(settings_path, backup)
        print(f"    backup: {backup}")

    if "statusLine" in snippet:
        if "statusLine" in settings:
            print("    note: keeping your existing statusLine. To use this one, set "
                  "statusLine.command to ~/.claude/status/cc-statusline.py manually.")
        else:
            settings["statusLine"] = snippet["statusLine"]

    if "hooks" in snippet:
        settings["hooks"] = merge_hooks(settings.get("hooks", {}), snippet["hooks"])

    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"    wrote: {settings_path}")


if __name__ == "__main__":
    main()
