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
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

LANGS = ("java", "python", "dotnet", "golang", "nodejs", "bun", "rust")

EXTS = (".md", ".yml", ".yaml", ".toml", ".json", ".sh", ".py",
        ".xml", ".ts", ".js", ".go", ".rs", ".cs", ".props", ".mermaid")

# Extension-less shipped paths that check_path_refs should still resolve.
# EXTS-based matching can never catch these (they have no extension by
# design), so they need an explicit allowlist or a rename silently stops
# being checked.
EXTENSIONLESS_ALLOWLIST = frozenset({"assets/guardrails/CODEOWNERS"})


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


def doc_paths(ctx: Context) -> list[str]:
    """Committed doc paths in scope, in stable order."""
    out = []
    for p in sorted(committed_paths(ctx)):
        if p in ("README.md", "PROMPTING_GUIDE.md"):
            out.append(p)
        elif p.startswith("adv-framework/") and p.endswith(".md"):
            out.append(p)
        elif p.startswith("scripts/") and p.endswith(".md"):
            out.append(p)
    return out


BACKTICK_RE = re.compile(r"`([^`\n]+)`")

# `<doc>'s "Section Title"` — doc may be `SKILL.md`, `gate-structure.md`,
# or the bare word README (the original defect wrote "the README's").
# Apostrophe and quotes accept both ASCII and typographic variants: no
# typographic quotes exist in the docs today, but an editor autocorrect
# turning a straight quote into a curly one would otherwise make this
# check silently stop matching.
DOC_REF_RE = re.compile(r"\b(README|[A-Za-z0-9_.-]+\.md)['’]s\s+"
                        r"[\"“]([^\"”]+)[\"”]")

HEADING_RE = re.compile(r"^(#{2,3})\s+(.*?)\s*$", re.MULTILINE)

# A glob is a pattern, not a path to resolve.
GLOB_CHARS = frozenset("*?{}[]")

# Paths naming a file in the READER's project, not this repo.
EXTERNAL_ALLOWLIST = frozenset({".claude/settings.json"})


def resolve_bases(ctx: Context, containing_rel: str) -> list[str]:
    """Directories a reference in `containing_rel` may resolve against.

    A reference inside adv-framework/ must resolve INSIDE the bundle:
    the bundle ships alone, so a reference that only resolves from the
    repo root is broken for every installation. That is precisely the
    defect this check exists to catch, so the repo root is deliberately
    not an accepted base for bundle files.
    """
    containing_dir = "/".join(containing_rel.split("/")[:-1])
    if containing_rel.startswith("adv-framework/"):
        return [containing_dir, "adv-framework"]
    return [containing_dir, ""]


def _join(base: str, token: str) -> str:
    return f"{base}/{token}" if base else token


def check_path_refs(ctx: Context) -> CheckResult:
    """Backticked tokens that look like file paths must resolve.

    A token is checked if it contains '/', has no glob metacharacter, and
    is not absolute, AND (it ends in a known extension, OR it is in
    EXTENSIONLESS_ALLOWLIST, OR -- inside a bundle doc -- it starts with
    `adv-framework/`, which is flagged regardless of extension). That
    `adv-framework/`-prefix branch is load-bearing: the original defect
    this check caught (`adv-framework/examples/python/`) had no
    extension, so extension-gating alone would have missed it. Anything
    else is a *mention*: a tool name (`mypy`), an artifact (`coverage/`),
    a URL fragment (`/issues/`), or a file the reader creates in their
    own project (`.gitlab-ci.yml`).

    Directory references are deliberately NOT checked: a bare
    trailing-slash token (`tests/unit/`) is never resolved against the
    tree, even when it names a real directory. Counting them produced 31
    false positives against this repo -- directory conventions describing
    the reader's project, REST URL fragments, and globs -- versus zero
    real defects. This is a known, accepted coverage gap, not an
    oversight.
    """
    res = CheckResult("path-refs")
    paths = committed_paths(ctx)

    for doc in doc_paths(ctx):
        text = read_committed(ctx, doc) or ""
        in_bundle = doc.startswith("adv-framework/")
        bases = resolve_bases(ctx, doc)
        for token in BACKTICK_RE.findall(text):
            token = token.strip()
            if "/" not in token or token in EXTERNAL_ALLOWLIST:
                continue
            if token.startswith("/"):
                continue  # URL fragment or absolute path
            if GLOB_CHARS & set(token):
                continue  # a pattern, not a path
            # A bundle doc must read correctly from inside an INSTALLED
            # bundle, where a repo-root path like adv-framework/x means
            # adv-framework/adv-framework/x. This is the same defect class
            # as the dead README pointer that motivated this checker.
            if in_bundle and token.startswith("adv-framework/"):
                res.findings.append(Finding(
                    "path-refs", doc,
                    f"reference `{token}` starts with `adv-framework/` inside "
                    "the bundle; from an installed skill that resolves to "
                    "adv-framework/adv-framework/... -- make it relative to "
                    "the bundle root"))
                continue
            if not token.endswith(EXTS) and token not in EXTENSIONLESS_ALLOWLIST:
                continue
            expansions = ([token.replace("<lang>", lang) for lang in LANGS]
                          if "<lang>" in token else [token])
            for expanded in expansions:
                if not any(_join(b, expanded) in paths for b in bases):
                    res.findings.append(Finding(
                        "path-refs", doc,
                        f"reference `{expanded}` does not resolve within "
                        f"{'the bundle' if in_bundle else 'the repo'}"))
    return res


