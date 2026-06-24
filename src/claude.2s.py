#!/usr/bin/env python3
"""
claude.2s.py — SwiftBar plugin (reference front-end for claude-statusbar).

SwiftBar runs this every 2 seconds (the `.2s.` in the filename) and renders its
stdout in the macOS menu bar. It reads every ~/.claude/status/*.json file and
shows the status across all live Claude Code sessions.

Menu-bar icon:
  🔴 N   — N sessions need you (permission / idle prompt)
  🟡 N   — N sessions actively working
  🟢     — all idle / done
  (pin a project to show its live %/cost right in the bar text)

Interactivity:
  * Click a session row → focus that session's terminal window/tab (by tty).
  * "Show in menu bar" → feature that project in the bar.
  * "Filter to pinned" → show only the pinned project.
  * "Clear idle sessions" / per-session clear → drop stale entries.

A session shown as "working" but not updated in IDLE_AFTER seconds is treated as
idle — a genuinely working session refreshes its status line constantly, so
silence means it actually finished (and just never fired a Stop event).
"""
import os
import json
import glob
import time
import base64

STATUS_DIR = os.path.expanduser("~/.claude/status")
CONFIG = os.path.join(STATUS_DIR, "config.json")
FOCUS = os.path.expanduser("~/.claude/status/cc-focus.py")
CONF = os.path.expanduser("~/.claude/status/cc-config.py")
ICON = os.path.expanduser("~/.claude/status/menubar.png")
PY = "/usr/bin/python3"  # invoke scripts via python3, never `bash file.py`


def action(script, *params):
    """Build a SwiftBar click action that runs a python script.

    Using shell=python3 (not bash=script.py) is essential: bash= would try to
    interpret the Python file AS bash, fail, and fall back to *opening* the .py
    file — which launches your default editor (e.g. VS Code) instead of focusing
    the terminal.
    """
    parts = [f'shell="{PY}"', f'param1="{script}"']
    parts += [f'param{i + 2}="{p}"' for i, p in enumerate(params)]
    return " ".join(parts)

STALE_SECONDS = 6 * 3600     # hide entirely after this
IDLE_AFTER = 90              # "working" with no refresh past this == idle

RANK = {"needs-attention": 3, "working": 2, "idle": 1, "done": 1}
DOT = {"needs-attention": "🔴", "working": "🟡", "idle": "⚪", "done": "🟢"}

# Readable on both the translucent light and dark menu backgrounds.
MUTED = "#6B7280"   # secondary text (was too-faint #8A8A8E before)
RED = "#D14343"     # needs-attention / critical context
AMBER = "#C77700"
GREEN = "#1F8A4C"


def ctx_limit(model):
    return 1_000_000 if "1m" in (model or "").lower() else 200_000


def human(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{round(n / 1000)}k"
    return str(int(n))


def bar(pct, width=10):
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100 * width))
    return "▰" * filled + "▱" * (width - filled)


def usage_color(pct):
    if pct >= 85:
        return RED
    if pct >= 60:
        return AMBER
    return GREEN


def short_model(model):
    return (model or "Claude").replace(" (1M context)", " · 1M").replace("(1M context)", "1M")


