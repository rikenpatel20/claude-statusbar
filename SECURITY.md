# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Instead, report privately via a
[GitHub security advisory](https://github.com/rikenpatel20/claude-statusbar/security/advisories/new).
You can expect an initial response within a few days.

## Scope & threat model

`claude-statusbar` runs entirely on your own machine. It:

- reads/writes JSON files under `~/.claude/status/`,
- reads the Claude Code hook/status-line payloads on stdin,
- runs `osascript` to post local notifications and focus terminal windows,
- never makes network requests and has no runtime dependencies.

Things we care about and actively guard against:

- **Command/AppleScript injection** — values that flow into `osascript` (session
  messages, tty paths) are sanitized; tty paths are validated against a strict
  `/dev/tty…` pattern before use.
- **Path traversal** — `session_id` is sanitized to `[A-Za-z0-9_-]` before being
  used as a filename.
- **Never breaking your session** — hook scripts swallow errors and exit 0.

If you find a way around any of these, we'd love to hear about it via the private
advisory link above.
