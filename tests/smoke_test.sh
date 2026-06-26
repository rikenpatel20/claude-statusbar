#!/usr/bin/env bash
#
# smoke_test.sh — end-to-end test of the hook + status-line + plugin pipeline.
#
# Runs everything against a throwaway HOME so it never touches your real
# ~/.claude/status. Verifies the state file is written correctly and that the
# SwiftBar plugin renders the expected menu-bar title.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_DIR/src"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP"
STATUS_DIR="$TMP/.claude/status"
SID="test-session-001"
CWD="/Users/me/code/web-app"

fail() { echo "FAIL: $1" >&2; exit 1; }

# Fake transcript with a usage block the status line will read.
TRANSCRIPT="$TMP/transcript.jsonl"
printf '%s\n' \
  '{"type":"assistant","message":{"usage":{"input_tokens":1000,"output_tokens":200,"cache_read_input_tokens":11000,"cache_creation_input_tokens":231}}}' \
  > "$TRANSCRIPT"

echo "1. UserPromptSubmit -> working"
echo "{\"session_id\":\"$SID\",\"cwd\":\"$CWD\"}" | python3 "$SRC/cc-status.py" working
[ -f "$STATUS_DIR/$SID.json" ] || fail "state file not created"
python3 - "$STATUS_DIR/$SID.json" <<'PY' || fail "status != working"
import json,sys
s=json.load(open(sys.argv[1]))
assert s["status"]=="working", s
assert s["project"]=="web-app", s
PY

echo "2. status line records tokens + cost (preserves status)"
echo "{\"session_id\":\"$SID\",\"transcript_path\":\"$TRANSCRIPT\",\"workspace\":{\"current_dir\":\"$CWD\"},\"model\":{\"display_name\":\"Opus 4.8\"},\"cost\":{\"total_cost_usd\":0.0812}}" \
  | python3 "$SRC/cc-statusline.py" > "$TMP/line.txt"
grep -q "Opus 4.8" "$TMP/line.txt" || fail "status line text wrong: $(cat "$TMP/line.txt")"
python3 - "$STATUS_DIR/$SID.json" <<'PY' || fail "tokens/cost/status wrong after statusline"
import json,sys
s=json.load(open(sys.argv[1]))
assert s["tokens"]==12431, s              # 1000+200+11000+231
assert abs(s["cost_usd"]-0.0812)<1e-6, s
assert s["status"]=="working", s          # statusline must NOT clobber hook status
PY

echo "3. Notification -> needs-attention (with message)"
echo "{\"session_id\":\"$SID\",\"cwd\":\"$CWD\",\"message\":\"Permission needed: Bash\"}" \
  | python3 "$SRC/cc-status.py" needs-attention
python3 - "$STATUS_DIR/$SID.json" <<'PY' || fail "needs-attention not recorded"
import json,sys
s=json.load(open(sys.argv[1]))
assert s["status"]=="needs-attention", s
assert s["message"]=="Permission needed: Bash", s
assert s["tokens"]==12431, s              # token data preserved across transition
PY

echo "3b. idle 'waiting for your input' is NOT treated as needs-attention"
echo "{\"session_id\":\"$SID\",\"cwd\":\"$CWD\",\"message\":\"Claude is waiting for your input\"}" \
  | python3 "$SRC/cc-status.py" needs-attention
python3 - "$STATUS_DIR/$SID.json" <<'PY' || fail "idle-input was wrongly kept as needs-attention"
import json,sys
s=json.load(open(sys.argv[1]))
assert s["status"]=="done", "expected done, got %r" % s["status"]
PY
# restore the needs-attention state for the remaining tests
echo "{\"session_id\":\"$SID\",\"cwd\":\"$CWD\",\"message\":\"Permission needed: Bash\"}" \
  | python3 "$SRC/cc-status.py" needs-attention

echo "4. terminal info (term + tty) is captured when available"
# term (TERM_PROGRAM) and tty are best-effort: both are legitimately empty in a
# headless/CI shell. Assert only that the fields are well-formed when present.
python3 - "$STATUS_DIR/$SID.json" <<'PY' || fail "terminal info fields malformed"
import json,sys
s=json.load(open(sys.argv[1]))
assert isinstance(s.get("term",""), str), "term must be a string"
if s.get("tty"):
    assert s["tty"].startswith("/dev/"), "tty must be a /dev path: %r" % s["tty"]
