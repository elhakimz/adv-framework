#!/usr/bin/env python3
"""Deterministic self-check for the adv-framework skill bundle.

Applies ADV's own ratchet rule to ADV itself: two defects reached main
that no per-file review could catch, so this adds the deterministic
checks that would have caught them.

ADVISORY, NOT A GATE. This runs from a pre-push hook, and
adv-framework/references/local-verification.md is emphatic that such
hooks enforce nothing — CI and CODEOWNERS are what gate a merge.

All content is read from COMMITTED BYTES via `git show`, never the
working tree: on Windows checkouts with core.autocrlf=true the working
tree holds CRLF while the index holds LF, so linting the working tree
reports SC1017 carriage-return errors that do not exist in what ships.

Exit codes:
    0  all checks ran and passed
    1  at least one finding
    2  all runnable checks passed, but at least one was skipped

Requires: PyYAML (check 5), shellcheck on PATH (check 4). Missing tools
are reported as SKIPPED, never silently passed.

Install note for this machine: Avast TLS interception breaks PyPI, so
    pip install --cert "C:\\ProgramData\\AVAST Software\\Avast\\wscert.pem" pyyaml shellcheck-py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

LANGS = ("java", "python", "dotnet", "golang", "nodejs", "bun", "rust")

EXTS = (".md", ".yml", ".yaml", ".toml", ".json", ".sh", ".py",
        ".xml", ".ts", ".js", ".go", ".rs", ".cs", ".props")

# Docs that are part of the published product. docs/** is deliberately
# excluded: plans and specs reference files that do not exist yet by
# design, so including them would guarantee false positives.
DOC_GLOBS = ("adv-framework/**/*.md", "README.md", "PROMPTING_GUIDE.md")


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    message: str


@dataclass
class CheckResult:
    name: str
    findings: list[Finding] = field(default_factory=list)
    skipped_reason: str | None = None


@dataclass
class Context:
    repo_root: Path
    bundle_root: Path
    rev: str = "HEAD"


CHECKS: list[Callable[[Context], CheckResult]] = []


def _git(ctx: Context, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(("git", *args), cwd=ctx.repo_root,
                          capture_output=True, text=False)


def read_committed(ctx: Context, rel_path: str) -> str | None:
    """Text of `rel_path` as committed at ctx.rev, or None if absent."""
    proc = _git(ctx, "show", f"{ctx.rev}:{rel_path}")
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace")


def read_committed_bytes(ctx: Context, rel_path: str) -> bytes | None:
    """Raw bytes as committed — needed to detect CRLF, which decoding hides."""
    proc = _git(ctx, "show", f"{ctx.rev}:{rel_path}")
    return None if proc.returncode != 0 else proc.stdout


def committed_paths(ctx: Context) -> set[str]:
    proc = _git(ctx, "ls-tree", "-r", "--name-only", ctx.rev)
    if proc.returncode != 0:
        return set()
    return {ln for ln in proc.stdout.decode("utf-8").splitlines() if ln}


def committed_dirs(ctx: Context) -> set[str]:
    dirs: set[str] = set()
    for p in committed_paths(ctx):
        parts = p.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    return dirs


def doc_paths(ctx: Context) -> list[str]:
    """Committed doc paths in scope, in stable order."""
    out = []
    for p in sorted(committed_paths(ctx)):
        if p in ("README.md", "PROMPTING_GUIDE.md"):
            out.append(p)
        elif p.startswith("adv-framework/") and p.endswith(".md"):
            out.append(p)
    return out


def exit_code_for(results: list[CheckResult]) -> int:
    if any(r.findings for r in results):
        return 1
    if any(r.skipped_reason for r in results):
        return 2
    return 0


def render(results: list[CheckResult]) -> None:
    for r in results:
        if r.skipped_reason:
            print(f"  SKIPPED  {r.name} -- {r.skipped_reason}")
        elif r.findings:
            print(f"  FAIL     {r.name} ({len(r.findings)})")
            for f in r.findings:
                print(f"             {f.path}: {f.message}")
        else:
            print(f"  ok       {r.name}")

    skipped = [r.name for r in results if r.skipped_reason]
    if skipped:
        print()
        print("  NOT A CLEAN PASS: these checks did not run: "
              + ", ".join(skipped))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rev", default="HEAD",
                    help="git revision to check (default: HEAD)")
    ap.add_argument("--update", action="store_true",
                    help="re-record the heading manifest (deliberate human action)")
    args = ap.parse_args(argv)

    repo_root = Path(
        subprocess.run(("git", "rev-parse", "--show-toplevel"),
                       capture_output=True, text=True, check=True)
        .stdout.strip())
    ctx = Context(repo_root=repo_root,
                  bundle_root=repo_root / "adv-framework",
                  rev=args.rev)

    if args.update:
        return update_manifest(ctx)

    results = [check(ctx) for check in CHECKS]
    render(results)
    return exit_code_for(results)


def update_manifest(ctx: Context) -> int:
    """Placeholder until Task 4 implements the manifest tripwire."""
    print("--update: no manifest check registered yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
