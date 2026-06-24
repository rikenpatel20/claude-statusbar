#!/usr/bin/env python3
"""
cc-statusline.py — Claude Code status line that also records token/cost data.

Claude Code calls this on every status-line refresh and passes a JSON payload
on stdin. This script does two things:

  1. Prints the status line shown inside Claude Code (model · project · ctx · $).
  2. Writes live token + cost numbers into ~/.claude/status/<session>.json so the
     menu-bar app can show them, WITHOUT clobbering the status written by hooks.

Context-token usage is read from the last `usage` block in the session
transcript (input + output + cache tokens) — i.e. how full the context window
currently is. Only the tail of the transcript is read, so this stays cheap even
for long sessions.

Composition with an existing status line:

    cc-statusline.py --chain ~/.claude/statusline.sh   # record, then show yours
    cc-statusline.py --record-only                     # record, print nothing

With --chain, the original stdin payload is forwarded to your script and its
output is what Claude Code displays — so this records data for the menu bar
without changing your status line at all.

This script always prints *something* (unless --record-only) so the status line
never goes blank, and never raises even if the state directory is unwritable.
"""
import sys
import os
import json
import time
import tempfile
import subprocess
import shlex
from collections import deque

STATUS_DIR = os.path.expanduser("~/.claude/status")
TRANSCRIPT_TAIL_LINES = 400


def last_usage(transcript_path):
    """Return the most recent token-usage dict from the transcript, or None."""
    try:
        with open(transcript_path) as f:
            tail = deque(f, maxlen=TRANSCRIPT_TAIL_LINES)
    except Exception:
        return None
    for line in reversed(tail):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        usage = None
        if isinstance(msg, dict):
            usage = msg.get("usage")
        if usage is None and isinstance(obj, dict):
            usage = obj.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


def find_tty():
    """Walk up the process tree to the first ancestor with a controlling tty."""
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
    """Record TERM_PROGRAM + tty once per session (skipped once known)."""
    if not state.get("term"):
        term = os.environ.get("TERM_PROGRAM", "")
        if term:
            state["term"] = term
    if not state.get("tty"):
        tty = find_tty()
        if tty:
            state["tty"] = tty


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


def record(data, model, project, cwd, cost, tokens):
    sid = str(data.get("session_id") or "unknown")
    safe_sid = "".join(c for c in sid if c.isalnum() or c in "-_") or "unknown"
    os.makedirs(STATUS_DIR, exist_ok=True)
    path = os.path.join(STATUS_DIR, f"{safe_sid}.json")

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
        "model": model,
        "tokens": tokens,
        "cost_usd": round(cost, 4),
        "updated_at": int(time.time()),
    })
    # Never overwrite a status set by a hook; only seed one if missing.
    state.setdefault("status", "working")
    add_terminal_info(state)
    atomic_write(path, state)


def parse_args(argv):
    chain = None
    record_only = False
    i = 0
    while i < len(argv):
        if argv[i] == "--chain" and i + 1 < len(argv):
            chain = argv[i + 1]
            i += 2
        elif argv[i] == "--record-only":
            record_only = True
            i += 1
        else:
            i += 1
    return chain, record_only


def run_chain(command, raw_stdin):
    """Forward the raw payload to an existing status-line command; return stdout."""
    cmd = os.path.expanduser(command)
    argv = [cmd] if os.path.exists(cmd) else shlex.split(command)
    try:
        proc = subprocess.run(
            argv, input=raw_stdin, capture_output=True, text=True, timeout=5
        )
        return proc.stdout.rstrip("\n")
    except Exception:
        return None


def main():
    chain, record_only = parse_args(sys.argv[1:])
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    model = (data.get("model") or {}).get("display_name", "Claude")
    workspace = data.get("workspace") or {}
    cwd = workspace.get("current_dir") or data.get("cwd") or os.getcwd()
    project = os.path.basename(cwd.rstrip("/")) or cwd
    cost = (data.get("cost") or {}).get("total_cost_usd", 0.0) or 0.0
    transcript_path = data.get("transcript_path", "")

    tokens = 0
    usage = last_usage(transcript_path) if transcript_path else None
    if usage:
        tokens = (
            usage.get("input_tokens", 0)
            + usage.get("output_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )

    # Record state, but never let a write failure blank the status line.
    try:
        record(data, model, project, cwd, cost, tokens)
    except Exception:
        pass

    if record_only:
        return

    if chain:
        out = run_chain(chain, raw)
        if out is not None:
            print(out)
            return
        # fall through to our default line if the chained command failed

    ctx_k = tokens / 1000
    print(f"{model} · {project} · {ctx_k:.0f}k ctx · ${cost:.2f}")


if __name__ == "__main__":
    main()