def ago(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"


def effective_status(s, now):
    st = s.get("status", "idle")
    if st == "working" and now - s.get("updated_at", 0) > IDLE_AFTER:
        return "idle"
    return st


def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return {}


def load_sessions(now):
    out = []
    for path in glob.glob(os.path.join(STATUS_DIR, "*.json")):
        if os.path.basename(path) == "config.json":
            continue
        try:
            with open(path) as f:
                s = json.load(f)
        except Exception:
            continue
        if now - s.get("updated_at", 0) > STALE_SECONDS:
            continue
        s["_eff"] = effective_status(s, now)
        s["_age"] = now - s.get("updated_at", 0)
        out.append(s)
    return out


def focus_action(s):
    return action(FOCUS, s.get("tty", ""), s.get("term", "")) + " terminal=false"


def row_color(st):
    if st == "needs-attention":
        return RED
    if st == "idle":
        return MUTED
    return ""  # working / done: default label color (crisp in light + dark)


def emit_session(s, primary):
    st = s["_eff"]
    project = s.get("project", "?")
    pinned = project == primary
    dot = DOT.get(st, "⚪")
    star = "★ " if pinned else ""
    tokens = s.get("tokens", 0)
    cost = s.get("cost_usd", 0)
    model = s.get("model", "Claude")
    message = s.get("message", "")
    limit = ctx_limit(model)
    pct = (tokens / limit * 100) if limit else 0
    focus = focus_action(s)

    # Top-level row: status (dot) + project + the two numbers you most want at a
    # glance (context fill % and spend) — visible without opening the submenu.
    warn = "   ⚠" if st == "needs-attention" else ""
    rc = row_color(st)
    rc_attr = f"color={rc} " if rc else ""
    print(f"{dot}  {star}{project}    {pct:.0f}% · ${cost:,.2f}{warn} | {rc_attr}{focus}")

    # Submenu (hover): the full picture + actions. Detail lines use the default
    # label color (full contrast in light + dark); only accents are colored.
    if st == "needs-attention":
        print(f"--⚠  {message or 'Needs your attention'} | color={RED} size=13 {focus}")
        print("-----")
    bar_attr = f"color={RED} " if pct >= 85 else ""
    print(f"--{bar(pct)}   {pct:.0f}% context | font=Menlo size=13 {bar_attr}{focus}")
    print(f"--{human(tokens)} / {human(limit)} tokens   ·   ${cost:,.2f} | font=Menlo size=13 {focus}")
    print(f"--{short_model(model)}  ·  active {ago(s['_age'])} | color={MUTED} size=12 {focus}")
    print("-----")
    print(f"--↳ Open this terminal | {focus}")
    pin_label = "☆ Unpin from menu bar" if pinned else "★ Show in menu bar"
    print(f'--{pin_label} | {action(CONF, "pin", project)} terminal=false refresh=true')
    print(f'--✕ Clear this session | color={MUTED} {action(CONF, "clear", s.get("session_id", ""))} terminal=false refresh=true')


def menubar_image():
    """Base64-encoded PNG of the mascot for the menu-bar icon ('' if missing)."""
    try:
        with open(ICON, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def title_text(scope, primary):
    """Menu-bar text: a colored status DOT (always visible, so you can tell at a
    glance whether Claude is waiting) plus a count or the pinned project's %.
    """
    needs = sum(1 for s in scope if s["_eff"] == "needs-attention")
    if needs:
        return f"🔴 {needs}"

    working = sum(1 for s in scope if s["_eff"] == "working")
    if primary:
        p = next((s for s in scope if s.get("project") == primary), None)
        if p:
            limit = ctx_limit(p.get("model"))
            pct = (p.get("tokens", 0) / limit * 100) if limit else 0
            return f"{DOT.get(p['_eff'], '⚪')} {pct:.0f}%"

    if working:
        return f"🟡 {working}"
    return "🟢"


def emit_title(scope, primary):
    """Print the menu-bar line: colored status dot + mascot logo."""
    img = menubar_image()
    text = title_text(scope, primary)
    print(f"{text} | image={img}" if img else f"{text} | ")


def main():
    now = time.time()
    cfg = load_config()
    primary = cfg.get("primary", "")
    filter_on = cfg.get("filter", False)

    all_sessions = load_sessions(now)

    scope = all_sessions
    if filter_on and primary:
        scope = [s for s in all_sessions if s.get("project") == primary] or all_sessions

    if not all_sessions:
        img = menubar_image()
        print(f" | image={img}" if img else "🟢 | ")
        print("---")
        print(f"No active Claude Code sessions | color={MUTED}")
        return

    emit_title(scope, primary)
    print("---")

    needs = sum(1 for s in scope if s["_eff"] == "needs-attention")
    working = sum(1 for s in scope if s["_eff"] == "working")
    total_cost = sum(s.get("cost_usd", 0) for s in scope)
    summary = f"{len(scope)} session" + ("s" if len(scope) != 1 else "")
    summary += f"   ·   {needs} waiting · {working} working   ·   ${total_cost:,.2f}"
    print(f"{summary} | color={MUTED} size=12")
    print("---")

    ordered = sorted(
        scope,
        key=lambda s: (
            s.get("project") != primary,            # pinned first
            -RANK.get(s["_eff"], 0),                 # then by urgency
            -s.get("cost_usd", 0),                   # then by spend
        ),
    )
    for i, s in enumerate(ordered):
        if i:
            print("---")
        emit_session(s, primary)

    print("---")
    filt = "✓ Filter: pinned only" if filter_on else "Filter: showing all"
    print(f'{filt} | {action(CONF, "filter")} terminal=false refresh=true')
    print(f'Clear idle sessions (30m+) | {action(CONF, "clearstale", "1800")} terminal=false refresh=true')


if __name__ == "__main__":
    main()
