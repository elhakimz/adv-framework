# Python Example Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real, runnable Python project under `adv-framework/examples/python/` that lets a user try the local pre-push hook end-to-end — clone, run, watch it fail on one deliberate issue, fix it, watch it pass.

**Architecture:** A self-contained `pyproject.toml` (config copied from the already-reviewed `pyproject-adv-fragment.toml`, not reinvented) plus a small `calculator` package with unit and property tests, run directly against `adv-framework/assets/python/pre-push.sh` without copying it anywhere.

**Tech Stack:** Python 3.10+, setuptools (src layout), pytest + pytest-cov, Hypothesis, ruff, mypy, bandit, `build`.

## Global Constraints

- Project lives at `adv-framework/examples/python/`, a new top-level `examples/` folder — not nested inside `assets/python/`.
- `pyproject.toml` is a complete, standalone project file — not the merge-target fragment used elsewhere in this skill.
- Tool config sections (`[tool.ruff]`, `[tool.mypy]`, `[tool.bandit]`, `[tool.pytest.ini_options]`) are copied verbatim in spirit from `adv-framework/assets/python/pyproject-adv-fragment.toml`, trimmed to only what this example actually exercises (no `regression` pytest marker, no syrupy/schemathesis/alembic — this example has no regression tests and the local hook doesn't run Contract/Regression anyway).
- The calculator functions and tests follow the "calculator" theme already used for example tests elsewhere in this skill (Node.js/Go/Rust).
- The deliberate failure is exactly one thing: a single-quoted string literal in `calculator/__init__.py` that `ruff format --check .` flags but `ruff check .` / `mypy --strict` / `bandit` do not. It must not be present until Task 3 — Tasks 1–2 produce correctly-formatted code.
- No regression tests, no `core.hooksPath` wiring against this repo — see the design's Non-goals.
- **Python interpreter**: this machine's `python` on PATH is an MSYS2 build with no `pip`. A separate, real Python 3.10 install with a working `pip` exists at `C:\Users\HP\AppData\Local\Programs\Python\Python310\python.exe` — use that interpreter's full path for every `pip`/`python` command in this plan (e.g. `"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pip install -e ".[dev]"`, then that same interpreter's `Scripts/` dir for `pytest`/`ruff`/`mypy`/`bandit`, or invoke each as `python.exe -m <tool>`). Real end-to-end verification IS possible in this environment — do not skip straight to a `py_compile`-only fallback. Only fall back to `python -m py_compile <file>` (noting it explicitly in your report) if a specific tool genuinely fails to install after a real attempt, and flag that specific failure for human follow-up rather than silently treating the whole task as unverifiable.
- **Python version floor**: only Python 3.10 is available on this machine, so `requires-python`, ruff's `target-version`, and mypy's `python_version` all target **3.10**, not 3.12 (the version the rest of this skill's CI configs happen to use elsewhere) — this example prioritizes actually running on whatever a user has installed over matching an arbitrary CI image version. Nothing in the calculator code needs anything newer than 3.10.

---

## Task 1: Project scaffolding + calculator module + unit tests

**Files:**
- Create: `adv-framework/examples/python/pyproject.toml`
- Create: `adv-framework/examples/python/src/calculator/__init__.py`
- Create: `adv-framework/examples/python/tests/test_calculator.py`

**Interfaces:**
- Produces: `calculator.add(a: int, b: int) -> int`, `calculator.subtract(a: int, b: int) -> int`, `calculator.multiply(a: int, b: int) -> int`, `calculator.divide(a: int, b: int) -> float` (raises `ZeroDivisionError` if `b == 0`). Task 2's property tests and Task 3's deliberate edit both depend on these exact names and signatures.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "adv-example-calculator"
version = "0.1.0"
description = "Runnable example demonstrating the ADV framework's local pre-push verification hook (Python)."
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "ruff>=0.7.0",
    "mypy>=1.13.0",
    "bandit>=1.7.10",
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "hypothesis>=6.115.0",
    "build>=1.2.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

# ---------------------------------------------------------------------------
# ruff — lint + format, replaces flake8/isort/black in one tool
# ---------------------------------------------------------------------------
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = [
    "E", "F", "W",   # pycodestyle + pyflakes core
    "I",             # isort (import ordering)
    "UP",            # pyupgrade — flags outdated syntax
    "B",             # bugbear — common bug patterns
    "C4",            # comprehension simplifications
    "SIM",           # code simplification suggestions
]
ignore = []

[tool.ruff.lint.isort]
known-first-party = ["calculator"]

# ---------------------------------------------------------------------------
# mypy — strict typing gate
# ---------------------------------------------------------------------------
[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

# ---------------------------------------------------------------------------
# bandit — Python-specific SAST
# ---------------------------------------------------------------------------
[tool.bandit]
exclude_dirs = ["tests", ".venv"]

# ---------------------------------------------------------------------------
# pytest — the `property` marker is what lets the hook run it in isolation
# via `-m property` / `-m "not property and not regression"`
# ---------------------------------------------------------------------------
[tool.pytest.ini_options]
markers = [
    "property: Hypothesis-based property/invariant tests (slower, run in their own CI stage)",
]
testpaths = ["tests"]
addopts = "--strict-markers"

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*"]
```

- [ ] **Step 2: Write the failing unit tests**

```python
# adv-framework/examples/python/tests/test_calculator.py
import pytest

from calculator import add, divide, multiply, subtract


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5


def test_subtract_returns_difference() -> None:
    assert subtract(5, 3) == 2


def test_multiply_returns_product() -> None:
    assert multiply(4, 3) == 12


def test_divide_returns_quotient() -> None:
    assert divide(10, 2) == 5.0


def test_divide_by_zero_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
```

- [ ] **Step 3: Confirm the tests fail for the right reason**

Use the Python 3.10 interpreter at `C:\Users\HP\AppData\Local\Programs\Python\Python310\python.exe` (see Global Constraints) for every command below — not whatever `python`/`pip` resolve to on PATH.

From `adv-framework/examples/python/`, run:
`"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pip install -e ".[dev]"`
then:
`"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/test_calculator.py -v`

Expected: `ModuleNotFoundError: No module named 'calculator'` — the package doesn't exist yet.

If this specific interpreter is genuinely unavailable when you run this task, fall back to `python -m py_compile tests/test_calculator.py` for a syntax-only check, and say explicitly in your report which real command you couldn't run and why.

- [ ] **Step 4: Implement the calculator module**

```python
# adv-framework/examples/python/src/calculator/__init__.py
"""Simple calculator functions used to demonstrate the ADV local pre-push hook."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Return a minus b."""
    return a - b


def multiply(a: int, b: int) -> int:
    """Return the product of a and b."""
    return a * b


def divide(a: int, b: int) -> float:
    """Return a divided by b.

    Raises:
        ZeroDivisionError: if b is 0.
    """
    if b == 0:
        raise ZeroDivisionError("b must not be zero")
    return a / b
```

- [ ] **Step 5: Confirm the tests pass**

Run: `"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/test_calculator.py -v`
Expected: `5 passed`

If this fails for an environment reason (not a code bug), fall back to `python -m py_compile src/calculator/__init__.py tests/test_calculator.py`, confirm no output (exit 0), and report exactly what went wrong with the real command rather than silently treating the fallback as sufficient.

- [ ] **Step 6: Commit**

```bash
git add adv-framework/examples/python/pyproject.toml adv-framework/examples/python/src/calculator/__init__.py adv-framework/examples/python/tests/test_calculator.py
git commit -m "Add Python example project: scaffolding, calculator module, unit tests"
```

---

## Task 2: Property tests

**Files:**
- Create: `adv-framework/examples/python/tests/test_calculator_property.py`

**Interfaces:**
- Consumes: `calculator.add`, `calculator.multiply`, `calculator.divide` from Task 1 — exact same signatures, unchanged.

- [ ] **Step 1: Write the property tests**

```python
# adv-framework/examples/python/tests/test_calculator_property.py
"""Property tests for the calculator module — see tests/test_calculator.py for
the unit tests these complement. Marked `property` so the local pre-push
hook's Unit stage (`-m "not property and not regression"`) skips these and
the Property stage (`-m property`) runs only these."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from calculator import add, divide, multiply


@pytest.mark.property
@given(a=st.integers(), b=st.integers())
def test_add_is_commutative(a: int, b: int) -> None:
    assert add(a, b) == add(b, a)


@pytest.mark.property
@given(a=st.integers(), b=st.integers())
def test_multiply_is_commutative(a: int, b: int) -> None:
    assert multiply(a, b) == multiply(b, a)


@pytest.mark.property
@given(a=st.integers(), b=st.integers().filter(lambda x: x != 0))
def test_divide_never_raises_for_nonzero_divisor(a: int, b: int) -> None:
    divide(a, b)


@pytest.mark.property
@given(a=st.integers())
def test_divide_by_zero_always_raises_zero_division_error(a: int) -> None:
    with pytest.raises(ZeroDivisionError):
        divide(a, 0)
```

- [ ] **Step 2: Run the property tests**

Run: `"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/test_calculator_property.py -v -m property`
Expected: `4 passed`

If this fails for an environment reason: fall back to `python -m py_compile tests/test_calculator_property.py`, confirm no output, and report exactly what failed with the real command — same caveat as Task 1.

- [ ] **Step 3: Confirm the unit-only filter still excludes these**

Run: `"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/ -v -m "not property and not regression"`
Expected: the 5 tests from Task 1's `test_calculator.py` run and pass; none of this task's 4 property tests appear in the output.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/examples/python/tests/test_calculator_property.py
git commit -m "Add property tests to Python example project"
```

---

## Task 3: Deliberate format violation + README walkthrough

**Files:**
- Modify: `adv-framework/examples/python/src/calculator/__init__.py`
- Create: `adv-framework/examples/python/README.md`

**Interfaces:**
- Consumes: the exact file written in Task 1 — this task changes exactly one line in it.

- [ ] **Step 1: Introduce the deliberate formatting violation**

In `adv-framework/examples/python/src/calculator/__init__.py`, change the single line:

```python
        raise ZeroDivisionError("b must not be zero")
```

to:

```python
        raise ZeroDivisionError('b must not be zero')
```

(double quotes → single quotes — nothing else in the file changes). `ruff format` normalizes string quotes to double by default; `ruff check` (the lint pass, using the rule set selected in `pyproject.toml`: `E,F,W,I,UP,B,C4,SIM`) does not include a quote-style rule, so this fails formatting only, not linting, typing, or security.

- [ ] **Step 2: Confirm the violation is format-only**

Run these four commands from `adv-framework/examples/python/`, using the Python 3.10 interpreter's installed console scripts (installed in Task 1's Step 3 via `pip install -e ".[dev]"`) — either the full path to each script under `C:\Users\HP\AppData\Local\Programs\Python\Python310\Scripts\` or `"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m <tool>`:
- `ruff format --check .` — Expected: fails, reports `src/calculator/__init__.py` would be reformatted.
- `ruff check .` — Expected: passes, no issues.
- `python.exe -m mypy --strict src/` — Expected: passes, no issues.
- `python.exe -m bandit -r src/ -q` — Expected: passes, no issues.

(`ruff` is a standalone Rust binary with no `-m` invocation form — use the `Scripts/ruff.exe` installed by pip, or `python.exe -m ruff` if that's unavailable, both work.)

If any of these three tools genuinely fails to run after Task 1's install step, fall back to `python -m py_compile src/calculator/__init__.py` to confirm the file is still syntactically valid Python (single vs. double quotes doesn't affect parsing), and report exactly which tool failed and why — the "format-only failure" claim this task's whole design rests on needs the real commands, not just a syntax check.

- [ ] **Step 3: Write the README**

```markdown
# Python example — local pre-push hook demo

A minimal, runnable calculator project for trying the ADV framework's
[local pre-push verification hook](../../references/local-verification.md)
without setting anything up yourself.

## Setup

From this directory:

```bash
pip install -e ".[dev]"
```

## Run the hook

No copying needed — the hook script's commands operate on your current
directory, not on where the script file itself lives:

```bash
sh ../../assets/python/pre-push.sh
```

## What you'll see the first time

The **static** stage fails on exactly one check:

```
── static ──
  ✗ ruff format --check .
❌ static failed
```

`ruff check .`, `mypy --strict src/`, and `bandit -r src/ -q` all pass —
only formatting is broken. This project ships with `src/calculator/__init__.py`
containing one single-quoted string where `ruff format` wants double quotes,
specifically so you see the hook's collect-all-failures reporting do
something real on the very first run.

## Fix it and re-run

```bash
ruff format .
sh ../../assets/python/pre-push.sh
```

This time static, build, unit, and property should all pass.

## A note on the diff-coverage check

The hook's Unit stage includes a diff-coverage gate that compares your
changes against `origin/<default-branch>` — but this example lives inside
the ADV framework's own git repository. Right after this project is merged,
there's no diff on these files yet, so diff-coverage will trivially pass
with nothing to check. That's expected, not a sign the gate is broken —
edit a file locally (like the fix above) to see it evaluate a real diff.

## What's not exercised here

This example only has unit and property tests. The pre-push hook's
Contract, Regression, and Deploy Gate stages aren't run locally at all
(by design — see the reference doc linked above), so there's no
regression test in this project either.
```

- [ ] **Step 4: Verify the README's commands match reality**

Re-read `adv-framework/assets/python/pre-push.sh` and confirm:
- The stage order and names (`static`, `build`, `unit`, `property`) in the README's "what you'll see" section match what the script actually prints.
- The relative path `../../assets/python/pre-push.sh` is correct from `adv-framework/examples/python/` (i.e. `adv-framework/assets/python/pre-push.sh` exists at that location).

- [ ] **Step 5: Commit**

```bash
git add adv-framework/examples/python/src/calculator/__init__.py adv-framework/examples/python/README.md
git commit -m "Add deliberate format-only failure and walkthrough README to Python example"
```

---

## Plan self-review notes

- **Spec coverage**: structure (Task 1), calculator module + unit tests (Task 1), property tests (Task 2), deliberate failure + README (Task 3), diff-coverage caveat (documented in the README, Task 3 Step 3), verification limitation (called out in every task's test steps and in Global Constraints), non-goals (no regression tests, no `core.hooksPath` wiring — neither task adds either).
- **Placeholder scan**: no TBD/TODO; every step has complete file content or an exact command with expected output. The plan initially assumed no `pip` was available anywhere in this environment; corrected mid-review after finding a working Python 3.10 install at a specific path — every task now points at that interpreter explicitly for real verification, with `python -m py_compile` demoted to a genuine last-resort fallback (used only if a specific tool fails, reported by name) rather than the default path.
- **Type/interface consistency**: `add`/`subtract`/`multiply`/`divide` signatures are defined once in Task 1 and referenced identically (same names, same `(a: int, b: int)` shapes) in Task 2's property tests and Task 3's one-line edit. `divide`'s `ZeroDivisionError` behavior, established in Task 1, is exactly what Task 2's property tests assert and what Task 3's edit touches.
