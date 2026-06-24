#!/usr/bin/env python3
"""
cc-focus.py — bring a Claude Code session's terminal window/tab to the front.

Invoked by the menu-bar plugin when you click a session row:

    cc-focus.py <tty> <term_program> [cwd]

  <tty>          e.g. /dev/ttys004 (recorded by the hook/status line)
  <term_program> the TERM_PROGRAM value, e.g. Apple_Terminal, iTerm.app, vscode

For Apple Terminal and iTerm2 the exact tab/session is located by matching its
tty. For other terminals (or when the tty is unknown) we fall back to simply
activating the terminal application, which is still better than nothing.
"""
import sys
import os
import subprocess

# TERM_PROGRAM value (lowercased) -> AppleScript application name to activate.
GENERIC_APPS = {
    "vscode": "Visual Studio Code",
    "warpterminal": "Warp",
    "wezterm": "WezTerm",
    "ghostty": "Ghostty",
    "hyper": "Hyper",
    "kitty": "kitty",
    "tabby": "Tabby",
    "alacritty": "Alacritty",
}


def osa(script):
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def activate_app(name):
    name = name.replace('"', "")
    osa(f'tell application "{name}" to activate')


def focus_terminal(tty):
    osa(f'''
tell application "Terminal"
  activate
  repeat with w in windows
    try
      repeat with t in tabs of w
        if (tty of t) is "{tty}" then
          set selected of t to true
          set frontmost of w to true
          return
        end if
      end repeat
    end try
  end repeat
end tell
''')


def focus_iterm(tty):
    osa(f'''
tell application "iTerm"
  activate
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        try
          if (tty of s) is "{tty}" then
            select w
            tell t to select
            tell s to select
            return
          end if
        end try
      end repeat
    end repeat
  end repeat
end tell
''')


def main():
    tty = sys.argv[1] if len(sys.argv) > 1 else ""
    term = sys.argv[2] if len(sys.argv) > 2 else ""
    tl = term.lower()

    # Only allow a well-formed tty path into the AppleScript string.
    if tty and not (tty.startswith("/dev/") and tty[5:].replace("tty", "").isalnum()):
        tty = ""

    if tl == "apple_terminal":
        if tty:
            focus_terminal(tty)
        else:
            activate_app("Terminal")
    elif tl in ("iterm.app", "iterm2", "iterm"):
        if tty:
            focus_iterm(tty)
        else:
            activate_app("iTerm")
    else:
        name = GENERIC_APPS.get(tl)
        if not name and term:
            name = term[:-4] if term.endswith(".app") else term
        activate_app(name or "Terminal")


if __name__ == "__main__":
    main()
