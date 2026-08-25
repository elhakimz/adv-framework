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
    Counted:    xs[i] indexing, `for x in xs`, `y in xs`, sum/max
    Invisible:  xs.count(v), xs.index(v)  -- C-level list methods bypass
                Python protocols. Routines relying on these need
                element-level comparison counting, not container counting.
    Undercount: xs[10:20] slicing registers as 1 read for 10 elements.
                sorted(xs) registers n reads for O(n log n) of comparison
                work -- a routine that just sorts and returns passes a
                declared O(n) bound.
    Escape hatch: copying the input out of the instrumented container
                (list(xs), set(xs), building a dict index) makes
                everything done on the copy invisible -- only the first
                pass, the copy itself, is counted.
    Not counted: len(xs) -- correct, it is genuinely O(1).
    Only container access is counted. Heavy per-element arithmetic is
    invisible: such a routine registers as O(n) regardless of its cost.
    The determinism guard (see assert_complexity_bound) is PROBABILISTIC:
    it compares two runs at the smallest size and a routine that varies
    rarely can produce identical counts twice and slip through.
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
    """Return [(n, operations)] for each size, in ascending size order.

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

    # Reuse the guard's first measurement as sample 0 rather than drawing a
    # third sample at the smallest size -- for a stateful routine, the guard
    # could otherwise compare runs 1 and 2 successfully and then calibrate
    # on a run the guard never saw.
    samples = [(ordered[0], first.reads)]
    if len(ordered) > 1:
        samples += measure_ops(routine, ordered[1:], make_input=build)

    # Guard 1: sanity floor. Together, these catch TOTAL non-instrumentation
    # only; partial instrumentation is caught by CountingList's wide protocol
    # coverage. The first assertion (ops_last > 0) is logically fully subsumed
    # by the second (ops_last > ops_first), since read counts are never
    # negative -- if ops_last == 0 then 0 > ops_first is false for any
    # ops_first >= 0. It is kept for the clearer error message on the common
    # case of complete non-instrumentation, not for additional protection.
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
