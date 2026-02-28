# 🛡 git-shield

**Audit your git repos for exposed real email addresses. Fix them before spammers find you.**

---

Inspired by: [YC companies scrape GitHub activity, send spam emails to users](https://news.ycombinator.com/item?id=47163885) (670 upvotes, HN)

Every `git commit` embeds your email address. When you push to GitHub, that email is public — and startups are actively scraping it to build cold-email lists.

`git-shield` scans your local git repos, shows exactly which ones expose your real email, and tells you how to fix it.

## Quick Start

```bash
# Scan your home directory for exposed emails
python3 git-shield.py ~

# Scan a specific directory
python3 git-shield.py ~/Documents/GitHub
```

No dependencies. Just Python 3 + git.

## Example Output

```
╔══════════════════════════════════════════════╗
║  🛡  git-shield v0.1.0                       ║
║     Audit your git repos for email exposure  ║
╚══════════════════════════════════════════════╝

🔍 Scanning for git repos under: /Users/you/Documents/GitHub

  Found 12 git repo(s)

⚠️  Exposed real emails found in 3 repo(s):

──────────────────────────────────────────────────────────────

📁 /Users/you/Documents/GitHub/my-project
   Remote: https://github.com/you/my-project.git
   📧 you@yourdomain.com  ← 47 commit(s)

📊 Summary
   Repos with exposure  : 3
   Unique real emails   : 1
   Total commits exposed: 89

🔧 FIX IT IN 3 STEPS:

1️⃣  Find your GitHub no-reply email:
    https://github.com/settings/emails
    → 'Keep my email addresses private'
    → Copy: YOUR_ID+USERNAME@users.noreply.github.com

2️⃣  Set it as your global git email:
    git config --global user.email "YOUR_ID+USERNAME@users.noreply.github.com"

3️⃣  Block CLI pushes that expose real email:
    https://github.com/settings/emails
    → Enable: 'Block command line pushes that expose my email'
```

## What it detects

- ✅ Your real email in commit history
- ✅ Multiple email addresses used across repos
- ✅ Shows remote URL so you know which are public

## What it does NOT do

- ❌ Makes no network requests (100% local)
- ❌ Does not modify any files
- ❌ Cannot remove emails from past commits (that's risky without explicit action)

## Why this matters

Every commit you make contains your email in plaintext. Anyone can run:

```bash
git log --format="%ae" | sort | uniq
```

…on a cloned repo and harvest your address. Some YC-backed companies have built businesses around this. Your email is in thousands of commits before you realize it.

The fix takes 2 minutes. This tool shows you exactly where to look.

## The fix, explained

GitHub provides a "no-reply" email that links commits to your account without exposing your real address. It looks like:

```
12345678+yourusername@users.noreply.github.com
```

Once configured, GitHub routes everything correctly. Past commits still contain your old email — but you stop the bleeding going forward.

## Requirements

- Python 3.7+
- git installed in PATH

## License

MIT
