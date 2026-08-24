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
    with pytest.raises(AssertionError, match=r"bound exceeded"):
        bh.assert_complexity_bound(quadratic_mixed, "O(n)", SIZES)


def test_quadratic_passes_its_true_bound():
    bh.assert_complexity_bound(quadratic_mixed, "O(n^2)", SIZES)


# --- bound discrimination ------------------------------------------------

def test_linear_passes_linear():
    bh.assert_complexity_bound(linear_scan, "O(n)", SIZES)


def test_linear_fails_logarithmic():
    with pytest.raises(AssertionError, match=r"bound exceeded"):
        bh.assert_complexity_bound(linear_scan, "O(log n)", SIZES)


def test_binary_passes_logarithmic():
    bh.assert_complexity_bound(binary_probe, "O(log n)", SIZES)


def test_binary_fails_constant():
    with pytest.raises(AssertionError, match=r"bound exceeded"):
        bh.assert_complexity_bound(binary_probe, "O(1)", SIZES)


# --- guard 1: sanity floor -----------------------------------------------

def test_uninstrumented_routine_fails_rather_than_passing_vacuously():
    """A routine touching nothing reports 0 ops and would otherwise pass
    every bound including O(1)."""
    def touches_nothing(data):
        return 42

    with pytest.raises(AssertionError, match="zero operations counted"):
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
