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
# Register in sys.modules before exec: on this interpreter, dataclasses'
# KW_ONLY check does sys.modules.get(cls.__module__).__dict__ while the
# class body executes, which crashes with AttributeError on a module that
# was never registered. This is a known CPython dataclasses/importlib
# interaction bug, not specific to this file.
sys.modules[_spec.name] = bc
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
