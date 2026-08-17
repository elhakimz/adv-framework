# Bundle Self-Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give this repo its first deterministic self-verification — five checks over the shipped bundle (doc cross-references, SKILL.md manifest freshness, shellcheck on the seven hooks, GitLab CI structure), plus a `.gitattributes` fix for a latent CRLF defect.

**Architecture:** One self-contained Python script at `scripts/check-bundle-integrity.py` exposing a uniform `check_*(ctx) -> CheckResult` interface per check, driven by a small CLI. All content is read from **committed bytes** via `git show`, never the working tree. A `.githooks/pre-push` hook invokes it. Tests use throwaway git repos as fixtures.

**Tech Stack:** Python 3.10 (stdlib for checks 1–3; `PyYAML` for check 5; `shellcheck` binary for check 4), pytest, git.

## Global Constraints

- **Interpreter**: this machine's `python` on PATH is a pip-less MSYS2 build. The working interpreter is `C:\Users\HP\AppData\Local\Programs\Python\Python310\python.exe`. Use its full path for every command in this plan. Its `Scripts/` dir holds `pytest.exe` and `shellcheck.exe`.
- **Dependency install**: `pyyaml` and `shellcheck-py` are already installed. If a reinstall is ever needed, Avast TLS interception on this machine requires `--cert "C:\ProgramData\AVAST Software\Avast\wscert.pem"`.
- **Committed bytes, always.** Every check reads content via `git show <rev>:<path>`, never `Path.read_text()` on the working tree. Linting the working tree reports `SC1017` CRLF false positives on every Windows clone (verified during design — `git ls-files --eol` shows `i/lf w/crlf` here), and a check that cries wolf gets ignored.
- **Location**: `scripts/` at the repo root. Nothing in this plan may be placed inside `adv-framework/` — that directory is what ships to users' skill directories, and repo tooling has no purpose there.
- **Advisory, not a gate.** `references/local-verification.md` insists a pre-push hook enforces nothing. No file created by this plan may describe the checker as a gate.
- **Never a silent pass.** A check whose tool is missing must report `SKIPPED` unmistakably and must not be reportable as clean. Exit codes: **0** = all checks ran and passed; **1** = at least one finding; **2** = all runnable checks passed but at least one was skipped. *(This resolves an ambiguity in the spec, which said both "exits non-zero if any runnable check failed" and "a run with skips must never be reportable as a clean pass" — distinct exit codes satisfy both.)*
- **Doc-check scope**: `adv-framework/**/*.md` plus root `README.md` and `PROMPTING_GUIDE.md`. **Never `docs/**`** — plans and specs legitimately reference files that don't exist yet, so including them guarantees false positives.
- **Seven languages**, exact directory names: `java`, `python`, `dotnet`, `golang`, `nodejs`, `bun`, `rust`.
- **Baseline is clean.** All five checks were run manually against this repo during design and found zero real issues. Any finding on the real repo during implementation is either a new regression or a checker bug — investigate, do not "fix" the repo to satisfy a wrong check.

---

## Task 1: `.gitattributes` — enforce LF for shipped text assets

Independent of the checker. Fixes a latent defect: the LF-in-index property that makes the seven shipped hooks runnable on Linux/macOS is currently an accident of one contributor's `core.autocrlf=true`, not an enforced invariant. A contributor with different git config could commit CRLF and break every Unix user at the shebang.

**Files:**
- Create: `.gitattributes` (repo root)

**Interfaces:**
- Produces: nothing consumed by later tasks. Task 5's CRLF test guards this invariant but does not import from here.

- [ ] **Step 1: Confirm the current state is LF-in-index**

Run:
```bash
git ls-files --eol adv-framework/assets/*/pre-push.sh
```
Expected: all seven lines show `i/lf` (index is LF). The `w/` column may show `crlf` on Windows — that is the working tree and is fine.

If any line shows `i/crlf`, a CRLF file is already committed and this task must also normalize it — report that before proceeding, as it changes the task's scope.

- [ ] **Step 2: Create `.gitattributes`**

```gitattributes
# Enforce LF in the index for shipped text assets.
#
# The seven `assets/<lang>/pre-push.sh` hooks are executed by Linux and
# macOS users. A CRLF shebang makes the kernel look for an interpreter
# named `sh\r`, which fails with "bad interpreter: No such file or
# directory". Before this file existed, LF-in-index was an accident of
# one contributor's core.autocrlf setting rather than a guarantee.

* text=auto

*.sh    text eol=lf
*.py    text eol=lf
*.yml   text eol=lf
*.yaml  text eol=lf
*.toml  text eol=lf
*.json  text eol=lf
*.md    text eol=lf

# Not text: leave untouched
*.png   binary
*.jpg   binary
```

- [ ] **Step 3: Verify no committed content changes**

Adding `.gitattributes` must not rewrite anything already stored correctly. Run:
```bash
git add .gitattributes
git status --porcelain
```
Expected: exactly one line, `A  .gitattributes`. No `M` lines for any `.sh`/`.md`/`.yml` file.

