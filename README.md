# 🛡 git-shield

**Scan your git repos for exposed email addresses. Fix them in one command.**

---

Inspired by: [YC companies scrape GitHub activity, send spam emails to users](https://news.ycombinator.com/item?id=47163885) (670 upvotes, HN)

Every `git commit` bakes your email address into history. When you push to GitHub, it's public — and it gets scraped. `git-shield` finds every repo leaking your real email and fixes it automatically using GitHub's no-reply address.

## Quick Start

```bash
# Scan your home directory for exposed emails
python3 git-shield.py scan ~

# Auto-fix all repos (detects GitHub username, sets no-reply email)
python3 git-shield.py fix ~

# Preview what would change (no writes)
python3 git-shield.py fix ~ --dry-run

# Fix + install pre-commit hook to block future leaks
python3 git-shield.py fix ~ --hook

# Fix your global git config (run from inside a GitHub repo)
python3 git-shield.py fix --global
```

No dependencies. Just Python 3 + git.

## What `fix` does

1. Detects your GitHub username from the repo's remote URL
2. Fetches your GitHub user ID via the public API
3. Constructs the correct no-reply address: `12345678+yourusername@users.noreply.github.com`
4. Sets `git config user.email` locally per repo (or globally with `--global`)
5. Optionally installs a pre-commit hook that blocks commits if your real email slips back in

## Example Output

```
╔══════════════════════════════════════════════╗
║  🛡  git-shield v0.2.0                       ║
║     Audit your git repos for email exposure  ║
╚══════════════════════════════════════════════╝

🔧 Fixing git repos under: /Users/you/Documents/GitHub

  Found 5 git repo(s)

──────────────────────────────────────────────────────────────

✅ my-project
   Set: you@yourdomain.com → 12345678+yourusername@users.noreply.github.com
   🪝 Pre-commit hook installed

✅ side-project
   Set: (not set) → 12345678+yourusername@users.noreply.github.com

⏭️  dotfiles  (already correct)

──────────────────────────────────────────────────────────────

📊 Fix Summary
   Fixed       : 2 repo(s)
   Skipped     : 1 repo(s) (already correct)
   No GH remote: 2 repo(s) (skipped)

✅ Done. Future commits will use the GitHub no-reply email.
```

## All commands

| Command | What it does |
|---|---|
| `git-shield scan [dir]` | Scan for repos with exposed real emails |
| `git-shield fix [dir]` | Auto-fix using GitHub no-reply email |
| `git-shield fix --dry-run` | Preview changes, apply nothing |
| `git-shield fix --global` | Fix global git config (run from inside a GitHub repo) |
| `git-shield fix --hook` | Fix + install pre-commit hook |
| `git-shield fix [dir] --hook --dry-run` | Preview fix + hook installation |

## Why the pre-commit hook matters

`git config` only affects future commits — but you can still accidentally override it with `GIT_AUTHOR_EMAIL` or a misconfigured editor plugin. The `--hook` flag installs a local pre-commit check that blocks the commit if the email doesn't match the no-reply pattern.

```
❌ git-shield: Commit blocked!
   Your email 'you@yourdomain.com' is not a GitHub no-reply address.
   Run: git-shield fix
```

## What about past commits?

They still contain your old email. Rewriting history is risky (force-push, collaborator divergence) and out of scope here. `git-shield` focuses on stopping the bleeding going forward. The real fix is to enable GitHub's "Block command line pushes that expose my email" setting and use the no-reply address everywhere from now on.

## Requirements

- Python 3.7+
- git in PATH
- Internet access for `fix` (GitHub API to fetch user ID)

## License

MIT
