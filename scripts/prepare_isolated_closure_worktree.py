#!/usr/bin/env python3
"""Create or reuse an isolated Granted Hours publication worktree.

Print-desk-calendar WIP in the canonical checkout must not block daily
website publication. This script always publishes from a detached
worktree at origin/main and never mutates the canonical dirty tree.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


WORKSPACE = Path("/Users/simonmeng/HermesWorkspaces/Heizhou")
CANONICAL = WORKSPACE / "art-projects" / "granted-hours-daily-sync"
DEFAULT_ROOT = WORKSPACE / "tmp"
PRIVATE_FILES = (
    "identity-denylist.json",
    "holdings-denylist.json",
    "self-media-denylist.json",
)


def run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )


def fail(message: str) -> None:
    raise SystemExit(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    return parser.parse_args()


def git_sha(cwd: Path, *rev: str) -> str:
    result = run(["git", "rev-parse", *rev], cwd=cwd)
    if result.returncode != 0:
        fail(result.stderr.strip() or "git rev-parse failed")
    return result.stdout.strip()


def main() -> int:
    args = parse_args()
    canonical = args.canonical.resolve()
    if not (canonical / ".git").exists() and not (canonical / ".git").is_file():
        fail(f"Canonical worktree is missing: {canonical}")
    fetch = run(["git", "fetch", "origin", "main"], cwd=canonical)
    if fetch.returncode != 0:
        fail(fetch.stderr.strip() or "git fetch origin main failed")
    origin_main = git_sha(canonical, "origin/main")
    remote = run(["git", "ls-remote", "origin", "refs/heads/main"], cwd=canonical)
    remote_sha = remote.stdout.split()[0] if remote.returncode == 0 and remote.stdout.split() else ""
    if not remote_sha or remote_sha != origin_main:
        fail("origin/main is not aligned with remote refs/heads/main")

    porcelain = run(["git", "status", "--porcelain", "-z"], cwd=canonical)
    dirty_count = len([item for item in porcelain.stdout.split("\0") if item])
    worktree = (args.output_root / f"granted-hours-closure-{args.current_date}").resolve()
    worktree.parent.mkdir(parents=True, exist_ok=True)

    if worktree.exists():
        head = git_sha(worktree, "HEAD")
        status = run(["git", "status", "--porcelain"], cwd=worktree)
        tracked_dirty = [
            line
            for line in status.stdout.splitlines()
            if line and not line.endswith(" node_modules") and ".private/" not in line
        ]
        if head != origin_main or tracked_dirty:
            fail(
                "Existing isolated worktree is not a clean origin/main checkout; "
                "choose a new date path instead of mutating it"
            )
    else:
        added = run(
            ["git", "worktree", "add", "--detach", str(worktree), origin_main],
            cwd=canonical,
        )
        if added.returncode != 0:
            fail(added.stderr.strip() or "git worktree add failed")

    private_src = canonical / ".private"
    private_dst = worktree / ".private"
    private_dst.mkdir(mode=0o700, exist_ok=True)
    for name in PRIVATE_FILES:
        source = private_src / name
        if not source.is_file():
            continue
        target = private_dst / name
        shutil.copy2(source, target)
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)

    node_modules = worktree / "node_modules"
    canonical_modules = canonical / "node_modules"
    if not node_modules.exists() and canonical_modules.is_dir():
        node_modules.symlink_to(canonical_modules)

    result = {
        "schema": "granted-hours-isolated-closure-worktree-v1",
        "current_date": args.current_date,
        "worktree": str(worktree),
        "head": git_sha(worktree, "HEAD"),
        "origin_main": origin_main,
        "remote_main": remote_sha,
        "canonical": str(canonical),
        "canonical_dirty_count": dirty_count,
        "isolated_required": dirty_count > 0,
        "publication_root": str(worktree),
    }
    if result["head"] != origin_main:
        fail("Isolated worktree HEAD is not origin/main")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