If other files appear as modified, git is renormalizing — stop and report, because that means content was previously stored with CRLF and the change is larger than this task describes.

- [ ] **Step 4: Verify the rule actually applies**

Run:
```bash
git check-attr text eol -- adv-framework/assets/python/pre-push.sh
```
Expected output:
```
adv-framework/assets/python/pre-push.sh: text: set
adv-framework/assets/python/pre-push.sh: eol: lf
```

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Enforce LF in the index for shipped text assets

The seven assets/<lang>/pre-push.sh hooks run on Linux and macOS, where
a CRLF shebang fails with "bad interpreter". LF-in-index was previously
an accident of one contributor's core.autocrlf setting rather than an
enforced invariant, so a contributor with different git config could
have silently broken every Unix user.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Checker harness — committed-bytes IO, CLI, reporting

The foundation every check builds on. Deliverable: a runnable checker registering zero checks, which correctly reads committed bytes, reports, and exits with the right code.

**Files:**
- Create: `scripts/check-bundle-integrity.py`
- Create: `scripts/test_check_bundle_integrity.py`

**Interfaces:**
- Produces, and Tasks 3–5 all consume:
  - `@dataclass(frozen=True) class Finding: check: str; path: str; message: str`
  - `@dataclass class CheckResult: name: str; findings: list[Finding]; skipped_reason: str | None = None`
  - `@dataclass class Context: repo_root: Path; bundle_root: Path; rev: str`
  - `def read_committed(ctx: Context, rel_path: str) -> str | None` — decoded UTF-8 text of the file at `rev`, or `None` if absent
  - `def committed_paths(ctx: Context) -> set[str]` — every repo-relative path committed at `rev`, forward slashes
  - `def committed_dirs(ctx: Context) -> set[str]` — every directory prefix implied by those paths, no trailing slash
  - `CHECKS: list[Callable[[Context], CheckResult]]` — the registry the CLI iterates; Tasks 3–5 append to it
  - `DOC_GLOBS`, `LANGS`, `EXTS` module constants
