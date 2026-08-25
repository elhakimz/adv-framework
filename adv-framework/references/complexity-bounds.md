# Algorithmic Complexity Bounds — Reference

None of ADV's seven gates catch algorithmic degradation. A change turning
an O(n log n) routine into O(n^2) passes static analysis, compiles,
satisfies every unit and property test, matches its golden files, and
smoke-tests green. It surfaces in production as a timeout under load.

**This is a different axis from the complexity budget** in
`references/gate-structure.md`. That measures cyclomatic/cognitive complexity —
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
is a flaky gate, and `references/security.md` already warns that a check which cries
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
| `sum(xs)`, `max(xs)` | Yes |
| `xs[10:20]` | Undercounts — 1 read for 10 elements |
| `sorted(xs)` | **Undercounts** — registers n reads for O(n log n) of comparison work. A routine that just sorts and returns passes a declared O(n) bound |
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
- Once a routine copies the input out of the instrumented container
  (`list(xs)`, `set(xs)`, building a dict index), everything done on the
  copy is invisible — only the first pass, the copy itself, is counted.
  This escape hatch is more likely to appear in real code than
  `.count()`/`.index()`: "defensively copy the argument, then work on the
  copy" is a common pattern that happens to defeat this gate.
- The determinism guard (guard 3, above) is **probabilistic, not a
  guarantee**: it compares two runs at the smallest size, and a routine
  that varies rarely can produce identical counts twice and slip through.
- Python only. The technique transfers to any language with an
  interceptable collection type, but no other language ships an asset.

## Where to start

`assets/python/bigo_harness.py` is the harness.
`examples/python/tests/test_search_complexity.py` is a worked example
against real routines, including one test that proves the gate fires on a
wrong declaration.

The usage snippet above assumes `bigo_harness` is importable. Either copy
`bigo_harness.py` into your own test directory and import it normally, or
load it directly by path — see how
`examples/python/tests/test_search_complexity.py` does this with
`importlib.util.spec_from_file_location`, which needs no install step.
