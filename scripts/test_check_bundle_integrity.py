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
    return bc.Context(repo_root=tmp_path, rev="HEAD")


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


def test_committed_paths(tmp_path):
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": "#!/usr/bin/env sh\n"})
    c = ctx_for(tmp_path)
    assert "adv-framework/assets/python/pre-push.sh" in bc.committed_paths(c)


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


def test_root_readme_resolves_relative_to_its_own_directory(tmp_path):
    """A root README reference also resolves via its containing dir (""),
    not only via the `adv-framework/` prefix -- exercising the
    `bases = [containing_dir, ""]` branch of resolve_bases."""
    make_repo(tmp_path, {
        "README.md": "See `docs/notes.md`.\n",
        "docs/notes.md": "# Notes\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_mermaid_extension_is_checked(tmp_path):
    """Guards `.mermaid` staying in EXTS: a dangling reference must be flagged."""
    make_repo(tmp_path, {
        "adv-framework/SKILL.md": "See `diagrams/flow.mermaid` for detail.\n",
    })
    findings = bc.check_path_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "diagrams/flow.mermaid" in findings[0].message


# Literal, not `next(iter(bc.EXTENSIONLESS_ALLOWLIST))`: if the allowlist
# is ever emptied, iterating it at collection time would raise
# StopIteration and crash collection of this whole file instead of
# failing the one test that guards the allowlist.
_ALLOWLISTED = "assets/guardrails/CODEOWNERS"


def test_extensionless_allowlist_absent_fails(tmp_path):
    """Guards EXTENSIONLESS_ALLOWLIST staying non-empty: a reference to the
    allowlisted extension-less path must still be resolved when missing."""
    assert _ALLOWLISTED in bc.EXTENSIONLESS_ALLOWLIST
    make_repo(tmp_path, {
        "adv-framework/SKILL.md": f"See `{_ALLOWLISTED}`.\n",
    })
    findings = bc.check_path_refs(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert _ALLOWLISTED in findings[0].message


def test_extensionless_allowlist_present_passes(tmp_path):
    make_repo(tmp_path, {
        "adv-framework/SKILL.md": f"See `{_ALLOWLISTED}`.\n",
        f"adv-framework/{_ALLOWLISTED}": "* @owner\n",
    })
    assert bc.check_path_refs(ctx_for(tmp_path)).findings == []


def test_doc_paths_includes_scripts_readme(tmp_path):
    """Guards the `scripts/` arm added to doc_paths."""
    make_repo(tmp_path, {"scripts/README.md": "# Scripts\n"})
    assert "scripts/README.md" in bc.doc_paths(ctx_for(tmp_path))


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


def test_manifest_missing_reports_finding(tmp_path):
    """Neither committed nor on disk: report, don't crash."""
    make_repo(tmp_path, {_REF: "## One\n", "adv-framework/SKILL.md": "# S\n"})
    findings = bc.check_manifest(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "manifest missing" in findings[0].message


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


def test_manifest_prefers_committed_bytes_over_dirty_worktree(tmp_path):
    """The load-bearing property: a fresh worktree manifest must not mask
    a stale committed one. A stale manifest is committed (missing the
    "## Two" heading); a fresh, correct manifest is then written to the
    working tree WITHOUT being committed. check_manifest must still flag
    the doc as stale -- reading manifest_path(ctx).read_text() instead of
    the committed bytes would silently pass this."""
    stale = json.dumps({_REF: bc.heading_hash("## One\n")}, indent=2) + "\n"
    fresh = json.dumps({_REF: bc.heading_hash("## One\n\n## Two\n")}, indent=2) + "\n"
    repo = make_repo(tmp_path, {
        _REF: "## One\n\n## Two\n",
        "adv-framework/SKILL.md": "# S\n",
        "scripts/heading-manifest.json": stale,
    })
    (repo / "scripts" / "heading-manifest.json").write_text(fresh, encoding="utf-8")
    findings = bc.check_manifest(ctx_for(tmp_path)).findings
    assert len(findings) == 1
    assert "headings changed" in findings[0].message


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


@needs_shellcheck
def test_shellcheck_checks_githooks_pre_push(tmp_path):
    """Guards the `.githooks/pre-push` arm of check_shellcheck's selector."""
    make_repo(tmp_path, {".githooks/pre-push": _DIRTY_SH})
    findings = bc.check_shellcheck(ctx_for(tmp_path)).findings
    assert findings and "SC2086" in findings[0].message


def test_shellcheck_missing_tool_is_skipped_not_passed(tmp_path, monkeypatch):
    make_repo(tmp_path, {"adv-framework/assets/python/pre-push.sh": _CLEAN_SH})
    monkeypatch.setattr(bc.shutil, "which", lambda name: None)
    result = bc.check_shellcheck(ctx_for(tmp_path))
    assert result.skipped_reason is not None
    assert result.findings == []
    assert bc.exit_code_for([result]) == 2   # never a clean 0


def test_ci_structure_missing_pyyaml_is_skipped_not_passed(tmp_path, monkeypatch):
    """Mirrors test_shellcheck_missing_tool_is_skipped_not_passed: an
    absent optional dependency must report SKIPPED, never a silent pass."""
    make_repo(tmp_path, {"adv-framework/assets/python/gitlab-ci-python-adv.yml": _GOOD_CI})
    monkeypatch.setitem(sys.modules, "yaml", None)  # forces `import yaml` to raise ImportError
    result = bc.check_ci_structure(ctx_for(tmp_path))
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