- Test helper produced here and reused by Tasks 3–5: `make_repo(tmp_path, files, *, crlf_paths=())`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_check_bundle_integrity.py`:

```python
"""Tests for check-bundle-integrity.py.

Fixtures are real throwaway git repos, because the checker reads
committed bytes rather than the working tree — a fixture that only
writes files to disk would not exercise the real code path.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("check-bundle-integrity.py")
_spec = importlib.util.spec_from_file_location("bundle_check", _MODULE_PATH)
bc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc)


def make_repo(tmp_path: Path, files: dict[str, str], *, crlf_paths=()) -> Path:
    """Create a git repo containing `files` (rel path -> text), committed.

    core.autocrlf is forced off so fixtures control line endings exactly.
    Without this, a machine with autocrlf=true would silently normalize
    the CRLF fixture to LF on commit, making that test vacuous.
    """
    run = lambda *a: subprocess.run(a, cwd=tmp_path, check=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
    run("git", "init", "-q")
    run("git", "config", "core.autocrlf", "false")
    run("git", "config", "user.email", "fixture@example.com")
    run("git", "config", "user.name", "Fixture")
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        newline = "\r\n" if rel in crlf_paths else "\n"
        p.write_text(content, encoding="utf-8", newline=newline)
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "fixture")
    return tmp_path


def ctx_for(tmp_path: Path) -> "bc.Context":
    return bc.Context(repo_root=tmp_path,
                      bundle_root=tmp_path / "adv-framework",
                      rev="HEAD")


def test_read_committed_returns_text(tmp_path):
    make_repo(tmp_path, {"adv-framework/SKILL.md": "# Hello\n"})
    assert bc.read_committed(ctx_for(tmp_path), "adv-framework/SKILL.md") == "# Hello\n"


def test_read_committed_missing_returns_none(tmp_path):
    make_repo(tmp_path, {"adv-framework/SKILL.md": "# Hello\n"})
    assert bc.read_committed(ctx_for(tmp_path), "adv-framework/nope.md") is None


def test_read_committed_ignores_worktree_edits(tmp_path):
    """The load-bearing property: uncommitted edits must be invisible."""
    make_repo(tmp_path, {"adv-framework/SKILL.md": "# Committed\n"})
    (tmp_path / "adv-framework" / "SKILL.md").write_text("# Dirty\n", encoding="utf-8")
    assert bc.read_committed(ctx_for(tmp_path), "adv-framework/SKILL.md") == "# Committed\n"


def test_committed_paths_and_dirs(tmp_path):
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": "#!/usr/bin/env sh\n"})
    c = ctx_for(tmp_path)
    assert "adv-framework/assets/python/pre-push.sh" in bc.committed_paths(c)
    assert "adv-framework/assets/python" in bc.committed_dirs(c)
    assert "adv-framework/assets" in bc.committed_dirs(c)


def test_exit_code_zero_when_all_pass():
    results = [bc.CheckResult("a", []), bc.CheckResult("b", [])]
    assert bc.exit_code_for(results) == 0


def test_exit_code_one_when_any_finding():
    results = [bc.CheckResult("a", [bc.Finding("a", "f.md", "bad")]),
               bc.CheckResult("b", [], skipped_reason="no tool")]
    assert bc.exit_code_for(results) == 1


def test_exit_code_two_when_skipped_but_no_findings():
    results = [bc.CheckResult("a", []), bc.CheckResult("b", [], skipped_reason="no tool")]
    assert bc.exit_code_for(results) == 2


def test_render_marks_skips_unmistakably(capsys):
    bc.render([bc.CheckResult("shellcheck", [], skipped_reason="shellcheck not on PATH")])
    out = capsys.readouterr().out
    assert "SKIPPED" in out
    assert "shellcheck not on PATH" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v
```
Expected: collection error — `check-bundle-integrity.py` does not exist yet.

- [ ] **Step 3: Write the harness**

Create `scripts/check-bundle-integrity.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v
```
Expected: `8 passed`.

- [ ] **Step 5: Run against the real repo**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py
```
Expected: no check lines (registry is empty), exit code 0. Confirm with `echo $?`.

- [ ] **Step 6: Commit**

```bash
git add scripts/check-bundle-integrity.py scripts/test_check_bundle_integrity.py
git commit -m "$(cat <<'EOF'
Add bundle self-check harness: committed-bytes IO, CLI, reporting

Foundation for the five checks. Reads content via `git show` rather than
the working tree, because on Windows checkouts the tree holds CRLF while
the index holds LF — linting the tree reports carriage-return errors that
do not exist in what ships.

Exit codes distinguish a clean pass (0) from a pass with skipped checks
(2), so a missing tool can never be reported as clean.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Checks 1 and 2 — path references and documentary references

Both scan the same doc set under the same resolution rule, so they belong together.

**Files:**
- Modify: `scripts/check-bundle-integrity.py` (add two check functions, register both)
- Modify: `scripts/test_check_bundle_integrity.py` (append tests)

**Interfaces:**
- Consumes from Task 2: `Finding`, `CheckResult`, `Context`, `read_committed`, `committed_paths`, `committed_dirs`, `doc_paths`, `CHECKS`, `LANGS`, `EXTS`, and the test helpers `make_repo` / `ctx_for`.
- Produces: `check_path_refs(ctx) -> CheckResult` (name `"path-refs"`), `check_doc_refs(ctx) -> CheckResult` (name `"doc-refs"`), and `resolve_bases(ctx, containing_rel) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_check_bundle_integrity.py`:

```python
# --------------------------------------------------------------------
# Check 1: path references
# --------------------------------------------------------------------

def test_path_ref_resolving_in_bundle_passes(tmp_path):
    make_repo(tmp_path, {
        "adv-framework/SKILL.md": "See `references/gate-structure.md` for detail.\n",
        "adv-framework/references/gate-structure.md": "# Gates\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_bundle_ref_resolving_only_at_repo_root_fails(tmp_path):
    """The original defect: a bundle file pointing outside the bundle."""
    make_repo(tmp_path, {
        "adv-framework/SKILL.md": "See `docs/notes/thing.md` for detail.\n",
        "docs/notes/thing.md": "# Thing\n",
    })
    findings = bc.check_path_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "docs/notes/thing.md" in findings[0].message


def test_path_ref_resolving_nowhere_fails(tmp_path):
    make_repo(tmp_path, {"adv-framework/SKILL.md": "See `references/ghost.md`.\n"})
    assert len(bc.check_path_refs(ctx_for(tmp_path)).findings) == 1


def test_bare_filename_is_not_treated_as_a_path(tmp_path):
    """`pre-push.sh`, `mypy`, `.gitlab-ci.yml` are mentions, not paths."""
    make_repo(tmp_path, {
        "adv-framework/SKILL.md":
            "Run `pre-push.sh`, install `mypy`, create `.gitlab-ci.yml`.\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_lang_placeholder_requires_all_seven(tmp_path):
    files = {"adv-framework/SKILL.md": "Copy `assets/<lang>/pre-push.sh`.\n"}
    for lang in bc.LANGS:
        if lang != "rust":
            files[f"adv-framework/assets/{lang}/pre-push.sh"] = "#!/usr/bin/env sh\n"
    make_repo(tmp_path, files)
    findings = bc.check_path_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "rust" in findings[0].message


def test_lang_placeholder_all_seven_present_passes(tmp_path):
    files = {"adv-framework/SKILL.md": "Copy `assets/<lang>/pre-push.sh`.\n"}
    for lang in bc.LANGS:
        files[f"adv-framework/assets/{lang}/pre-push.sh"] = "#!/usr/bin/env sh\n"
    make_repo(tmp_path, files)
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_directory_conventions_are_not_checked(tmp_path):
    """Trailing-slash tokens are conventions, artifacts, or URL fragments.

    Checking these produced 31 false positives against the real repo.
    """
    make_repo(tmp_path, {
        "adv-framework/SKILL.md":
            "Put them in `tests/unit/`, ignore `coverage/`, POST to `/issues/`.\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_glob_patterns_are_not_checked(tmp_path):
    make_repo(tmp_path, {
        "adv-framework/SKILL.md":
            "Files `tests/*.rs` and `assets/bun/tests/{unit,property}/*.test.ts`.\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_external_allowlist_is_not_checked(tmp_path):
    """`.claude/settings.json` names a file in the reader's project."""
    make_repo(tmp_path, {"README.md": "Configure `.claude/settings.json`.\n"})
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_bundle_doc_may_not_use_repo_root_prefix(tmp_path):
    """From an installed bundle, `adv-framework/x` means adv-framework/adv-framework/x."""
    make_repo(tmp_path, {
        "adv-framework/references/g.md": "See `adv-framework/examples/python/foo.md`.\n",
        "adv-framework/examples/python/foo.md": "# Foo\n",
    })
    findings = bc.check_path_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "adv-framework/" in findings[0].message


