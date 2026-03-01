#!/usr/bin/env python3
"""
git-shield — Audit your git repos for exposed real email addresses. Fix them automatically.

Inspired by the HN thread: "YC companies scrape GitHub activity, send spam emails to users"
https://news.ycombinator.com/item?id=47163885

Usage:
    git-shield scan [directory]         Scan for git repos with exposed emails (default: ~)
    git-shield fix [directory]          Auto-fix exposed emails using GitHub no-reply address
    git-shield fix --global             Apply fix to global git config
    git-shield fix --hook               Also install pre-commit hook to block real email commits
    git-shield fix --dry-run            Show what would change without applying

    git-shield --version
    git-shield --help
"""

import os
import sys
import subprocess
import re
import json
import urllib.request
import urllib.error
from pathlib import Path
from collections import defaultdict

VERSION = "0.2.0"
GITHUB_NOREPLY_PATTERN = re.compile(r'\d+\+.+@users\.noreply\.github\.com')
BANNER = """
╔══════════════════════════════════════════════╗
║  🛡  git-shield v{version:<27} ║
║     Audit your git repos for email exposure  ║
╚══════════════════════════════════════════════╝
""".format(version=VERSION)

PRE_COMMIT_HOOK = r"""#!/bin/sh
# git-shield pre-commit hook: block commits with real email
# Installed by: git-shield fix --hook

NOREPLY_PATTERN='^[0-9]+\+.+@users\.noreply\.github\.com$'
CURRENT_EMAIL=$(git config user.email)

if ! echo "$CURRENT_EMAIL" | grep -qE "$NOREPLY_PATTERN"; then
    echo "❌ git-shield: Commit blocked!"
    echo "   Your email '$CURRENT_EMAIL' is not a GitHub no-reply address."
    echo "   Run: git-shield fix"
    echo "   Or:  git config user.email YOUR_ID+USERNAME@users.noreply.github.com"
    exit 1
fi
"""