def check_doc_refs(ctx: Context) -> CheckResult:
    """`<doc>'s "Section"` — doc must resolve and contain that heading."""
    res = CheckResult("doc-refs")
    paths = committed_paths(ctx)

    for doc in doc_paths(ctx):
        text = read_committed(ctx, doc) or ""
        bases = resolve_bases(ctx, doc)
        for named, section in DOC_REF_RE.findall(text):
            filename = "README.md" if named == "README" else named
            target = next((_join(b, filename) for b in bases
                           if _join(b, filename) in paths), None)
            if target is None:
                res.findings.append(Finding(
                    "doc-refs", doc,
                    f"references {named!r}, which does not resolve within "
                    f"{'the bundle' if doc.startswith('adv-framework/') else 'the repo'}"))
                continue
            headings = [h.strip() for _, h in
                        HEADING_RE.findall(read_committed(ctx, target) or "")]
            if section not in headings:
                res.findings.append(Finding(
                    "doc-refs", doc,
                    f"{target} has no heading {section!r}"))
    return res


def heading_hash(text: str) -> str:
    """Hash the ordered ## and ### headings of a document.

    Both levels matter: SKILL.md's bullet for gate-structure.md names
    "complexity budget, suite health, real execution", which are ###
    subsections under one ## parent — a ##-only hash would miss a new or
    renamed subsection the bullet should have mentioned.
    """
    headings = [f"{hashes} {title.strip()}"
                for hashes, title in HEADING_RE.findall(text)]
    return hashlib.sha256("\n".join(headings).encode("utf-8")).hexdigest()


def manifest_path(ctx: Context) -> Path:
    return ctx.repo_root / "scripts" / "heading-manifest.json"


def _reference_docs(ctx: Context) -> list[str]:
    return sorted(p for p in committed_paths(ctx)
                  if p.startswith("adv-framework/references/") and p.endswith(".md"))


def check_manifest(ctx: Context) -> CheckResult:
    """Tripwire: flag that SKILL.md's described inputs changed.

    Deliberately does NOT judge SKILL.md's prose. Its bullets describe
    contents in wording that does not string-match the headings ("the
    full 7-gate table" describes "The 7 gates, in order"), so fuzzy
    matching would produce both false positives and false negatives.
    This only reports that the described file changed and a human should
    re-read the bullet. Zero false positives by construction.
    """
    res = CheckResult("manifest")

    # Every other input to this checker is committed bytes; the manifest
    # must be too, or a regenerated-but-uncommitted manifest on disk would
    # mask a stale committed one. Fall back to the working-tree file only
    # when the manifest has never been committed at all (first-run case).
    manifest_text = read_committed(ctx, "scripts/heading-manifest.json")
    if manifest_text is None:
        mpath = manifest_path(ctx)
        if not mpath.exists():
            res.findings.append(Finding(
                "manifest", "scripts/heading-manifest.json",
                "manifest missing; create it with --update"))
            return res
        manifest_text = mpath.read_text(encoding="utf-8")

    recorded = json.loads(manifest_text)
    ref_docs = _reference_docs(ctx)
    for doc in ref_docs:
        actual = heading_hash(read_committed(ctx, doc) or "")
        if doc not in recorded:
            res.findings.append(Finding(
                "manifest", doc,
                "not in the heading manifest; SKILL.md may need a bullet "
                "for it. Re-record with --update once SKILL.md is correct."))
        elif recorded[doc] != actual:
            res.findings.append(Finding(
                "manifest", doc,
                "headings changed since SKILL.md's manifest was last "
                "verified. Re-read SKILL.md's bullet for this file, update "
                "it if the change should be reflected there, then re-record "
                "with --update."))
    for doc in recorded:
        if doc not in ref_docs:
            res.findings.append(Finding(
                "manifest", doc,
                "recorded in the manifest but no longer committed; "
                "re-record with --update"))
    return res


