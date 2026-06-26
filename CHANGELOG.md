# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-06-25

### Added
- Auto-prune: finished sessions (done/idle) older than 30 minutes drop off the
  menu automatically, so it never fills with runs you're done with. Sessions
  that need you or are actively working are always shown.
- Homebrew tap: install with `brew install rikenpatel20/tap/claude-statusbar`.

## [0.1.0] - 2026-06-24

Initial release.

### Added
- macOS menu-bar indicator (SwiftBar plugin) showing all live Claude Code
  sessions, with the mascot logo and an always-visible colored status dot
  (🔴 waiting · 🟡 working · 🟢 idle) plus a count or the pinned project's
  context %.
- Native notification + sound the instant a session hits a permission prompt.
- Per-session live token (context-window usage) and dollar cost, with a
  context-fill bar that auto-detects 200K vs 1M-context models.
- Click a session row to focus its exact terminal window/tab (matched by tty);
  Apple Terminal + iTerm2, with app-activate fallback for other terminals.
- Pin a project to feature its live %/cost in the menu-bar text, plus a
  filter-to-pinned toggle.
- Staleness handling: a "working" session with no refresh for 90s is shown as
  idle, with one-click "Clear idle sessions" and per-row clear.
- `--chain` mode so an existing custom status line is recorded *and* displayed
  unchanged.
- Documented state-file JSON schema so alternative front-ends can be built.
- Safe, idempotent, backed-up `settings.json` merge (`install.sh --write-settings`).
- Smoke-test suite running on macOS and Linux via GitHub Actions CI.

### Fixed
- Claude Code's idle "waiting for your input" notification is no longer treated
  as a red action item (it maps to `done`), so the bar never shows a false
  "waiting on you".
- Clicking a session row could launch your editor (e.g. VS Code) instead of
  focusing the terminal: SwiftBar's `bash=` ran the Python helper *through bash*,
  which failed and fell back to opening the `.py` file. Click actions now invoke
  `python3` explicitly via `shell=`.
- Menu detail text uses full-contrast colors instead of washed-out gray.

[Unreleased]: https://github.com/rikenpatel20/claude-statusbar/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/rikenpatel20/claude-statusbar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/rikenpatel20/claude-statusbar/releases/tag/v0.1.0
