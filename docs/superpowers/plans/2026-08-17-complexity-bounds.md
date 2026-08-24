# Algorithmic Complexity Bounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deterministic gate that verifies a human-declared algorithmic complexity bound by counting operations, closing the one failure class none of ADV's seven gates catch.

**Architecture:** A single shipped asset, `assets/python/bigo_harness.py`, instruments the *container* (not the routine) and asserts `ops(n) <= C·f(n)·tolerance`. The repo's own test suite unit-tests that asset; the runnable `examples/python/` project imports the real asset by path and proves it end to end against genuinely linear and genuinely quadratic routines. Lives inside ADV's existing Property gate (#4) — no eighth gate.

**Tech Stack:** Python 3.10, stdlib only (`math`, `hashlib` not needed — no dependencies), pytest.

## Global Constraints

- **Interpreter**: `python` on PATH is a pip-less MSYS2 build. Use `C:\Users\HP\AppData\Local\Programs\Python\Python310\python.exe` for every command. `pytest.exe` lives in its `Scripts/`.
- **No new dependencies.** The harness is stdlib-only. It ships to users; a dependency would be a tax on every consumer.
- **Operation counting, never timing.** No `time`, `timeit`, `perf_counter`, or benchmark library anywhere in the harness. Timing is non-deterministic and this repo documents flaky gates as worse than none.
- **Tolerance default `1.30`** — validated band is 1.10–3.00; 1.05 and 5.00 both misclassify. Do not change the default.
- **Minimum size span `64`** — `max(sizes)/min(sizes)` must be ≥ 64. Verified to give a 2.33× discrimination margin against the 1.30 tolerance.
- **Calibrate `C` on the SMALLEST sample** — `C = ops(n₀)/f(n₀)`. Calibrating on the largest would let a too-fast-growing curve pass. Guard `f(n₀)==0` with an `or 1.0` fallback; `math.log2(1) == 0` raises `ZeroDivisionError`, confirmed.
- **Wide instrumentation is mandatory, not optional.** `__getitem__`, `__iter__`, AND `__contains__`. Counting only `__getitem__` let a genuinely O(n²) routine report exactly `n` ops and pass a declared O(n) bound — a gate that lies.
- **All three guards raise `AssertionError`** — a violated guard is a test failure, never a warning.
- **Not an eighth gate.** This sits inside Property (#4) and reuses the existing `property` pytest marker. Do not add a stage, a marker, or a pipeline job.
- **Nothing may describe this as proving true complexity.** It verifies a *declared bound* against *counted operations*. Blind spots (`xs.count()`, `xs.index()`) must be documented wherever the harness is described.
- **Seven languages exist** (`java`, `python`, `dotnet`, `golang`, `nodejs`, `bun`, `rust`) but this change ships **Python only**. Do not add assets for the other six.

---

## Task 1: The harness asset and its unit tests

**Files:**
- Create: `adv-framework/assets/python/bigo_harness.py`
- Create: `scripts/test_bigo_harness.py`

The harness is a shipped asset, but its tests live in `scripts/` because that is where this repo keeps verification of its own artifacts (alongside `scripts/test_check_bundle_integrity.py`). Shipping untested code in an asset is precisely what this framework criticises.

**Interfaces:**
- Produces, consumed by Tasks 2 and 3:
  - `class CountingList(list)` — attribute `reads: int`; counts `__getitem__`, `__iter__`, `__contains__`
  - `GROWTH: dict[str, Callable[[int], float]]` — keys exactly `"O(1)"`, `"O(log n)"`, `"O(n)"`, `"O(n log n)"`, `"O(n^2)"`
  - `def measure_ops(routine, sizes, *, make_input=None) -> list[tuple[int, int]]`
  - `def assert_complexity_bound(routine, bound, sizes, *, make_input=None, tolerance=1.30) -> None`
  - `MIN_SPAN = 64`, `DEFAULT_TOLERANCE = 1.30`
  - `routine` is always called as `routine(data)` with a single argument; callers needing extra arguments close over them in a lambda.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_bigo_harness.py`:

```python
"""Tests for the shipped bigo_harness asset.

These live in scripts/ because this is where the repo verifies its own
artifacts. The harness ships to users; untested shipped code is the thing
this framework exists to argue against.
"""
import importlib.util
import math
import random
import sys
from pathlib import Path

import pytest

_HARNESS = (Path(__file__).resolve().parents[1]
            / "adv-framework" / "assets" / "python" / "bigo_harness.py")
_spec = importlib.util.spec_from_file_location("bigo_harness", _HARNESS)
bh = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bh          # dataclass/annotation resolution needs this
_spec.loader.exec_module(bh)


# --- routines under test, deliberately uninstrumented -------------------

def linear_scan(data):                      # O(n)
    total = 0
    for x in data:
        total += x
    return total


def binary_probe(data):                     # O(log n)
    lo, hi = 0, len(data) - 1
    target = len(data) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if data[mid] == target:
            return mid
        if data[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def quadratic_mixed(data):
    """Genuinely O(n^2). Outer indexes, inner iterates.

    This is the exact shape that defeated a __getitem__-only harness:
    it reported n ops and passed a declared O(n) bound.
    """
    total = 0
    for i in range(len(data)):
        _ = data[i]
        for y in data:
            total += y
    return total


SIZES = [16, 64, 256, 1024]                 # 64x span


# --- CountingList coverage ----------------------------------------------

def test_counts_indexing():
    c = bh.CountingList(range(100))
    for i in range(100):
        _ = c[i]
    assert c.reads == 100


def test_counts_iteration():
    c = bh.CountingList(range(100))
    _ = [x for x in c]
    assert c.reads == 100


def test_counts_membership():
    c = bh.CountingList(range(100))
    _ = 50 in c
    assert c.reads == 100


def test_len_is_not_counted():
    """len() is genuinely O(1); counting it would be wrong."""
    c = bh.CountingList(range(100))
    _ = len(c)
    assert c.reads == 0


# --- the load-bearing regression ----------------------------------------

def test_quadratic_with_iterating_inner_loop_is_not_mistaken_for_linear():
    """Guards the silent-pass hole that defeated the first design.

    A __getitem__-only CountingList reports exactly n ops here and passes
    O(n). If this test fails, __iter__ instrumentation has been removed.
    """
    with pytest.raises(AssertionError):
        bh.assert_complexity_bound(quadratic_mixed, "O(n)", SIZES)


def test_quadratic_passes_its_true_bound():
    bh.assert_complexity_bound(quadratic_mixed, "O(n^2)", SIZES)


# --- bound discrimination ------------------------------------------------

def test_linear_passes_linear():
    bh.assert_complexity_bound(linear_scan, "O(n)", SIZES)


def test_linear_fails_logarithmic():
    with pytest.raises(AssertionError):
        bh.assert_complexity_bound(linear_scan, "O(log n)", SIZES)


def test_binary_passes_logarithmic():
    bh.assert_complexity_bound(binary_probe, "O(log n)", SIZES)


def test_binary_fails_constant():
    with pytest.raises(AssertionError):
        bh.assert_complexity_bound(binary_probe, "O(1)", SIZES)


# --- guard 1: sanity floor -----------------------------------------------

def test_uninstrumented_routine_fails_rather_than_passing_vacuously():
    """A routine touching nothing reports 0 ops and would otherwise pass
    every bound including O(1)."""
    def touches_nothing(data):
        return 42

    with pytest.raises(AssertionError, match="not instrumented"):
        bh.assert_complexity_bound(touches_nothing, "O(1)", SIZES)


# --- guard 2: minimum span ------------------------------------------------

def test_narrow_size_span_is_rejected():
    with pytest.raises(AssertionError, match="span"):
        bh.assert_complexity_bound(linear_scan, "O(n)", [512, 1024])  # 2x


def test_span_of_exactly_64_is_accepted():
    bh.assert_complexity_bound(linear_scan, "O(n)", [16, 1024])


# --- guard 3: determinism -------------------------------------------------

def test_nondeterministic_routine_is_rejected():
    """Uses a routine that varies RELIABLY between calls.

    An actual unseeded RNG would make this test flaky: at the smallest
    size (n=16) two draws from randint(1, 16) collide about 6% of the
    time, and the guard would silently not fire. A call-counter varies
    the op count every time, so this exercises the same guard
    deterministically. The guard itself remains probabilistic against
    real randomness -- that limitation is documented, not tested away.
    """
    state = {"calls": 0}

    def varies_between_calls(data):
        state["calls"] += 1
        for i in range(state["calls"]):
            _ = data[i % len(data)]

    with pytest.raises(AssertionError, match="non-deterministic"):
        bh.assert_complexity_bound(varies_between_calls, "O(n)", SIZES)


def test_seeded_routine_is_accepted():
    def seeded(data):
        rng = random.Random(12345)
        n = len(data)
        for _ in range(rng.randint(1, n)):
            _ = data[rng.randrange(n)]

    bh.assert_complexity_bound(seeded, "O(n)", SIZES)


# --- edge cases -----------------------------------------------------------

def test_log_bound_with_n0_of_1_does_not_divide_by_zero():
    """math.log2(1) == 0, so an unguarded C = ops(n0)/f(n0) raises.

    Only O(log n) with n0=1 reaches a zero denominator -- O(n) at n=1
    gives f=1.0 and would not exercise the guard at all. Whether the
    bound itself holds is irrelevant here; an AssertionError is a fine
    outcome. A ZeroDivisionError is not, and would propagate and fail.
    """
    assert math.log2(1) == 0
    try:
        bh.assert_complexity_bound(binary_probe, "O(log n)", [1, 64, 256])
    except AssertionError:
        pass


def test_unknown_bound_name_is_rejected_clearly():
    with pytest.raises(AssertionError, match="unknown bound"):
        bh.assert_complexity_bound(linear_scan, "O(n!)", SIZES)


def test_measure_ops_is_reproducible():
    a = bh.measure_ops(linear_scan, SIZES)
    b = bh.measure_ops(linear_scan, SIZES)
    assert a == b


def test_custom_make_input_is_used():
    seen = []

    def make(n):
        seen.append(n)
        return bh.CountingList(range(n))

    bh.measure_ops(linear_scan, SIZES, make_input=make)
    assert seen == SIZES   # one build per size, in sorted order
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_bigo_harness.py -q
```
Expected: collection error — `adv-framework/assets/python/bigo_harness.py` does not exist yet.

- [ ] **Step 3: Write the harness**

Create `adv-framework/assets/python/bigo_harness.py`:

```python
"""Deterministic algorithmic-complexity bound checking by operation counting.

WHAT THIS DOES
    Verifies a human-DECLARED complexity bound by counting operations at
    increasing input sizes. It does NOT infer complexity, and it does not
    prove a routine's true complexity -- see LIMITATIONS.

WHY NOT TIMING
    Every off-the-shelf tool (bigocheck, big_O, big-o-test, JMH) measures
    wall-clock time. Timing varies with CI runner load and thermal state,
    which makes a timing-based check a flaky gate -- and a gate that cries
    wolf trains people to ignore it. Operation counts are reproducible.
    This is a deliberate trade: narrower coverage, in exchange for being
    usable as a gate at all. For DISCOVERY (finding which routines deserve
    a bound), the timing tools are better than this.

HOW
    Instrument the CONTAINER, not the routine. CountingList counts element
    access; the routine under test is unmodified.

LIMITATIONS
    Counted:    xs[i] indexing, `for x in xs`, `y in xs`, sum/max/sorted
    Invisible:  xs.count(v), xs.index(v)  -- C-level list methods bypass
                Python protocols. Routines relying on these need
                element-level comparison counting, not container counting.
    Undercount: xs[10:20] slicing registers as 1 read for 10 elements.
    Not counted: len(xs) -- correct, it is genuinely O(1).
    Only container access is counted. Heavy per-element arithmetic is
    invisible: such a routine registers as O(n) regardless of its cost.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

DEFAULT_TOLERANCE = 1.30   # validated band 1.10-3.00; 1.05 and 5.00 misclassify
MIN_SPAN = 64              # gives 2.33x discrimination margin at tolerance 1.30

GROWTH: dict[str, Callable[[int], float]] = {
    "O(1)":       lambda n: 1.0,
    "O(log n)":   lambda n: math.log2(n) if n > 1 else 0.0,
    "O(n)":       lambda n: float(n),
    "O(n log n)": lambda n: float(n) * (math.log2(n) if n > 1 else 0.0),
    "O(n^2)":     lambda n: float(n) * float(n),
}


class CountingList(list):
    """A list that counts element access. The routine under test is unmodified.

    All three protocols matter. Counting only __getitem__ lets a genuinely
    O(n^2) routine whose inner loop iterates report exactly n operations,
    which passes a declared O(n) bound -- a gate that lies.
    """

    def __init__(self, iterable: Iterable = ()) -> None:
        super().__init__(iterable)
        self.reads = 0

    def __getitem__(self, index):
        self.reads += 1
        return super().__getitem__(index)

    def __iter__(self):
        for item in super().__iter__():
            self.reads += 1
            yield item

    def __contains__(self, item) -> bool:
        self.reads += len(self)
        return super().__contains__(item)


def _default_make_input(n: int) -> CountingList:
    return CountingList(range(n))


def measure_ops(
    routine: Callable[[CountingList], object],
    sizes: Sequence[int],
    *,
    make_input: Callable[[int], CountingList] | None = None,
) -> list[tuple[int, int]]:
    """Return [(n, operations)] for each size, in the order given.

    `routine` is always called as routine(data). Close over any extra
    arguments in a lambda.
    """
    build = make_input or _default_make_input
    samples: list[tuple[int, int]] = []
    for n in sorted(sizes):
        data = build(n)
        routine(data)
        samples.append((n, data.reads))
    return samples


def assert_complexity_bound(
    routine: Callable[[CountingList], object],
    bound: str,
    sizes: Sequence[int],
    *,
    make_input: Callable[[int], CountingList] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> None:
    """Assert the routine's counted operations stay within `bound`.

    Raises AssertionError on violation or on any guard failure. A guard
    that only warned would let the vacuous-gate case through.
    """
    assert bound in GROWTH, (
        f"unknown bound {bound!r}; expected one of {sorted(GROWTH)}")

    ordered = sorted(sizes)
    assert len(ordered) >= 2, "need at least two sizes to observe growth"

    # Guard 2: minimum span. Checked before measuring -- fail fast.
    span = ordered[-1] / ordered[0]
    assert span >= MIN_SPAN, (
        f"size span too narrow: {ordered[0]}..{ordered[-1]} is {span:.1f}x, "
        f"need >={MIN_SPAN}x. Slow-growing bounds cannot be discriminated "
        f"over a narrow range.")

    build = make_input or _default_make_input

    # Guard 3: determinism. Measure the smallest size twice.
    # PROBABILISTIC, not a guarantee: a routine that varies rarely can
    # produce identical counts twice and slip through.
    first = build(ordered[0])
    routine(first)
    again = build(ordered[0])
    routine(again)
    assert first.reads == again.reads, (
        f"routine appears non-deterministic: {first.reads} vs {again.reads} "
        f"operations at n={ordered[0]}. Randomized algorithms must be seeded "
        f"to be gated.")

    samples = measure_ops(routine, ordered, make_input=build)

    # Guard 1: sanity floor. Catches TOTAL non-instrumentation only;
    # partial instrumentation is caught by CountingList's wide coverage.
    n_first, ops_first = samples[0]
    n_last, ops_last = samples[-1]
    assert ops_last > 0, (
        f"zero operations counted -- routine is not instrumented by this "
        f"harness. See LIMITATIONS in this module: xs.count() and "
        f"xs.index() bypass instrumentation.")
    assert ops_last > ops_first, (
        f"operation count did not grow ({ops_first} at n={n_first} -> "
        f"{ops_last} at n={n_last}) -- routine is not instrumented by this "
        f"harness, or does not depend on input size.")

    f = GROWTH[bound]
    denominator = f(n_first) or 1.0   # math.log2(1) == 0 would divide by zero
    c = ops_first / denominator

    for n, ops in samples[1:]:
        allowed = c * f(n) * tolerance
        assert ops <= allowed, (
            f"{bound} bound exceeded: {ops} operations at n={n}, "
            f"allowed {allowed:.0f} "
            f"(calibrated C={c:.3f} from {ops_first} ops at n={n_first}, "
            f"tolerance {tolerance}). Measured: {samples}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/test_bigo_harness.py -q
```
Expected: `19 passed`.

If `test_quadratic_with_iterating_inner_loop_is_not_mistaken_for_linear` fails, `__iter__` instrumentation is missing — that is the load-bearing regression, not a flaky test.

- [ ] **Step 5: Prove the guards are not decorative**

Each guard must be shown to actually fire. Temporarily break each one, confirm the matching test fails, then restore. Report the observed failure for each:

1. Remove the `__iter__` method from `CountingList` → `test_quadratic_with_iterating_inner_loop_is_not_mistaken_for_linear` must fail.
2. Change `MIN_SPAN` to `1` → `test_narrow_size_span_is_rejected` must fail.
3. Delete the determinism assertion → `test_nondeterministic_routine_is_rejected` must fail.
4. Delete the `ops_last > 0` assertion → `test_uninstrumented_routine_fails_rather_than_passing_vacuously` must fail.

Restore the file to its committed state afterwards and confirm `git diff` on it is empty. A guard whose test still passes when the guard is removed is not protecting anything.

- [ ] **Step 6: Confirm the repo's existing suite still passes**

Run:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/ -q
```
Expected: 45 pre-existing (verified) + 19 new = `64 passed`. Report the actual number.

- [ ] **Step 7: Commit**

```bash
git add adv-framework/assets/python/bigo_harness.py scripts/test_bigo_harness.py
git commit -m "$(cat <<'EOF'
Add operation-counting harness for declared complexity bounds

Verifies a human-declared bound by counting container operations at
increasing input sizes -- deterministic, unlike every off-the-shelf tool,
which measures wall-clock time and would make a flaky gate.

Instruments __getitem__, __iter__ and __contains__. All three are
load-bearing: a __getitem__-only version let a genuinely O(n^2) routine
report exactly n operations and pass a declared O(n) bound.

Three guards, all raising AssertionError: a sanity floor for
uninstrumented routines, a 64x minimum size span, and a determinism
check for unseeded randomized routines.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Worked example proving the harness end to end

The example project currently contains only scalar arithmetic (`add`, `subtract`, `multiply`, `divide` on ints) — nothing that touches a collection, so nothing whose complexity is meaningful. This task adds a subject worth bounding.

The test imports the **real shipped asset** by path rather than copying it, so the example proves the actual artifact and cannot drift from it.

**Files:**
- Create: `adv-framework/examples/python/src/calculator/search.py`
- Create: `adv-framework/examples/python/tests/test_search_complexity.py`
- Modify: `adv-framework/examples/python/README.md`

**Interfaces:**
- Consumes from Task 1: `assert_complexity_bound(routine, bound, sizes, *, make_input=None, tolerance=1.30)`, `CountingList`, loaded via `Path(__file__).resolve().parents[3] / "assets" / "python" / "bigo_harness.py"`.
- Produces: `calculator.search.contains(haystack, needle) -> bool` (O(n)) and `calculator.search.has_duplicates(values) -> bool` (O(n²)).

- [ ] **Step 1: Write the failing tests**

Create `adv-framework/examples/python/tests/test_search_complexity.py`:

```python
"""Complexity-bound tests for calculator.search.

Marked `property` so ADV's Property gate (#4) runs them: these are
properties over input size, and the existing `-m property` stage picks
them up with no pipeline change.

The harness is imported from the shipped asset by path, not copied, so
this example exercises the real artifact.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from calculator.search import contains, has_duplicates

# adv-framework/examples/python/tests/ -> parents[3] == adv-framework/
_HARNESS = (Path(__file__).resolve().parents[3]
            / "assets" / "python" / "bigo_harness.py")
_spec = importlib.util.spec_from_file_location("bigo_harness", _HARNESS)
bh = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bh
_spec.loader.exec_module(bh)

SIZES = [16, 64, 256, 1024]          # 64x span, satisfies MIN_SPAN


@pytest.mark.property
def test_contains_is_linear():
    """Worst case: the needle is absent, so the whole list is scanned."""
    bh.assert_complexity_bound(
        lambda data: contains(data, -1), "O(n)", SIZES)


@pytest.mark.property
def test_has_duplicates_is_quadratic():
    bh.assert_complexity_bound(
        lambda data: has_duplicates(data), "O(n^2)", SIZES)


@pytest.mark.property
def test_the_gate_actually_fires_on_a_wrong_declaration():
    """Proves the gate is not vacuous.

    Declaring O(n) for a quadratic routine MUST fail. Without this, a
    harness that silently passed everything would look identical to a
    working one in this suite.
    """
    with pytest.raises(AssertionError):
        bh.assert_complexity_bound(
            lambda data: has_duplicates(data), "O(n)", SIZES)
```

- [ ] **Step 2: Run to verify they fail**

From `adv-framework/examples/python/`:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/test_search_complexity.py -q
```
Expected: collection error — `calculator.search` does not exist yet.

- [ ] **Step 3: Write the routines under test**

Create `adv-framework/examples/python/src/calculator/search.py`:

```python
"""Collection routines with deliberately different complexity classes.

These exist so the complexity-bound harness has something meaningful to
verify. The calculator module itself is scalar arithmetic, which has no
interesting asymptotic behaviour.
"""


def contains(haystack: list[int], needle: int) -> bool:
    """Linear scan. O(n).

    Deliberately does NOT use `needle in haystack` -- that would be one
    __contains__ call, which the harness charges as len(haystack) in a
    single step. The explicit loop is what makes the growth observable
    per element.
    """
    for item in haystack:
        if item == needle:
            return True
    return False


def has_duplicates(values: list[int]) -> bool:
    """Naive pairwise comparison. O(n^2).

    A hash-set implementation would be O(n); this is the deliberately
    quadratic version, so the example can demonstrate both a bound that
    holds and a declaration that is wrong.
    """
    n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            if values[i] == values[j]:
                return True
    return False
```

- [ ] **Step 4: Run the complexity tests**

From `adv-framework/examples/python/`:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/test_search_complexity.py -v
```
Expected: `3 passed`.

If `test_contains_is_linear` fails, read the measured counts in the assertion message before changing anything — the message includes the full `[(n, ops)]` series.

- [ ] **Step 5: Confirm the Property-gate selector picks them up**

The whole point of reusing the `property` marker is that the existing stage runs these with no pipeline change. Verify both directions:

```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/ -m property -q
```
Expected: the 4 pre-existing property tests plus these 3 = `7 passed`.

```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/ -m "not property and not regression" -q
```
Expected: `5 passed` (the original unit tests), with the complexity tests deselected. Report both actual numbers.

- [ ] **Step 6: Document it in the example's README**

Add this section to `adv-framework/examples/python/README.md`, immediately before the existing "A note on the diff-coverage check" section:

```markdown
## Complexity bounds

`tests/test_search_complexity.py` declares and verifies algorithmic
complexity bounds for `calculator.search`, using the harness shipped at
`assets/python/bigo_harness.py`. It counts container operations rather
than timing anything, so results are reproducible.

Run just those:

```bash
pytest tests/test_search_complexity.py -v
```

One of the three tests deliberately asserts that declaring `O(n)` for a
quadratic routine **fails**. That test passing is what proves the gate
is not vacuous — a harness that silently accepted everything would look
identical to a working one without it.

This verifies a *declared* bound against *counted* operations. It does not
prove true complexity: `xs.count()` and `xs.index()` bypass the
instrumentation entirely. See the harness module docstring for the full
coverage map.
```

- [ ] **Step 7: Confirm the full example suite is green**

From `adv-framework/examples/python/`:
```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest tests/ -q
```
Expected: 5 unit + 4 property + 3 complexity = `12 passed`. Report the actual number.

- [ ] **Step 8: Commit**

```bash
git add adv-framework/examples/python/src/calculator/search.py adv-framework/examples/python/tests/test_search_complexity.py adv-framework/examples/python/README.md
git commit -m "$(cat <<'EOF'
Add worked complexity-bound example to the Python example project

The example project was scalar arithmetic only, so it had no routine
whose complexity was meaningful. Adds a linear contains() and a
deliberately quadratic has_duplicates() as subjects.

The test imports the real shipped harness by path rather than copying
it, so the example exercises the actual artifact and cannot drift.

One test asserts that declaring O(n) for the quadratic routine FAILS --
without it, a harness that silently accepted everything would look
identical to a working one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Reference documentation and routing

**Files:**
- Create: `adv-framework/references/complexity-bounds.md`
- Modify: `adv-framework/references/gate-structure.md`
- Modify: `adv-framework/SKILL.md`
- Modify: `scripts/heading-manifest.json` (regenerated, not hand-edited)

**Interfaces:**
- Consumes: the asset paths from Tasks 1 and 2. All references to them must resolve *within the bundle* — `scripts/check-bundle-integrity.py` enforces this and will fail the build otherwise.

- [ ] **Step 1: Write the reference doc**

Create `adv-framework/references/complexity-bounds.md`:

```markdown
# Algorithmic Complexity Bounds — Reference

None of ADV's seven gates catch algorithmic degradation. A change turning
an O(n log n) routine into O(n^2) passes static analysis, compiles,
satisfies every unit and property test, matches its golden files, and
smoke-tests green. It surfaces in production as a timeout under load.

**This is a different axis from the complexity budget** in
`gate-structure.md`. That measures cyclomatic/cognitive complexity —
branching structure. A five-line function with no branches can be O(n^3).
Do not treat one as covering the other.

## Two layers

**Discovery — never a gate.** Use an LLM, [`bigocheck`](https://github.com/adwantg/bigocheck),
or [`big_O`](https://pypi.org/project/big-O/) to find candidate routines
and estimate their class. The output is a nomination: "this looks
superlinear, declare a bound for it." This is the use ADV's own README
endorses for LLM review — routing work toward a new deterministic check.

**Gate — the deterministic check.** A human declares the bound; the
harness verifies it by counting operations. This is what merges or blocks.

LLM-estimated complexity is the anti-pattern *only when it is the gate*.
As discovery it is legitimate and useful.

## Why not the existing tools

Every off-the-shelf option measures wall-clock time:

| Tool | Language | Measures | Asserts a declared bound? |
|---|---|---|---|
| `bigocheck` | Python | Wall-clock | Yes — best of the group, and candid about instability |
| `big_O` | Python | Wall-clock | No — infers a best-fit class |
| `big-o-test` | Java | Wall-clock | Yes, but 5 stars and no published Maven coordinates |
| JMH | Java | Wall-clock | No — benchmarks, does not assert bounds |

Timing varies with CI runner load and thermal state. A timing-based check
is a flaky gate, and `security.md` already warns that a check which cries
wolf trains people to ignore it.

Operation counting is chosen **deliberately against the grain**, and the
trade is narrower coverage for reproducibility. That justification applies
to a *gate*; it is not a claim that op-counting beats timing generally.
For discovery, use the timing tools.

## The technique

Instrument the container, not the routine. `CountingList` counts element
access; the routine under test is unmodified.

```python
from bigo_harness import assert_complexity_bound

def test_lookup_is_logarithmic():
    assert_complexity_bound(
        lambda data: binary_search(data, -1),
        "O(log n)",
        [16, 64, 256, 1024],
    )
```

Measure ops at increasing sizes, calibrate `C = ops(n0)/f(n0)` on the
**smallest** sample, then assert `ops(n) <= C*f(n)*tolerance` for every
larger one. Calibrating on the smallest is the direction that catches
super-linear blowup.

Place these in the **Property gate (#4)** with the existing `property`
marker. This is not an eighth gate.

## Calibrated parameters

Both were measured, not chosen.

**Tolerance 1.30.** Validated band is 1.10–3.00 against six
classification cases; 1.05 is too tight (misclassifies bubble sort vs
O(n^2)) and 5.00 too loose (misclassifies binary search vs O(1)).

**Minimum span 64x.** Margin by which O(log n) data exceeds an O(1) bound,
which must beat the tolerance to be rejected: 8x span gives 1.40x
(thin), 64x gives 2.33x (comfortable), 1024x gives 3.86x. 64x is
sufficient; demanding more costs test time for no discrimination gain.

## Guards

All three raise `AssertionError` — a violated guard is a test failure,
never a warning.

1. **Sanity floor** — zero or non-growing counts fail with "not
   instrumented." Catches *total* non-instrumentation only.
2. **Minimum 64x span** — checked before measuring.
3. **Determinism** — the smallest size is measured twice and must match.
   This is **probabilistic, not a guarantee**: a routine that varies
   rarely can produce identical counts twice and slip through.

## Coverage, measured

| Access pattern | Counted? |
|---|---|
| `xs[i]` | Yes |
| `for x in xs` | Yes |
| `y in xs` | Yes (charged as `len(xs)` in one step) |
| `sum(xs)`, `max(xs)`, `sorted(xs)` | Yes |
| `xs[10:20]` | Undercounts — 1 read for 10 elements |
| `xs.count(v)`, `xs.index(v)` | **Invisible** — C-level methods bypass Python protocols |
| `len(xs)` | Not counted — correct, genuinely O(1) |

Counting only `__getitem__` is insufficient: a genuinely O(n^2) routine
whose inner loop iterates reports exactly `n` operations and passes a
declared O(n) bound. All three protocols are load-bearing.

## Limitations

- Verifies a **declared bound against counted operations**. It does not
  prove true complexity. If instrumentation misses work, the gate
  measures the wrong thing and can pass wrongly.
- Counts container access only. Heavy per-element arithmetic is invisible;
  such a routine registers as O(n) regardless of cost.
- Routines relying on `.count()` or `.index()` need element-level
  comparison counting instead — instrument the objects, not the container.
- Python only. The technique transfers to any language with an
  interceptable collection type, but no other language ships an asset.

## Where to start

`assets/python/bigo_harness.py` is the harness.
`examples/python/tests/test_search_complexity.py` is a worked example
against real routines, including one test that proves the gate fires on a
wrong declaration.
```

- [ ] **Step 2: Add the pointer in gate-structure.md**

In `adv-framework/references/gate-structure.md`, inside the
`## Further recommended checks (not in the default pipelines)` section,
add this as a new `###` subsection immediately after the
`### Complexity budget` subsection (before `### Suite health`):

```markdown
### Algorithmic complexity bounds

A distinct axis from the complexity budget above: that one measures
branching structure, this one measures asymptotic growth. A five-line
function with no branches can be O(n^3).

Declaring a bound and verifying it by counting operations is
deterministic and belongs in the **Property** gate. See
`references/complexity-bounds.md` for the technique, the calibrated
parameters, and the coverage limits; `assets/python/bigo_harness.py`
is a working implementation.
```

- [ ] **Step 3: Add the reference to SKILL.md's routing manifest**

`SKILL.md`'s reference-file bullets are the routing layer that decides
whether an agent opens a reference doc at all. A doc absent from it is
unreachable via the intended path.

In `adv-framework/SKILL.md`, add a bullet to the `references/` list,
after the `references/local-verification.md` bullet:

```markdown
- **`references/complexity-bounds.md`** — verifying a declared algorithmic complexity bound deterministically by counting operations rather than timing, why every off-the-shelf tool is unsuitable as a gate, the calibrated tolerance and size-span parameters, and the measured coverage limits. Read this when the user asks about Big O, algorithmic performance regressions, or complexity auditing — and note it is a different axis from the cyclomatic complexity budget in `references/gate-structure.md`.
```

- [ ] **Step 4: Confirm the self-check fails, for the right reason**

The new reference doc changes `references/` contents, so the heading
manifest is now stale. This is expected — verify the checker notices:

```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py
```
Expected: exit 1, with a `manifest` finding naming
`adv-framework/references/complexity-bounds.md` as not in the manifest.

Note the checker reads **committed** bytes, so commit Steps 1–3 first
(or expect the finding to reflect the pre-change state). If you see no
finding at all, the changes are not yet committed.

- [ ] **Step 5: Re-record the manifest and confirm green**

```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py --update
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" scripts/check-bundle-integrity.py
```
Expected: the update records 5 reference docs (was 4); the re-run reports
all five checks `ok`, exit 0.

If `path-refs` reports a finding, a reference in the new doc does not
resolve *within the bundle*. Fix the reference, not the checker.

- [ ] **Step 6: Confirm both suites still pass**

```bash
"/c/Users/HP/AppData/Local/Programs/Python/Python310/python.exe" -m pytest scripts/ -q
```
Expected: `64 passed`.

- [ ] **Step 7: Commit**

```bash
git add adv-framework/references/complexity-bounds.md adv-framework/references/gate-structure.md adv-framework/SKILL.md scripts/heading-manifest.json
git commit -m "$(cat <<'EOF'
Document algorithmic complexity bounds and route SKILL.md to it

Adds references/complexity-bounds.md covering the two-layer split
(LLM/bigocheck for discovery, operation counting for the gate), the
calibrated tolerance and span parameters, the measured coverage map, and
the stated limitations.

Corrects a likely misreading by saying plainly that this is a different
axis from the cyclomatic complexity budget -- a five-line branchless
function can be O(n^3).

SKILL.md's routing bullet is updated in the same commit, since a
reference doc missing from that manifest is unreachable by the agent it
was written for.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Plan self-review notes

- **Spec coverage**: harness + guards + coverage map → Task 1; two-layer split, discovery tools, prior-art table, limitations → Task 3's reference doc; Property-gate placement and marker reuse → Task 2 Step 5 (verified in both directions); Python-only scope and the Java rationale → Global Constraints and the reference doc's Limitations; the expected self-check failure → Task 3 Steps 4–5.
- **Gap the spec did not anticipate, now covered**: the example project had no collection-based routine, so there was nothing to bound. Task 2 adds `search.py` rather than stretching the scalar `calculator` module.
- **Improvement on the spec**: the spec put the worked example in `assets/python/`, where it could never execute. Task 2 places it in the runnable `examples/python/` project and imports the real asset by path, so the example proves the shipped artifact instead of a copy that can drift.
- **Placeholder scan**: no TBD/TODO. Every step has complete code or an exact command with expected output.
- **Anti-vacuity**: Task 1 Step 5 requires breaking each guard and observing the matching test fail, then restoring — a guard whose test passes when the guard is deleted protects nothing. Task 2 includes a test asserting the gate *fires* on a wrong declaration, for the same reason.
- **Interface consistency**: `assert_complexity_bound(routine, bound, sizes, *, make_input=None, tolerance=1.30)`, `measure_ops(routine, sizes, *, make_input=None)`, `CountingList.reads`, `GROWTH`, `MIN_SPAN`, `DEFAULT_TOLERANCE` are defined once in Task 1 and used under those exact names in Tasks 2 and 3. Bound strings are exactly `"O(1)"`, `"O(log n)"`, `"O(n)"`, `"O(n log n)"`, `"O(n^2)"` throughout.