def find_git_repos(root: str) -> list:
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
    try:
        result = subprocess.run(
            ['git', 'log', '--format=%ae', '--all'],
            cwd=repo_path, capture_output=True, text=True, timeout=10
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


def extract_github_username(remote_url: str) -> str:
    if not remote_url:
        return ''
    # SSH: git@github.com:username/repo.git or git@github-alias:username/repo.git
    ssh_match = re.match(r'git@[^:]+:([^/]+)/[^/]+(?:\.git)?$', remote_url)
    if ssh_match:
        return ssh_match.group(1)
    # HTTPS: https://github.com/username/repo.git
    https_match = re.match(r'https?://(?:[^@]+@)?github\.com/([^/]+)/[^/]+(?:\.git)?$', remote_url)
    if https_match:
        return https_match.group(1)
    return ''


def fetch_github_user_id(username: str) -> str:
    try:
        url = f'https://api.github.com/users/{username}'
        req = urllib.request.Request(url, headers={'User-Agent': 'git-shield/' + VERSION})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return str(data.get('id', ''))
    except Exception:
        return ''


def get_current_email(repo_path: str = None, scope: str = 'local') -> str:
    try:
        cmd = ['git', 'config', f'--{scope}', 'user.email']
        kw = {'capture_output': True, 'text': True, 'timeout': 5}
        if repo_path and scope == 'local':
            kw['cwd'] = repo_path
        result = subprocess.run(cmd, **kw)
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''


def set_git_email(email: str, repo_path: str = None, scope: str = 'local') -> bool:
    try:
        cmd = ['git', 'config', f'--{scope}', 'user.email', email]
        kw = {'capture_output': True, 'text': True, 'timeout': 5}
        if repo_path and scope == 'local':
            kw['cwd'] = repo_path
        result = subprocess.run(cmd, **kw)
        return result.returncode == 0
    except Exception:
        return False


def install_pre_commit_hook(repo_path: str, dry_run: bool = False) -> bool:
    hook_dir = Path(repo_path) / '.git' / 'hooks'
    hook_path = hook_dir / 'pre-commit'
    if dry_run:
        print(f"   [dry-run] Would install pre-commit hook: {hook_path}")
        return True
    try:
        hook_dir.mkdir(exist_ok=True)
        if hook_path.exists():
            backup = hook_path.with_suffix('.bak')
            hook_path.rename(backup)
            print(f"   ℹ️  Backed up existing hook to: {backup.name}")
        hook_path.write_text(PRE_COMMIT_HOOK)
        hook_path.chmod(0o755)
        return True
    except Exception as e:
        print(f"   ⚠️  Failed to install hook: {e}")
        return False


def is_real_email(email: str) -> bool:
    if not email or '@' not in email:
        return False
    if GITHUB_NOREPLY_PATTERN.match(email):
        return False
    if email.endswith('@users.noreply.github.com'):
        return False
    noreply_indicators = ['noreply', 'no-reply', 'bot@', 'action@', 'dependabot',
                          'github-actions', 'renovate', 'greenkeeper']
    service_accounts = {'actions@github.com', 'noreply@github.com'}
    if email.lower() in service_accounts:
        return False
    if any(ind in email.lower() for ind in noreply_indicators):
        return False
    return True


def resolve_noreply_email(username: str) -> str:
    user_id = fetch_github_user_id(username)
    if user_id:
        return f"{user_id}+{username}@users.noreply.github.com"
    return f"{username}@users.noreply.github.com"


# ─── Scan ─────────────────────────────────────────────────────────────────────

def scan(directory: str):
    print(BANNER)
    scan_dir = Path(directory).expanduser().resolve()
    print(f"🔍 Scanning for git repos under: {scan_dir}\n")

    repos = find_git_repos(str(scan_dir))
    if not repos:
        print("  No git repositories found.")
        return []

    print(f"  Found {len(repos)} git repo(s)\n")

    total_exposed = 0
    exposed_emails_global = defaultdict(int)
    repo_findings = []

    for repo_path in sorted(repos):
        emails = get_emails_from_repo(repo_path)
        remote = get_remote_url(repo_path)
        exposed = {e: c for e, c in emails.items() if is_real_email(e)}

        if exposed:
            repo_findings.append({'path': repo_path, 'remote': remote, 'exposed': exposed})
            for email, count in exposed.items():
                exposed_emails_global[email] += count
                total_exposed += count

    if not repo_findings:
        print("✅ No email exposure detected! Your commits are clean.\n")
        print("💡 Tip: Run periodically — new repos/collabs can introduce exposure.\n")
        return []

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
    print("\n💡 Run `git-shield fix` to automatically configure the GitHub no-reply email.\n")
    return repo_findings


# ─── Fix ──────────────────────────────────────────────────────────────────────

def fix(directory: str, use_global: bool = False, install_hook: bool = False,
        dry_run: bool = False):
    print(BANNER)
    prefix = "[dry-run] " if dry_run else ""

    if use_global:
        print("🔧 Fixing global git email config\n")
        cwd_remote = get_remote_url(os.getcwd())
        username = extract_github_username(cwd_remote)

        if not username:
            print("⚠️  Could not detect GitHub username from current directory remote.")
            print("   Make sure you're in a git repo with a GitHub remote, or")
            print("   set manually: git config --global user.email YOUR_ID+USER@users.noreply.github.com")
            sys.exit(1)

        noreply = resolve_noreply_email(username)
        current = get_current_email(scope='global')
        print(f"   GitHub username : {username}")
        print(f"   Current email   : {current or '(not set)'}")
        print(f"   No-reply email  : {noreply}\n")

        if current == noreply:
            print("✅ Already using GitHub no-reply email. Nothing to do.\n")
            return

        if dry_run:
            print(f"   {prefix}Would set global user.email → {noreply}\n")
        else:
            ok = set_git_email(noreply, scope='global')
            if ok:
                print(f"✅ Global git email updated → {noreply}\n")
            else:
                print("❌ Failed to update global git config.\n")
                sys.exit(1)
        return

    # Per-repo fix
    scan_dir = Path(directory).expanduser().resolve()
    print(f"🔧 Fixing git repos under: {scan_dir}\n")
    if dry_run:
        print(f"   (dry-run mode — no changes will be made)\n")

    repos = find_git_repos(str(scan_dir))
    if not repos:
        print("  No git repositories found.")
        return

    print(f"  Found {len(repos)} git repo(s)\n")
    print("─" * 62)

    fixed = skipped = failed = no_remote = 0
    username_cache = {}

    for repo_path in sorted(repos):
        remote = get_remote_url(repo_path)
        username = extract_github_username(remote)

        if not username:
            no_remote += 1
            continue

        if username not in username_cache:
            username_cache[username] = resolve_noreply_email(username)
        noreply = username_cache[username]

        current = get_current_email(repo_path, 'local')
        repo_name = Path(repo_path).name

        if current == noreply:
            print(f"\n⏭️  {repo_name}  (already correct)")
            skipped += 1
            continue

        if dry_run:
            print(f"\n✅ {repo_name}")
            print(f"   {prefix}Would set: {current or '(not set)'} → {noreply}")
            if install_hook:
                install_pre_commit_hook(repo_path, dry_run=True)
            fixed += 1
        else:
            ok = set_git_email(noreply, repo_path, 'local')
            if ok:
                print(f"\n✅ {repo_name}")
                print(f"   Set: {current or '(not set)'} → {noreply}")
                if install_hook:
                    hook_ok = install_pre_commit_hook(repo_path)
                    if hook_ok:
                        print(f"   🪝 Pre-commit hook installed")
                fixed += 1
            else:
                print(f"\n❌ {repo_name}  — git config failed")
                failed += 1

    print(f"\n{'─' * 62}")
    print(f"\n📊 Fix Summary {'(dry-run)' if dry_run else ''}")
    print(f"   {'Would fix' if dry_run else 'Fixed'}       : {fixed} repo(s)")
    print(f"   Skipped     : {skipped} repo(s) (already correct)")
    print(f"   No GH remote: {no_remote} repo(s) (skipped)")
    if failed:
        print(f"   Failed      : {failed} repo(s)")

    if dry_run and fixed > 0:
        print(f"\n   Run without --dry-run to apply changes.\n")
    elif fixed > 0:
        print(f"\n✅ Done. Future commits will use the GitHub no-reply email.\n")
        if not install_hook:
            print("💡 Tip: Re-run with --hook to also block accidental real-email commits.\n")
    elif fixed == 0 and failed == 0:
        print(f"\n✅ All GitHub repos already configured correctly.\n")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args or args[0] in ('--help', '-h', 'help'):
        print(__doc__)
        sys.exit(0)

    if args[0] in ('--version', '-v', 'version'):
        print(f"git-shield {VERSION}")
        sys.exit(0)

    subcommand = args[0]
    rest = args[1:]

    dry_run = '--dry-run' in rest
    use_global = '--global' in rest
    install_hook = '--hook' in rest
    positional = [a for a in rest if not a.startswith('--')]

    if subcommand == 'scan':
        directory = positional[0] if positional else '~'
        scan(directory)
    elif subcommand == 'fix':
        directory = positional[0] if positional else '~'
        fix(directory, use_global=use_global, install_hook=install_hook, dry_run=dry_run)
    else:
        # Legacy: treat bare invocation as scan
        directory = subcommand if not subcommand.startswith('-') else '~'
        scan(directory)


if __name__ == '__main__':
    main()
