#!/usr/bin/env python3
"""
cc-status.py — Claude Code hook that records session status to a state file.

Invoked by Claude Code hooks. Reads the hook JSON payload on stdin and takes a
single status argument:

    cc-status.py needs-attention   # Notification hook (waiting on you)
    cc-status.py working           # UserPromptSubmit / PostToolUse hook
    cc-status.py done              # Stop hook
    cc-status.py end               # SessionEnd hook (removes the state file)

It writes/merges ~/.claude/status/<session_id>.json so any front-end
(menu bar, tmux, waybar, web) can read a single documented state file.

When a session flips to `needs-attention` it also fires a native macOS
notification at that exact moment — so you never have to babysit the prompt.

Design notes:
  * Writes are atomic (temp file + os.replace) so a front-end never reads a
    half-written file.
  * Token/cost fields written by cc-statusline.py are preserved across status
    transitions (we merge, never blindly overwrite).
  * Stale state files (older than PRUNE_SECONDS) are removed opportunistically.
  * The script never raises into Claude Code: any failure exits 0 silently so a
    hook can never break the user's session.
"""
import sys
import os
import json
import time
import tempfile
import subprocess

STATUS_DIR = os.path.expanduser("~/.claude/status")
PRUNE_SECONDS = 24 * 3600
VALID_STATUSES = {"needs-attention", "working", "done", "idle", "end"}
NOTIFY_ON_DONE = os.environ.get("CC_NOTIFY_ON_DONE", "0") == "1"
NOTIFY_SOUND = os.environ.get("CC_NOTIFY_SOUND", "Glass")


def read_payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def find_tty():
    """Walk up the process tree to the first ancestor with a controlling tty.

    Hooks are often run without a controlling terminal of their own, but a
    parent (the `claude` process / shell) still owns the terminal's tty.
    Returns a path like "/dev/ttys004", or "" if none is found.
    """
    pid = os.getpid()
    for _ in range(12):
        try:
            out = subprocess.run(
                ["/bin/ps", "-o", "ppid=,tty=", "-p", str(pid)],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
        except Exception:
            return ""
        if not out:
            return ""
        parts = out.split(None, 1)
        try:
            ppid = int(parts[0])
        except (ValueError, IndexError):
            return ""
        tty = parts[1].strip() if len(parts) > 1 else ""
        if tty and tty not in ("??", "?", "-"):
            return tty if tty.startswith("/dev/") else "/dev/" + tty
        if ppid <= 1:
            return ""
        pid = ppid
    return ""


def add_terminal_info(state):
    """Record TERM_PROGRAM + tty once per session (cheap: skipped once known)."""
    if not state.get("term"):
        term = os.environ.get("TERM_PROGRAM", "")
        if term:
            state["term"] = term
    if not state.get("tty"):
        tty = find_tty()
        if tty:
            state["tty"] = tty


def notify(title, body, sound):
    """Fire a native macOS notification. No-op off macOS / on any failure."""
    osascript = "/usr/bin/osascript"
    if not os.path.exists(osascript):
        return

    def esc(s):
        # AppleScript double-quoted string: backslash and quote are the only
        # characters that can break out. Clamp length to keep banners sane.
        return str(s).replace("\\", "\\\\").replace('"', '\\"')[:200]

    script = (
        f'display notification "{esc(body)}" '
        f'with title "{esc(title)}" sound name "{esc(sound)}"'
    )
    try:
        subprocess.Popen(
            [osascript, "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def atomic_write(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def prune_stale():
    cutoff = time.time() - PRUNE_SECONDS
    try:
        entries = os.listdir(STATUS_DIR)
    except OSError:
        return
    for name in entries:
        if not name.endswith(".json"):
            continue
        path = os.path.join(STATUS_DIR, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.unlink(path)
        except OSError:
            pass


def run():
    status = sys.argv[1] if len(sys.argv) > 1 else "working"
    if status not in VALID_STATUSES:
        status = "working"

    data = read_payload()
    sid = str(data.get("session_id") or "unknown")
    # Defend against path traversal from an unexpected session_id value.
    safe_sid = "".join(c for c in sid if c.isalnum() or c in "-_") or "unknown"
    cwd = data.get("cwd") or os.getcwd()
    project = os.path.basename(cwd.rstrip("/")) or cwd
    message = data.get("message", "")

    # Claude Code's Notification event fires both for real permission prompts AND
    # for plain idle ("Claude is waiting for your input") after a turn finishes.
    # Only the former is an action item; the latter is just a session waiting for
    # the next prompt, so downgrade it to done (green, no red, no alarm).
    if status == "needs-attention":
        m = message.lower()
        if "waiting for your input" in m or "waiting for input" in m:
            status, message = "done", ""

    os.makedirs(STATUS_DIR, exist_ok=True)
    path = os.path.join(STATUS_DIR, f"{safe_sid}.json")

    # SessionEnd: remove the file and we're done.
    if status == "end":
        try:
            os.unlink(path)
        except OSError:
            pass
        prune_stale()
        return

    # Merge with existing so token/cost fields from the status line survive.
    state = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                state = json.load(f)
        except Exception:
            state = {}

    state.update({
        "session_id": sid,
        "project": project,
        "cwd": cwd,
        "status": status,
        "message": message,
        "updated_at": int(time.time()),
    })
    add_terminal_info(state)

    atomic_write(path, state)
    prune_stale()

    if status == "needs-attention":
        notify(f"Claude Code · {project}", message or "Needs your attention", NOTIFY_SOUND)
    elif status == "done" and NOTIFY_ON_DONE:
        notify(f"Claude Code · {project}", "Finished — ready for you", "Tink")


def main():
    try:
        run()
    except Exception:
        # A hook must never break the user's Claude Code session.
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
