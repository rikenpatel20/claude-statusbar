# Contributing to claude-statusbar

Thanks for your interest! This project is intentionally small, dependency-free,
and easy to hack on.

## Principles

- **No runtime dependencies.** Everything is `python3` (standard library) plus a
  shell installer. Please keep it that way — it's what makes install trivial.
- **The state file is the product.** The writers (`cc-status.py`,
  `cc-statusline.py`) and the front-end (`claude.2s.py`) are decoupled by a
  documented JSON schema (see the README). New front-ends should read that schema
  rather than coupling to SwiftBar.
- **A hook must never break a user's session.** Hook scripts swallow their own
  errors and exit 0. Keep that guarantee.

## Good first contributions

- **A new front-end** against the state-file schema: tmux status, waybar/polybar
  (Linux), Raycast, a tiny web dashboard, etc.
- **More terminal support** in `cc-focus.py` (Ghostty, WezTerm, Warp, kitty…).
- Docs, screenshots, or a demo GIF for the README.

## Development

```bash
git clone https://github.com/rikenpatel20/claude-statusbar
cd claude-statusbar
bash tests/smoke_test.sh        # the full pipeline, against a throwaway HOME
```

The smoke test never touches your real `~/.claude`. It's the same suite CI runs
on macOS and Linux.

To try your changes live:

```bash
./install.sh                    # copies scripts + plugin into place
# edit src/*.py, then re-run install.sh (or copy the changed file) and:
open "swiftbar://refreshplugin?name=claude"
```

## Pull requests

1. Branch off `main`.
2. Keep changes focused; update the README if behavior changes.
3. **Run `bash tests/smoke_test.sh`** and add a test for new behavior.
4. No emojis in commit messages; use clear, conventional summaries
   (`feat:`, `fix:`, `docs:`…).
5. Open the PR — CI must be green before merge.

## Reporting bugs / ideas

Use the [issue templates](https://github.com/rikenpatel20/claude-statusbar/issues/new/choose).
For anything security-related, see [SECURITY.md](./SECURITY.md).

By contributing, you agree your work is licensed under the project's
[MIT License](./LICENSE).
