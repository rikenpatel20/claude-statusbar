#!/usr/bin/env bash
#
# install.sh — set up claude-statusbar (macOS).
#
#   ./install.sh                  # install scripts + plugin, print settings snippet
#   ./install.sh --write-settings # also merge the snippet into ~/.claude/settings.json
#                                  # (a timestamped backup is made first)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_DIR="$HOME/.claude/status"
SETTINGS="$HOME/.claude/settings.json"
WRITE_SETTINGS=0
[ "${1:-}" = "--write-settings" ] && WRITE_SETTINGS=1

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found. Install it (xcode-select --install or brew install python)." >&2
  exit 1
fi

echo "==> Installing scripts to $STATUS_DIR"
mkdir -p "$STATUS_DIR"
install -m 0755 "$REPO_DIR/src/cc-status.py"     "$STATUS_DIR/cc-status.py"
install -m 0755 "$REPO_DIR/src/cc-statusline.py" "$STATUS_DIR/cc-statusline.py"
install -m 0755 "$REPO_DIR/src/cc-focus.py"      "$STATUS_DIR/cc-focus.py"
install -m 0755 "$REPO_DIR/src/cc-config.py"     "$STATUS_DIR/cc-config.py"

# Locate the SwiftBar plugins folder: prefer the value SwiftBar itself stores.
PLUGIN_DIR="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
if [ -z "${PLUGIN_DIR:-}" ]; then
  for d in \
    "$HOME/Library/Application Support/SwiftBar/Plugins" \
    "$HOME/Library/Application Support/SwiftBar" \
    "$HOME/.swiftbar" "$HOME/SwiftBar"; do
    [ -d "$d" ] && PLUGIN_DIR="$d" && break
  done
fi

if [ -n "${PLUGIN_DIR:-}" ] && [ -d "$PLUGIN_DIR" ]; then
  echo "==> Installing SwiftBar plugin to $PLUGIN_DIR"
  install -m 0755 "$REPO_DIR/src/claude.2s.py" "$PLUGIN_DIR/claude.2s.py"
else
  echo "!!  SwiftBar plugins folder not found."
  echo "    1) brew install --cask swiftbar"
  echo "    2) open SwiftBar and choose a plugins folder when prompted"
  echo "    3) copy src/claude.2s.py into it (keep the .2s. in the filename)"
fi

if [ "$WRITE_SETTINGS" = "1" ]; then
  echo "==> Merging hooks + statusLine into $SETTINGS"
  python3 "$REPO_DIR/scripts/merge_settings.py" "$SETTINGS" "$REPO_DIR/settings.snippet.json"
else
  echo
  echo "==> Final step: merge this into $SETTINGS (or re-run with --write-settings):"
  echo
  cat "$REPO_DIR/settings.snippet.json"
fi

echo
echo "Done. Restart Claude Code so the hooks + status line load."