PY
# Also prove capture works when TERM_PROGRAM is set — use a FRESH session id so
# the "only set term if missing" guard doesn't keep a value from an earlier step.
TERM_PROGRAM="iTerm.app" sh -c "echo '{\"session_id\":\"termcheck\",\"cwd\":\"$CWD\"}' | python3 '$SRC/cc-status.py' working"
python3 - "$STATUS_DIR/termcheck.json" <<'PY' || fail "term not captured when TERM_PROGRAM set"
import json,sys
s=json.load(open(sys.argv[1]))
assert s.get("term")=="iTerm.app", "expected iTerm.app, got %r" % s.get("term")
PY
rm -f "$STATUS_DIR/termcheck.json"
# restore needs-attention for the remaining steps
echo "{\"session_id\":\"$SID\",\"cwd\":\"$CWD\",\"message\":\"Permission needed: Bash\"}" \
  | python3 "$SRC/cc-status.py" needs-attention

echo "5. plugin: red title, clickable rows, pin/filter controls, no Refresh button"
OUT="$(python3 "$SRC/claude.2s.py")"
TITLE="$(echo "$OUT" | head -1)"
echo "   title: $TITLE"
echo "$TITLE" | grep -q "🔴" || fail "title not red while a session needs attention: $TITLE"
echo "$OUT" | grep -q "cc-focus.py" || fail "rows are not clickable (no cc-focus action)"
echo "$OUT" | grep -q "cc-config.py" || fail "pin/filter/clear controls missing"
echo "$OUT" | grep -q "Show in menu bar" || fail "pin action missing"
echo "$OUT" | grep -qi "Filter:" || fail "filter control missing"
# The standalone SwiftBar "Refresh | refresh=true" menu BUTTON must be gone
echo "$OUT" | grep -qx "Refresh | refresh=true" && fail "standalone Refresh button should be removed"
echo "$OUT" | grep -q "context" || fail "context-usage line missing"

echo "6. staleness: a 'working' session not updated in >90s is not counted working"
# Replace the live session with a stale 'working' one (updated 200s ago).
OLD=$(( $(date +%s) - 200 ))
cat > "$STATUS_DIR/$SID.json" <<JSON
{"session_id":"$SID","project":"oldproj","cwd":"$CWD","model":"Claude",
 "status":"working","tokens":1000,"cost_usd":0.01,"updated_at":$OLD}
JSON
SUMMARY="$(python3 "$SRC/claude.2s.py" | grep 'session')"
echo "$SUMMARY" | grep -q "0 working" \
  || fail "stale 'working' session was still counted as working: $SUMMARY"

echo "6b. auto-prune: a finished (done) session older than 30m drops off the menu"
OLD_DONE=$(( $(date +%s) - 2000 ))   # ~33m ago, past DONE_HIDE_AFTER (1800s)
cat > "$STATUS_DIR/done-old.json" <<JSON
{"session_id":"done-old","project":"finished-proj","cwd":"$CWD","model":"Claude",
 "status":"done","tokens":1000,"cost_usd":0.01,"updated_at":$OLD_DONE}
JSON
python3 "$SRC/claude.2s.py" | grep -q "finished-proj" \
  && fail "old finished session should have been auto-pruned from the menu"
# A recently-finished session must still be visible.
NEW_DONE=$(( $(date +%s) - 60 ))
cat > "$STATUS_DIR/done-new.json" <<JSON
{"session_id":"done-new","project":"justfinished","cwd":"$CWD","model":"Claude",
 "status":"done","tokens":1000,"cost_usd":0.01,"updated_at":$NEW_DONE}
JSON
python3 "$SRC/claude.2s.py" | grep -q "justfinished" \
  || fail "recently-finished session should still be shown"
rm -f "$STATUS_DIR/done-old.json" "$STATUS_DIR/done-new.json"

echo "7. pin + filter controls work via cc-config.py"
python3 "$SRC/cc-config.py" pin oldproj >/dev/null 2>&1
python3 - "$STATUS_DIR/config.json" <<'PY' || fail "pin not recorded"
import json,sys
c=json.load(open(sys.argv[1]))
assert c.get("primary")=="oldproj", c
PY
# When a project is pinned, the menu-bar title shows its live context % (with a
# status dot) instead of the generic session count.
python3 "$SRC/claude.2s.py" | head -1 | grep -q "%" \
  || fail "pinned project's context % not shown in menu-bar title"

echo "8. SessionEnd -> file removed"
echo "{\"session_id\":\"$SID\",\"cwd\":\"$CWD\"}" | python3 "$SRC/cc-status.py" end
[ ! -f "$STATUS_DIR/$SID.json" ] || fail "state file not removed on SessionEnd"

echo "9. plugin with no sessions renders the empty state"
python3 "$SRC/claude.2s.py" | grep -q "No active Claude Code sessions" || fail "empty state wrong"

echo
echo "ALL TESTS PASSED"