def update_manifest(ctx: Context) -> int:
    """Re-record heading hashes. A deliberate human action, never automated.

    Mirrors how ADV treats snapshot updates throughout the framework.
    The pre-push hook must never pass --update.
    """
    data = {doc: heading_hash(read_committed(ctx, doc) or "")
            for doc in _reference_docs(ctx)}
    path = manifest_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(data)} reference-doc heading hashes to {path}")
    return 0


def check_shellcheck(ctx: Context) -> CheckResult:
    """Run shellcheck against the COMMITTED bytes of every shipped hook.

    Committed bytes matter twice over here: on a Windows checkout the
    working tree holds CRLF while the index holds LF, so linting the
    tree reports SC1017 errors that do not exist in what ships; and
    conversely, CRLF that really is committed would break every Unix
    user at the shebang, which this check must catch.
    """
    res = CheckResult("shellcheck")
    if shutil.which("shellcheck") is None:
        res.skipped_reason = ("shellcheck not on PATH -- install with "
                              "`pip install shellcheck-py`")
        return res

    hooks = sorted(p for p in committed_paths(ctx)
                   if (p.startswith("adv-framework/assets/")
                       and p.endswith("/pre-push.sh"))
                   or p == ".githooks/pre-push")
    with tempfile.TemporaryDirectory() as tmp:
        for hook in hooks:
            raw = read_committed_bytes(ctx, hook)
            if raw is None:
                continue
            if b"\r\n" in raw:
                res.findings.append(Finding(
                    "shellcheck", hook,
                    "committed with CRLF line endings -- a CRLF shebang "
                    "fails on Linux/macOS with 'bad interpreter'. Check "
                    ".gitattributes."))
                continue
            scratch = Path(tmp) / hook.replace("/", "_")
            scratch.write_bytes(raw)
            proc = subprocess.run(
                ("shellcheck", "-s", "sh", "-f", "gcc", str(scratch)),
                capture_output=True, text=True)
            for line in proc.stdout.splitlines():
                if line.strip():
                    res.findings.append(Finding(
                        "shellcheck", hook, line.split(":", 1)[-1].strip()))
    return res


def check_ci_structure(ctx: Context) -> CheckResult:
    """Every job's stage is declared; every `needs` target exists.

    Not full GitLab CI schema validation -- that needs GitLab's CI Lint
    API and a project token. These are the two invariants a local edit
    realistically breaks.
    """
    res = CheckResult("ci-structure")
    try:
        import yaml
    except ImportError:
        res.skipped_reason = "PyYAML not installed -- `pip install pyyaml`"
        return res

    reserved = {"stages", "variables", "cache", "include", "default",
                "workflow", "image", "before_script", "after_script"}

    pipelines = sorted(p for p in committed_paths(ctx)
                       if p.startswith("adv-framework/assets/")
                       and "/gitlab-ci-" in p and p.endswith(".yml"))
    for rel in pipelines:
        try:
            doc = yaml.safe_load(read_committed(ctx, rel) or "") or {}
        except yaml.YAMLError as exc:
            res.findings.append(Finding("ci-structure", rel,
                                        f"does not parse as YAML: {exc}"))
            continue
        stages = doc.get("stages", [])
        jobs = {k: v for k, v in doc.items()
                if k not in reserved and not k.startswith(".")
                and isinstance(v, dict)}
        for name, body in jobs.items():
            stage = body.get("stage")
            if stage is None:
                res.findings.append(Finding("ci-structure", rel,
                                            f"job {name!r} declares no stage"))
            elif stage not in stages:
                res.findings.append(Finding(
                    "ci-structure", rel,
                    f"job {name!r} uses stage {stage!r}, not in {stages}"))
            for entry in body.get("needs") or []:
                target = entry.get("job") if isinstance(entry, dict) else entry
                if target not in jobs:
                    res.findings.append(Finding(
                        "ci-structure", rel,
                        f"job {name!r} needs {target!r}, which is not a job "
                        "in this file"))
    return res


CHECKS.extend([check_path_refs, check_doc_refs, check_manifest,
               check_shellcheck, check_ci_structure])


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
    ctx = Context(repo_root=repo_root, rev=args.rev)

    if args.update:
        return update_manifest(ctx)

    results = [check(ctx) for check in CHECKS]
    render(results)
    return exit_code_for(results)


if __name__ == "__main__":
    sys.exit(main())
