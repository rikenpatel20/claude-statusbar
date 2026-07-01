# Releasing claude-statusbar

Checklist for cutting a new release. **The Homebrew formula does not update itself** —
after every version bump you must update `url` **and** `sha256` in the tap, or `brew`
will keep installing the old version.

## 1. Tag and push the release

```bash
# bump the version, update CHANGELOG.md, commit
git tag vX.Y.Z
git push origin main --tags
gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
```

## 2. Get the new tarball's sha256

```bash
curl -sL "https://github.com/rikenpatel20/claude-statusbar/archive/refs/tags/vX.Y.Z.tar.gz" \
  | shasum -a 256
```

## 3. Update the Homebrew formula (the step that's easy to forget)

Repo: **https://github.com/rikenpatel20/homebrew-tap** → `Formula/claude-statusbar.rb`

Change both lines:

```ruby
url "https://github.com/rikenpatel20/claude-statusbar/archive/refs/tags/vX.Y.Z.tar.gz"
sha256 "<the sha256 from step 2>"
```

Commit + push the tap repo.

## 4. Verify the install works end to end

```bash
brew update
brew install rikenpatel20/tap/claude-statusbar   # or `brew upgrade` if already installed
```

If the version or sha256 is wrong, brew fails the integrity check here — that's the
signal the formula wasn't bumped.

---

**Rule of thumb:** a release isn't done until `Formula/claude-statusbar.rb` points at the
new tag with the matching `sha256`.
