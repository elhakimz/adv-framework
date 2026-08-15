# Python Example Project — Design

**Status**: Draft, pending review
**Date**: 2026-08-15

## Motivation

The local pre-push verification feature (added earlier this session) ships seven `pre-push.sh` scripts, but none of the seven per-language `assets/<lang>/` folders contain a full runnable project — only fragments and example test files, by original design (see `docs/superpowers/specs/2026-08-15-local-pre-push-verification-design.md`'s Testing/validation plan, which explicitly deferred end-to-end verification to "a real project once available"). There's currently no way to actually try the hook without first assembling a project yourself.

This adds one real, runnable Python project so a user can try the hook end-to-end in under a minute, see it fail, fix the failure, and see it pass — a concrete demo rather than an abstract description.

## Scope

One language only (Python), one project. Not a template for all seven languages — if this proves valuable, other languages get their own follow-up spec, not a mechanical repeat bundled into this one.

## Structure

```
adv-framework/examples/python/
├── README.md
├── pyproject.toml
├── src/
│   └── calculator/
│       └── __init__.py
└── tests/
    ├── test_calculator.py
    └── test_calculator_property.py
```

Lives under a new top-level `examples/` folder (sibling to `assets/` and `references/`), not nested inside `assets/python/` — keeps "copy this into your project" template assets separate from "clone this and try it" demos.

## Contents

**`pyproject.toml`**: a complete, self-contained project file (not the existing `pyproject-adv-fragment.toml`, which is a merge-target fragment for real consuming projects). Includes `[project]` metadata, a `setuptools` src-layout build backend, the same `[project.optional-dependencies].dev` group already defined in the fragment (ruff, mypy, bandit, pytest, pytest-cov, hypothesis), and the same `[tool.ruff]`/`[tool.mypy]`/`[tool.bandit]`/`[tool.pytest.ini_options]` sections — copied from the fragment rather than reinvented, so the example matches what the skill already documents as the correct config.

**`src/calculator/__init__.py`**: typed `add`, `subtract`, `multiply`, `divide` functions (divide raises `ZeroDivisionError` on a zero divisor, deliberately, so the property test below has something real to assert about). Follows the "calculator" theme already used for the Node.js/Go/Rust example test files elsewhere in this skill, for consistency.

**`tests/test_calculator.py`**: unit tests, no marker — picked up by the default `unit-test` stage.

**`tests/test_calculator_property.py`**: Hypothesis-based property tests marked `@pytest.mark.property` — commutativity of `add`/`multiply`, and that `divide` raises exactly `ZeroDivisionError` (never something else) when the divisor is zero. Mirrors the structure of `assets/python/test_example_markers.py` but with real, runnable bodies instead of commented-out pseudocode.

**The deliberate failure**: one string literal in `calculator/__init__.py` uses single quotes where `ruff format` normalizes to double quotes. This fails `ruff format --check .` specifically. It does not fail `ruff check .` (lint), `mypy --strict`, or `bandit` — none of ruff's selected lint rules (`E,F,W,I,UP,B,C4,SIM`, per the existing fragment) enforce quote style; that's format-only. So running the hook produces exactly one failing command inside an otherwise-passing static stage — a clean, single-variable demonstration of the collect-all-failures behavior added in the main feature, without confusing overlap between multiple failing tools.

**`README.md`**: setup (`pip install -e ".[dev]"`), how to run the hook (`cd adv-framework/examples/python && sh ../../assets/python/pre-push.sh` — no copying needed, since the script's commands operate on the caller's cwd, not the script's own location), what you'll see (static stage fails on the format check, everything else passes), how to fix it (`ruff format .`), and a re-run to confirm all-green.

**Documented caveat, not solved**: this project lives inside the ADV framework's own git history. The Unit stage's diff-coverage check compares against `origin/<default-branch>` of *this* repo. On a fresh clone, right after these files are merged, there's no diff on them — so diff-coverage trivially passes with nothing to check, not because coverage is actually good. The README says this plainly so a user doesn't read a no-op pass as a real signal. (Editing a file locally after cloning, per the walkthrough's "fix and re-run" step, produces a real diff and a real coverage check.)

## Verification limitation

The current environment has no `pip` and can't install or run ruff/mypy/pytest/bandit/hypothesis. Implementation will:
- Write every file carefully, cross-checking config against the already-reviewed `pyproject-adv-fragment.toml` and `test_example_markers.py`.
- Syntax-check Python files with `python -m py_compile` (available without pip) as the only automated check possible in this environment.
- Explicitly flag in the plan and in the final report that a human with a working Python toolchain must run `pip install -e ".[dev]"` then `sh ../../assets/python/pre-push.sh` once, confirm the static stage fails only on `ruff format --check .`, run `ruff format .`, and confirm a clean re-run — this is the actual acceptance test, and it cannot be automated away in this session.

## Non-goals

- Not a template for the other six languages — a separate ask if wanted later.
- Not wiring the example up as an actual git hook (`core.hooksPath`) against the ADV framework repo itself — that would apply pre-push checks to the whole meta-repo, not just the example. The README demonstrates by direct invocation only.
- Not adding regression-test coverage to the example — the local hook doesn't run the Regression stage at all (per the main feature's scope), so an example regression test would exercise nothing the hook actually checks.
