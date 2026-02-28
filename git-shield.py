#!/usr/bin/env python3
"""
git-shield — Audit your git repos for exposed real email addresses.

Inspired by the HN thread: "YC companies scrape GitHub activity, send spam emails to users"
https://news.ycombinator.com/item?id=47163885

Usage:
    python git-shield.py [directory]    # Scan directory for git repos (default: ~)
    python git-shield.py --fix          # Show exact commands to fix exposure
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from collections import defaultdict

VERSION = "0.1.0"
GITHUB_NOREPLY_PATTERN = re.compile(r'\d+\+.+@users\.noreply\.github\.com')
BANNER = """
╔══════════════════════════════════════════════╗
║  🛡  git-shield v{version:<27} ║
║     Audit your git repos for email exposure  ║
╚══════════════════════════════════════════════╝
""".format(version=VERSION)


def find_git_repos(root: str) -> list:
    """Find all git repos under root (depth-limited)."""
    repos = []
    root_path = Path(root).expanduser().resolve()

    for dirpath, dirnames, _ in os.walk(root_path):
        depth = len(Path(dirpath).relative_to(root_path).parts)
        if depth > 5:
            dirnames.clear()
            continue

        if '.git' in dirnames:
            repos.append(dirpath)
            dirnames.clear()
            continue

        dirnames[:] = [d for d in dirnames
                       if not d.startswith('.')
                       and d not in ('node_modules', '__pycache__', 'vendor', '.venv', 'venv')]

    return repos


def get_emails_from_repo(repo_path: str) -> dict:
    """Extract all unique author emails and commit counts from a repo."""
    try:
        result = subprocess.run(
            ['git', 'log', '--format=%ae', '--all'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return {}

        emails = defaultdict(int)
        for line in result.stdout.strip().split('\n'):
            email = line.strip()
            if email:
                emails[email] += 1
        return dict(emails)
    except Exception:
        return {}


def get_remote_url(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''


def is_real_email(email: str) -> bool:
    """Return True if the email looks like a real (non-anonymized) address."""
    if not email or '@' not in email:
        return False
    if GITHUB_NOREPLY_PATTERN.match(email):
        return False
    if email.endswith('@users.noreply.github.com'):
        return False
    noreply_indicators = [
        'noreply', 'no-reply', 'bot@', 'action@', 'dependabot',
        'github-actions', 'renovate', 'greenkeeper',
        'actions@github.com',
    ]
    # Exact matches for well-known service accounts
    service_accounts = {
        'actions@github.com',
        'noreply@github.com',
    }
    if email.lower() in service_accounts:
        return False
    if any(ind in email.lower() for ind in noreply_indicators):
        return False
    return True


def scan(directory: str):
    print(BANNER)
    scan_dir = Path(directory).expanduser().resolve()
    print(f"🔍 Scanning for git repos under: {scan_dir}\n")

    repos = find_git_repos(str(scan_dir))
    if not repos:
        print("  No git repositories found.")
        return

    print(f"  Found {len(repos)} git repo(s)\n")

    total_exposed = 0
    exposed_emails_global = defaultdict(int)
    repo_findings = []

    for repo_path in sorted(repos):
        emails = get_emails_from_repo(repo_path)
        remote = get_remote_url(repo_path)
        exposed = {e: c for e, c in emails.items() if is_real_email(e)}

        if exposed:
            repo_findings.append({
                'path': repo_path,
                'remote': remote,
                'exposed': exposed,
            })
            for email, count in exposed.items():
                exposed_emails_global[email] += count
                total_exposed += count

    if not repo_findings:
        print("✅ No email exposure detected! Your commits are clean.\n")
        print("💡 Tip: Run periodically — new repos/collabs can introduce exposure.\n")
        return

    print(f"⚠️  Exposed real emails found in {len(repo_findings)} repo(s):\n")
    print("─" * 62)

    for f in repo_findings:
        print(f"\n📁 {f['path']}")
        if f['remote']:
            print(f"   Remote: {f['remote']}")
        for email, count in sorted(f['exposed'].items(), key=lambda x: -x[1]):
            print(f"   📧 {email}  ← {count} commit(s)")

    print(f"\n{'─' * 62}")
    print(f"\n📊 Summary")
    print(f"   Repos with exposure  : {len(repo_findings)}")
    print(f"   Unique real emails   : {len(exposed_emails_global)}")
    print(f"   Total commits exposed: {total_exposed}")

    print(f"\n{'─' * 62}")
    print("\n🔧 FIX IT IN 3 STEPS:\n")
    print("1️⃣  Find your GitHub no-reply email:")
    print("    https://github.com/settings/emails")
    print("    → 'Keep my email addresses private'")
    print("    → Copy: YOUR_ID+USERNAME@users.noreply.github.com\n")
    print("2️⃣  Set it as your global git email:")
    print("    git config --global user.email \"YOUR_ID+USERNAME@users.noreply.github.com\"\n")
    print("3️⃣  Block CLI pushes that expose real email:")
    print("    https://github.com/settings/emails")
    print("    → Enable: 'Block command line pushes that expose my email'\n")
    print("📚 Docs: https://docs.github.com/en/account-and-profile/reference/email-addresses-reference\n")
    print("─" * 62)
    print("\nNote: Past commits can't be changed without rewriting history.")
    print("Focus on protecting future commits with the steps above.\n")


def main():
    args = [a for a in sys.argv[1:] if a not in ('--fix',)]

    if '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)

    if '--version' in args or '-v' in args:
        print(f"git-shield {VERSION}")
        sys.exit(0)

    directory = args[0] if args else '~'
    scan(directory)


if __name__ == '__main__':
    main()