def test_root_readme_may_use_repo_root_prefix(tmp_path):
    """The rule is bundle-only: README.md legitimately uses repo-root paths."""
    make_repo(tmp_path, {
        "README.md": "See `adv-framework/SKILL.md`.\n",
        "adv-framework/SKILL.md": "# Skill\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_root_readme_resolves_from_repo_root(tmp_path):
    make_repo(tmp_path, {
        "README.md": "See `adv-framework/SKILL.md`.\n",
        "adv-framework/SKILL.md": "# Skill\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


# --------------------------------------------------------------------
# Check 2: documentary references
# --------------------------------------------------------------------

def test_quoted_section_present_passes(tmp_path):
    make_repo(tmp_path, {
        "adv-framework/references/g.md":
            'See SKILL.md\'s "Guardrails against agent-specific failure modes".\n',
        "adv-framework/SKILL.md":
            "## Guardrails against agent-specific failure modes\n",
    })
    assert bc.check_doc_refs(ctx_for(tmp_path)).findings == []


def test_quoted_section_wrong_by_one_word_fails(tmp_path):
    """The exact original defect: 'Guarding' vs 'Guardrails'."""
    make_repo(tmp_path, {
        "adv-framework/references/g.md":
            'See SKILL.md\'s "Guarding against agent-specific failure modes".\n',
        "adv-framework/SKILL.md":
            "## Guardrails against agent-specific failure modes\n",
    })
    findings = bc.check_doc_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "Guarding against agent-specific failure modes" in findings[0].message


def test_bare_readme_reference_from_bundle_fails(tmp_path):
    """`the README's "..."` from inside the bundle: README does not ship."""
    make_repo(tmp_path, {
        "adv-framework/references/g.md": 'See the README\'s "Some Section".\n',
        "README.md": "## Some Section\n",
    })
    findings = bc.check_doc_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "README" in findings[0].message
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v -k "path_ref or placeholder or bare_filename or directory_reference or root_readme or quoted_section or bare_readme"
```
Expected: all fail with `AttributeError: module 'bundle_check' has no attribute 'check_path_refs'`.

- [ ] **Step 3: Implement both checks**

Insert into `scripts/check-bundle-integrity.py`, after `doc_paths` and before `exit_code_for`:

```python
BACKTICK_RE = re.compile(r"`([^`\n]+)`")

# `<doc>'s "Section Title"` — doc may be `SKILL.md`, `gate-structure.md`,
# or the bare word README (the original defect wrote "the README's").
DOC_REF_RE = re.compile(r"\b(README|[A-Za-z0-9_.-]+\.md)'s\s+\"([^\"]+)\"")

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


def _exists(candidate: str, paths: set[str]) -> bool:
    return candidate in paths


def _join(base: str, token: str) -> str:
    return f"{base}/{token}" if base else token


def check_path_refs(ctx: Context) -> CheckResult:
    """Backticked tokens that look like file paths must resolve.

    A token counts as a path only if it contains '/', ends in a known
    extension, has no glob metacharacter, and is not absolute. Anything
    else is a *mention*: a tool name (`mypy`), an artifact (`coverage/`),
    a URL fragment (`/issues/`), or a file the reader creates in their
    own project (`.gitlab-ci.yml`).

    Directory references are deliberately NOT checked. Counting
    trailing-slash tokens as directories produced 31 false positives
    against this repo -- directory conventions describing the reader's
    project, REST URL fragments, and globs -- versus zero real defects.
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
            if not token.endswith(EXTS):
                continue
            expansions = ([token.replace("<lang>", lang) for lang in LANGS]
                          if "<lang>" in token else [token])
            for expanded in expansions:
                if not any(_exists(_join(b, expanded), paths) for b in bases):
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
                           if _exists(_join(b, filename), paths)), None)
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


CHECKS.extend([check_path_refs, check_doc_refs])
```

Add `import re` to the imports at the **top** of the file, alongside the existing ones — not mid-file.

- [ ] **Step 4: Run the full test file**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v
```
Expected: `23 passed`.

- [ ] **Step 5: Fix the one genuine finding this check surfaces**

The new bundle-prefix rule flags a real defect at `adv-framework/references/local-verification.md:63`, which currently reads:

```
A runnable example with the hook already wired up lives at
`adv-framework/examples/python/` — try it there first if you want to see
the hook work before setting one up in your own project.
```

From inside an installed bundle that path resolves to `adv-framework/adv-framework/examples/python/`. Replace those three lines with:

```
A runnable example with the hook already wired up lives at
`examples/python/`, relative to this bundle's root — try it there first
if you want to see the hook work before setting one up in your own
project.
```

Naming the base explicitly ("relative to this bundle's root") keeps it correct for both audiences: someone reading an installed skill, and someone browsing a clone of the repo.

- [ ] **Step 6: Run against the real repo**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py
```
Expected: `ok  path-refs` and `ok  doc-refs`, exit 0.

If anything else is reported, investigate before proceeding: with the revised ruleset the repo is expected clean apart from the Step 5 fix, so a further finding means either a real regression or a checker bug. Do not edit `adv-framework/` to satisfy the checker without first confirming the checker is right — Step 5 is the one edit this task authorises, and only because it was adjudicated as a genuine defect.

- [ ] **Step 7: Commit**

```bash
git add scripts/check-bundle-integrity.py scripts/test_check_bundle_integrity.py adv-framework/references/local-verification.md
git commit -m "$(cat <<'EOF'
Add path-reference and documentary-reference checks

Catches the two shapes of the cross-reference defect that reached main:
a bundle file pointing at a path that only resolves from the repo root
(broken for every installation, since the bundle ships alone), and a
quoted section title that does not exist in the doc it names.

A token counts as a path only when it has a slash, a known extension, no
glob metacharacter, and no leading slash. Bare names like `mypy`,
directory conventions like `coverage/`, and URL fragments like `/issues/`
are mentions; checking them produced 31 false positives against this repo
versus zero real defects.

Also fixes the one genuine defect the new bundle-prefix rule surfaced:
local-verification.md pointed at `adv-framework/examples/python/`, which
from an installed bundle resolves to adv-framework/adv-framework/... —
the same defect class as the dead README pointer that motivated this
checker in the first place.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Check 3 — SKILL.md manifest freshness tripwire

**Files:**
- Modify: `scripts/check-bundle-integrity.py` (add check, implement `update_manifest`)
- Create: `scripts/heading-manifest.json`
- Modify: `scripts/test_check_bundle_integrity.py` (append tests)

**Interfaces:**
- Consumes from Tasks 2–3: `Finding`, `CheckResult`, `Context`, `read_committed`, `committed_paths`, `CHECKS`, `HEADING_RE`, and test helpers.
- Produces: `check_manifest(ctx) -> CheckResult` (name `"manifest"`), `heading_hash(text) -> str`, `manifest_path(ctx) -> Path`, and a real `update_manifest(ctx) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_check_bundle_integrity.py`:

```python
# --------------------------------------------------------------------
# Check 3: manifest freshness tripwire
# --------------------------------------------------------------------
import json

_REF = "adv-framework/references/gate-structure.md"


def _repo_with_manifest(tmp_path, ref_body: str, recorded_body: str | None = None):
    repo = make_repo(tmp_path, {_REF: ref_body, "adv-framework/SKILL.md": "# S\n"})
    body = ref_body if recorded_body is None else recorded_body
    (repo / "scripts").mkdir(exist_ok=True)
    (repo / "scripts" / "heading-manifest.json").write_text(
        json.dumps({_REF: bc.heading_hash(body)}, indent=2), encoding="utf-8")
    return repo


def test_manifest_unchanged_passes(tmp_path):
    _repo_with_manifest(tmp_path, "## One\n\n## Two\n")
    assert bc.check_manifest(ctx_for(tmp_path)).findings == []


def test_manifest_stale_when_heading_added(tmp_path):
    _repo_with_manifest(tmp_path, "## One\n\n## Two\n\n## Three\n",
                        recorded_body="## One\n\n## Two\n")
    findings = bc.check_manifest(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "--update" in findings[0].message


def test_manifest_detects_h3_change(tmp_path):
    """### matters: SKILL.md's bullet names ### subsections by name."""
    _repo_with_manifest(tmp_path, "## One\n\n### Sub A\n",
                        recorded_body="## One\n\n### Sub B\n")
    assert len(bc.check_manifest(ctx_for(tmp_path)).findings) == 1


def test_manifest_detects_heading_rename_not_just_count(tmp_path):
    _repo_with_manifest(tmp_path, "## Renamed\n\n## Two\n",
                        recorded_body="## One\n\n## Two\n")
    assert len(bc.check_manifest(ctx_for(tmp_path)).findings) == 1


def test_update_rewrites_manifest(tmp_path):
    repo = _repo_with_manifest(tmp_path, "## One\n\n## Two\n\n## Three\n",
                               recorded_body="## One\n\n## Two\n")
    c = ctx_for(tmp_path)
    assert bc.check_manifest(c).findings          # stale before
    assert bc.update_manifest(c) == 0
    assert bc.check_manifest(c).findings == []    # clean after


def test_heading_hash_ignores_body_text(tmp_path):
    """Only headings matter — prose edits must not trip the wire."""
    assert bc.heading_hash("## A\n\nlots of prose\n") == bc.heading_hash("## A\n\nother prose\n")
```

- [ ] **Step 2: Run to verify they fail**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v -k manifest or heading_hash
```
Expected: failures — `heading_hash` and `check_manifest` do not exist.

- [ ] **Step 3: Implement**

Add `import hashlib` and `import json` to the imports. Insert after `check_doc_refs`, and replace the placeholder `update_manifest`:

```python
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
    mpath = manifest_path(ctx)
    if not mpath.exists():
        res.findings.append(Finding(
            "manifest", "scripts/heading-manifest.json",
            "manifest missing; create it with --update"))
        return res

    recorded = json.loads(mpath.read_text(encoding="utf-8"))
    for doc in _reference_docs(ctx):
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
        if doc not in _reference_docs(ctx):
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


CHECKS.append(check_manifest)
```

- [ ] **Step 4: Run the tests**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v
```
Expected: `25 passed`.

- [ ] **Step 5: Record the real manifest and verify clean**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py --update
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py
```
Expected: the first records 4 hashes (`gate-structure.md`, `kanban-integration.md`, `local-verification.md`, `security.md`); the second prints `ok  manifest` alongside the other two checks, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/check-bundle-integrity.py scripts/heading-manifest.json scripts/test_check_bundle_integrity.py
git commit -m "$(cat <<'EOF'
Add SKILL.md manifest freshness tripwire

SKILL.md's reference-file bullets are the routing layer that decides
whether an agent opens a reference doc at all; when two sections were
added to gate-structure.md, its bullet went stale and both became
unreachable via the intended path.

The check records a hash of each reference doc's ordered ## and ###
headings rather than trying to match SKILL.md's prose, which
deliberately does not string-match the headings it describes. It is a
tripwire, not a validator: it reports that the described input changed,
never that the prose is wrong. --update re-records deliberately.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Checks 4 and 5 — shellcheck and GitLab CI structure

Both depend on an external tool and share the skip machinery.

**Files:**
- Modify: `scripts/check-bundle-integrity.py` (add two checks, register both)
- Modify: `scripts/test_check_bundle_integrity.py` (append tests)

**Interfaces:**
- Consumes from Tasks 2–4: `Finding`, `CheckResult`, `Context`, `read_committed_bytes`, `committed_paths`, `CHECKS`, `LANGS`, and test helpers.
- Produces: `check_shellcheck(ctx) -> CheckResult` (name `"shellcheck"`), `check_ci_structure(ctx) -> CheckResult` (name `"ci-structure"`).

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_check_bundle_integrity.py`:

```python
# --------------------------------------------------------------------
# Checks 4 and 5: shellcheck and CI structure
# --------------------------------------------------------------------
import shutil

_CLEAN_SH = "#!/usr/bin/env sh\nset -u\necho \"hello\"\n"
# SC2086: unquoted $x is word-split. A real bug sh -n cannot see.
_DIRTY_SH = "#!/usr/bin/env sh\nx=\"a b\"\necho $x\n"

_GOOD_CI = """\
stages:
  - static
  - unit

lint:
  stage: static
  script:
    - echo lint

test:
  stage: unit
  needs: ["lint"]
  script:
    - echo test
"""

needs_shellcheck = pytest.mark.skipif(
    shutil.which("shellcheck") is None, reason="shellcheck not installed")


@needs_shellcheck
def test_shellcheck_clean_script_passes(tmp_path):
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": _CLEAN_SH})
    assert bc.check_shellcheck(ctx_for(tmp_path)).findings == []


@needs_shellcheck
def test_shellcheck_catches_unquoted_expansion(tmp_path):
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": _DIRTY_SH})
    findings = bc.check_shellcheck(ctx_for(tmp_path)).findings
    assert findings and "SC2086" in findings[0].message


@needs_shellcheck
def test_shellcheck_catches_committed_crlf(tmp_path):
    """Guards the .gitattributes invariant: CRLF in the index breaks Unix."""
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": _CLEAN_SH},
              crlf_paths=("adv-framework/assets/python/pre-push.sh",))
    findings = bc.check_shellcheck(ctx_for(tmp_path)).findings
    assert findings and any("CRLF" in f.message or "SC1017" in f.message
                            for f in findings)


def test_shellcheck_missing_tool_is_skipped_not_passed(tmp_path, monkeypatch):
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": _CLEAN_SH})
    monkeypatch.setattr(bc.shutil, "which", lambda name: None)
    result = bc.check_shellcheck(ctx_for(tmp_path))
    assert result.skipped_reason is not None
    assert result.findings == []
    assert bc.exit_code_for([result]) == 2   # never a clean 0


def test_ci_structure_valid_pipeline_passes(tmp_path):
    make_repo(tmp_path, {"adv-framework/assets/python/gitlab-ci-python-adv.yml": _GOOD_CI})
    assert bc.check_ci_structure(ctx_for(tmp_path)).findings == []


def test_ci_structure_undeclared_stage_fails(tmp_path):
    bad = _GOOD_CI.replace("  stage: unit", "  stage: nonexistent")
    make_repo(tmp_path, {"adv-framework/assets/python/gitlab-ci-python-adv.yml": bad})
    findings = bc.check_ci_structure(ctx_for(tmp_path)).findings
    assert findings and "nonexistent" in findings[0].message


def test_ci_structure_dangling_needs_fails(tmp_path):
    bad = _GOOD_CI.replace('needs: ["lint"]', 'needs: ["ghost"]')
    make_repo(tmp_path, {"adv-framework/assets/python/gitlab-ci-python-adv.yml": bad})
    findings = bc.check_ci_structure(ctx_for(tmp_path)).findings
    assert findings and "ghost" in findings[0].message


def test_ci_structure_template_stub_jobs_are_not_findings(tmp_path):
    """sast/dependency_scanning/secret_detection have no script by design."""
    stub = _GOOD_CI + "\nsast:\n  stage: static\n"
    make_repo(tmp_path, {"adv-framework/assets/python/gitlab-ci-python-adv.yml": stub})
    assert bc.check_ci_structure(ctx_for(tmp_path)).findings == []
```

- [ ] **Step 2: Run to verify they fail**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v -k "shellcheck or ci_structure"
```
Expected: failures — `check_shellcheck` and `check_ci_structure` do not exist.

- [ ] **Step 3: Implement**

Add `import shutil` and `import tempfile` to the imports. Insert after `update_manifest`:

```python
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
                   if p.startswith("adv-framework/assets/")
                   and p.endswith("/pre-push.sh"))
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


CHECKS.extend([check_shellcheck, check_ci_structure])
```

Note: jobs with no `script` are **not** findings. `sast`, `dependency_scanning`, and `secret_detection` are intentionally body-less, supplied by the GitLab templates the file `include`s.

- [ ] **Step 4: Run the tests**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_check_bundle_integrity.py -v
```
Expected: `33 passed`.

- [ ] **Step 5: Run against the real repo**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py
echo "exit: $?"
```
Expected: all five checks print `ok`, exit 0. This matches the design baseline (7 pipelines structurally valid, 7 hooks shellcheck-clean). Any finding means a regression or a checker bug — investigate rather than editing `adv-framework/`.

- [ ] **Step 6: Commit**

```bash
git add scripts/check-bundle-integrity.py scripts/test_check_bundle_integrity.py
git commit -m "$(cat <<'EOF'
Add shellcheck and GitLab CI structural checks

The seven pre-push hooks were previously verified only by `sh -n`, which
proves a script parses but cannot see unquoted expansions or wrong test
operators. The seven CI pipelines had never been parsed at all.

Both run against committed bytes. shellcheck additionally rejects
committed CRLF outright, since a CRLF shebang fails on Linux and macOS
with "bad interpreter" -- guarding the .gitattributes invariant.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Pre-push hook and documentation

**Files:**
- Create: `.githooks/pre-push`
- Create: `scripts/README.md`

**Interfaces:**
- Consumes: `scripts/check-bundle-integrity.py` and its exit codes (0 clean, 1 findings, 2 skips).

- [ ] **Step 1: Write the hook**

Create `.githooks/pre-push`:

```sh
#!/usr/bin/env sh
# Runs the bundle self-check before push.
#
# ADVISORY, NOT A GATE. adv-framework/references/local-verification.md is
# emphatic that a pre-push hook enforces nothing -- it is bypassable with
# --no-verify and absent until someone runs the install step. CI and
# CODEOWNERS are what actually gate a merge.
#
# Install:  git config core.hooksPath .githooks
#
# Exit 1 (findings) blocks the push. Exit 2 (a check could not run
# because its tool is missing) warns loudly and allows it -- a missing
# optional tool should not block a contributor, but must never be
# mistaken for a clean run.
set -u

PY="${ADV_PYTHON:-python}"
"$PY" scripts/check-bundle-integrity.py
status=$?

if [ "$status" -eq 1 ]; then
  echo "bundle self-check found problems -- push blocked" >&2
  exit 1
elif [ "$status" -eq 2 ]; then
  echo "WARNING: bundle self-check was incomplete (see SKIPPED above)." >&2
  echo "Allowing the push, but this was NOT a clean run." >&2
  exit 0
fi

exit 0
```

- [ ] **Step 2: Verify the hook's own syntax and shellcheck cleanliness**

Run:
```bash
sh -n .githooks/pre-push
"/c/Users/HP/AppData/Local/Programs/Python/Python310/Scripts/shellcheck.exe" -s sh .githooks/pre-push
```
Expected: no output from either, exit 0 both times. (A self-check tool whose own hook fails shellcheck would be embarrassing and would undercut the whole exercise.)

- [ ] **Step 3: Exercise all three exit paths**

Run each and confirm the hook behaves as documented:

```bash
ADV_PYTHON="/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" sh .githooks/pre-push; echo "clean run -> $?"
```
Expected: check output, then `clean run -> 0`.

To confirm the blocking path without committing a defect, run the checker against a revision you construct in a scratch clone, or temporarily point `--rev` at a crafted commit. At minimum, confirm the mapping logic by running the hook with a stub:

```bash
printf '#!/usr/bin/env sh\nexit 1\n' > /tmp/stub.py.sh
```
Then reason through the `if` branches and state in your report which paths you exercised live versus verified by reading. Do not claim a path was tested if it was not run.

- [ ] **Step 4: Write `scripts/README.md`**

```markdown
# Repo self-check

Deterministic checks over the `adv-framework/` bundle. This is repo
tooling — it is deliberately **not** inside `adv-framework/`, because
that directory is what ships to users' skill directories.

**This is advisory, not a gate.** It runs from a pre-push hook, and
`adv-framework/references/local-verification.md` is emphatic that such
hooks enforce nothing: they are bypassable with `--no-verify` and absent
until someone runs the install step. Wiring this into CI is what would
make it a gate.

## Run it

```bash
python scripts/check-bundle-integrity.py
```

Exit codes: **0** all checks ran and passed · **1** findings · **2** all
runnable checks passed but at least one was skipped.

## Install the hook

```bash
git config core.hooksPath .githooks
```

Per-clone local config, so every contributor runs it once. It overrides
any existing `core.hooksPath` — check for one first.

## Checks

| Check | What it catches |
|---|---|
| `path-refs` | A backticked path that does not resolve. Inside the bundle, references must resolve *within the bundle* — one that only resolves from the repo root is broken for every installation. |
| `doc-refs` | `<doc>'s "Section"` where the doc or the heading does not exist. |
| `manifest` | A reference doc's headings changed since SKILL.md's bullet describing it was last verified. |
| `shellcheck` | Shell bugs in the seven shipped hooks, plus committed CRLF (which breaks the shebang on Linux/macOS). |
| `ci-structure` | A CI job using an undeclared stage, or a `needs` pointing at no job. |

All checks read **committed bytes**, never the working tree: on Windows
the tree holds CRLF while the index holds LF, so linting the tree would
report carriage-return errors that do not exist in what ships.

## Updating the heading manifest

When you intentionally add or rename a section in a reference doc,
re-read SKILL.md's bullet for that file, update it if needed, then:

```bash
python scripts/check-bundle-integrity.py --update
```

Never automate this, and never let the hook pass `--update` — accepting a
changed baseline is a human decision, the same rule this framework
applies to snapshot updates everywhere else.

## Dependencies

`pip install pyyaml shellcheck-py`. Missing tools are reported as
`SKIPPED` and produce exit 2 — never a silent pass.

## What a green run does not mean

Six of the seven `pre-push.sh` scripts have never been *executed*, and no
CI pipeline has ever run on a real GitLab runner. shellcheck proves the
absence of a class of shell bugs; it does not prove `mvn`, `cargo`, or
`bun` behave as the scripts assume. Green here means structurally sound
and internally consistent — bounded, auditable confidence, not proof.
```

- [ ] **Step 5: Commit**

```bash
git add .githooks/pre-push scripts/README.md
git commit -m "$(cat <<'EOF'
Add pre-push hook and self-check documentation

Exit 1 (findings) blocks the push; exit 2 (a check could not run) warns
loudly and allows it, so a missing optional tool does not block a
contributor but is never mistaken for a clean run.

Documents plainly what a green run does not mean: six of seven hooks
have still never been executed and no pipeline has run on a real runner.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Plan self-review notes

- **Spec coverage**: `.gitattributes` → Task 1. Harness, committed-bytes rule, exit codes, skip machinery → Task 2. Checks 1–2 with the resolution-base rule, slash rule, `<lang>` expansion → Task 3. Check 3 with `##`+`###` hashing and `--update` → Task 4. Checks 4–5 → Task 5. Hook, docs, honest framing, "what remains unproven" → Task 6. The spec's full test-fixture table maps onto tests in Tasks 2–5.
- **Resolved spec ambiguity**: the spec said both "exits non-zero if any runnable check failed" and "a run with skips must never be reportable as a clean pass." Distinct exit codes (0/1/2) satisfy both; recorded in Global Constraints so no implementer re-litigates it.
- **Fixture hazard made explicit**: `make_repo` forces `core.autocrlf=false`. Without it, a machine with `autocrlf=true` — like this one — would normalize the CRLF fixture to LF on commit, making `test_shellcheck_catches_committed_crlf` silently vacuous. That is precisely the "test that asserts nothing" the repo's own anti-gaming rules name.
- **Placeholder scan**: no TBD/TODO. Every step carries complete code or an exact command with expected output. Task 6 Step 3 explicitly instructs reporting which paths were exercised live versus read, rather than permitting an unverified claim.
- **Interface consistency**: `Finding`, `CheckResult`, `Context`, `read_committed`, `read_committed_bytes`, `committed_paths`, `committed_dirs`, `doc_paths`, `CHECKS`, `HEADING_RE`, `heading_hash`, `manifest_path`, `update_manifest`, and the test helpers `make_repo`/`ctx_for` are defined once in Tasks 2–4 and referenced under those exact names throughout. Check names (`path-refs`, `doc-refs`, `manifest`, `shellcheck`, `ci-structure`) match between implementation, `scripts/README.md`, and tests.
