# Algorithmic Complexity Bounds — Design

**Status**: Draft, pending review
**Date**: 2026-08-17

## Motivation

Nothing in ADV's seven gates catches algorithmic degradation. A change that turns an O(n log n) routine into O(n²) passes static analysis, compiles, satisfies every unit and property test, matches its golden files, and smoke-tests green. It surfaces in production as a timeout under load — the exact "escaped despite a green pipeline" scenario the ratchet rule exists to answer.

The complexity budget added in the previous change does **not** cover this. That is cyclomatic/cognitive complexity — a *structural* measure of branching. A five-line function with no branches at all can be O(n³). The two axes are unrelated, and conflating them is the most likely misreading of this feature.

## The constraint that shapes everything

ADV's founding principle: every gate is **pass/fail, reproducible, and free of judgment calls**. Algorithmic complexity resists all three:

- Determining the asymptotic complexity of arbitrary code is undecidable in general.
- Every existing tool measures **wall-clock time**, which varies with CI runner load, neighbours, and thermal state. A timing-based gate is a flaky gate, and `references/security.md` already warns that a check which cries wolf trains people to ignore it.
- Asking a model "what's the complexity of this?" produces a judgment, not a verdict.

So the feature cannot be "audit our Big O." It has to be something narrower and actually deterministic.

## Prior art, verified

Every tool below was checked against its own documentation rather than assumed. The finding that matters: **all of them measure execution time.**

| Tool | Language | Measures | Asserts a declared bound? | Assessment |
|---|---|---|---|---|
| [`bigocheck`](https://github.com/adwantg/bigocheck) | Python | Wall-clock (`timeit`/`time`) | Yes — `assert_bounds(lower, upper)`, pytest marker | Best of the group. Candid about the problem: ships instability detection, `compute_stability()`, warmup and trial knobs |
| [`big_O`](https://pypi.org/project/big-O/) | Python | Wall-clock | No — infers best-fit class | Inference, not assertion. Curve-fitting on noisy timing picks the wrong model readily |
| [`big-o-test`](https://github.com/MarkusSprunck/big-o-test) | Java | Wall-clock (proxy records duration) | Yes — `BigOAssert.*` | 5 stars, no discoverable Maven coordinates, no visible releases. Recommending it would put users on unmaintained tooling |
| [JMH](https://github.com/openjdk/jmh) + [`jmh-maven-plugin`](https://github.com/jhunters/jmh-maven-plugin) | Java | Wall-clock | No | Mature and excellent, but it benchmarks; it does not assert asymptotic bounds |
| Checkstyle / PMD `CyclomaticComplexity` | Java | Branch count | N/A | Already in ADV's Static gate. **Structural, not asymptotic** — flag this explicitly, since a team may believe they already have complexity coverage |

**Going against the grain, deliberately.** Every tool chose timing, and that is not an oversight by their authors — timing works on *any* routine with zero instrumentation. This design chooses operation counting instead, which is more rigorous but narrower. That trade is justified **for a gate specifically**, because ADV requires reproducibility; it is *not* a claim that op-counting is universally superior. For discovery, the timing tools are better than anything built here.

## Two layers

The split mirrors ADV's existing doctrine on LLM review, which the framework already permits as a signal generator that routes work "toward a human or toward a new deterministic check."

**Discovery layer — never a gate.** LLM scanning, `bigocheck`, or `big_O` identify candidate routines and estimate their class. Output is a *nomination*: "this looks superlinear, declare a bound for it." An earlier draft of this design listed LLM-estimated Big O as the anti-pattern outright. That was wrong: estimation is the endorsed use, and only becomes the anti-pattern when it *is* the gate.

**Gate layer — the deterministic check.** A human declares the bound; the harness verifies it by counting operations. This is what merges or blocks.

## The technique

Instrument the **container**, not the routine. A `CountingList` subclass counts element access; the routine under test is completely unmodified. Verified: op counts identical across three consecutive runs, no timing involved anywhere.

**Assertion.** Measure ops at increasing sizes, calibrate the constant `C = ops(n₀) / f(n₀)` on the **smallest** sample, then assert `ops(n) <= C · f(n) · tolerance` for every larger sample. Calibrating on the smallest is deliberate — it is the direction that catches super-linear blowup. Calibrating on the largest would let a too-fast-growing curve pass.

Two edge cases the harness must handle explicitly rather than divide by zero. `f(n₀) = 0` occurs for `O(log n)` when `n₀ = 1`, since log₂1 = 0 — confirmed to raise `ZeroDivisionError: float division by zero`, not a silent NaN. A `denom = f(n₀) or 1.0` fallback was verified to resolve it without crashing. The second case, `ops(n₀) = 0`, is already rejected by the sanity floor. The 64× span guard makes `n₀ = 1` unlikely in practice, but neither case should be left to chance.

**Placement.** ADV's **Property gate (#4)** — "operations grow no faster than n log n" is a property over input sizes. No eighth gate; the seven-gate structure is the framework's identity. Tests reuse the existing `property` pytest marker, so no pipeline change is required.

## Empirically established parameters

These were measured, not chosen.

**Tolerance = 1.30.** Swept against six classification cases (binary search vs O(log n)/O(1), linear search vs O(n)/O(log n), bubble sort vs O(n²)/O(n log n)):

| Tolerance | Result |
|---|---|
| 1.05 | Misclassifies bubble/O(n²) — too tight |
| **1.10 – 3.00** | **All six correct** |
| 5.00 | Misclassifies binary/O(1) — too loose |

1.30 sits inside the validated band with headroom on both sides — it can loosen to 3.00 (2.3× further) or tighten to 1.10 (1.2× further) before any case misclassifies. The asymmetry is expected: the upper limit is set by distinguishing near-constant growth, the lower by constant-factor noise at small n.

**Minimum size span = 64×.** Margin by which O(log n) data exceeds an O(1) bound (must beat the 1.30 tolerance to be correctly rejected):

| Span | Margin |
|---|---|
| 8× | 1.40× — thin |
| **64×** | **2.33× — comfortable, 1.8× headroom** |
| 512× | 3.00× |
| 1024× | 3.86× |
| 8192× | 4.71× |

An earlier draft demanded ≥1000×. That was overly conservative and cost test time for no discrimination gain; 64× (e.g. 16→1024) is sufficient.

## The silent-pass hole, and how it is closed

This is the most important finding, because the first version of the design would have shipped a gate that lies.

A genuinely O(n²) routine — outer loop indexing, inner loop iterating — reported exactly `n` operations: `[(16,16), (64,64), (256,256), (1024,1024)]`. Counts *grew*, so a naive sanity floor accepted them, and the routine **passed a declared O(n) bound**.

Instrumenting `__iter__` alongside `__getitem__` closes it. The same routine then reports `[(16,272), (64,4160), (256,65792), (1024,1049600)]` — correctly failing O(n) and passing O(n²).

**Consequence for the design:** wide instrumentation (`__getitem__`, `__iter__`, `__contains__`) is mandatory, not optional. The sanity floor alone is insufficient because it only catches *total* non-instrumentation, never partial.

## Verified coverage map

Measured at n=100. This is precisely what the harness can and cannot see, and it must be documented for users rather than left implicit.

| Access pattern | Counted? |
|---|---|
| `xs[i]` indexing | Yes — 100 |
| `for x in xs` iteration | Yes — 100 |
| `y in xs` membership | Yes — 100 |
| `sum(xs)`, `max(xs)`, `sorted(xs)` | Yes — 100 |
| `xs[10:20]` slicing | Undercounts — 1 read for 10 elements |
| `xs.count(v)`, `xs.index(v)` | **Invisible** — C-level list methods bypass Python protocols |
| `len(xs)` | Not counted — correct, it is genuinely O(1) |

Routines relying on `.count()` or `.index()` need element-level comparison counting (instrumenting the *objects*) rather than container counting. The reference doc will say so.

## Guards

Each guard raises `AssertionError` — a violated guard is a **test failure**, never a warning. A guard that only warns would let the vacuous-gate case through, which is the failure this whole section exists to prevent.

1. **Sanity floor** — if the largest sample's op count is zero, or is not greater than the smallest sample's, fail with "routine is not instrumented by this harness." This catches total non-instrumentation. It does **not** catch partial instrumentation; only the wide `__getitem__`/`__iter__`/`__contains__` coverage does that.
2. **Minimum 64× size span** — the harness inspects the `sizes` argument and fails before measuring if `max(sizes) / min(sizes) < 64`, naming the actual span. Enforced, not advisory.
3. **Determinism check instead of a seed mandate** — the harness cannot force a caller to seed their RNG, so "requires a seed" would be unenforceable. Instead it measures the **smallest** size twice and fails if the counts differ, reporting that the routine appears non-deterministic and must be seeded to be gated.

   Verified: an unseeded routine was rejected in **200 of 200 trials** (47 vs 90 ops on the first sample); a seeded routine and a deterministic routine were both correctly accepted.

   **This guard is probabilistic, not a guarantee, and must be documented as such.** It detects non-determinism only when two measurements happen to differ. A routine that varies rarely — say 99% of runs at exactly 100 ops — would likely produce identical counts twice and slip through. The 200/200 result reflects a routine with large variance and should not be read as a general detection rate.

## Scope: Python only

**Java was evaluated as a second pilot and declined.** There is no off-the-shelf deterministic option — the only Java complexity-assertion library is timing-based and effectively unmaintained (5 stars, no Maven coordinates). Java would therefore need the same hand-rolled instrumented-collection approach (a `List` wrapper counting `get()` and `iterator()`). The technique transfers cleanly, but it cannot be *executed* in the current environment, so it would ship written-but-never-run — the precise gap this repo already documents about its own six unexecuted hooks.

Python is the one language that can be proven end to end here, and `adv-framework/examples/python/` already exists as a home for the worked example.

## Deliverables

- `adv-framework/assets/python/bigo_harness.py` — the counting container, the bound assertion, and the three guards.
- `adv-framework/assets/python/test_example_bigo.py` — worked example: a routine passing its declared bound, and one failing it.
- `adv-framework/references/complexity-bounds.md` — the technique, the two-layer split, the coverage map, the calibration data, and the limitations.
- Pointer from `references/gate-structure.md`, in the "Further recommended checks" section alongside complexity budget and suite health.

Adding a reference doc will make `scripts/check-bundle-integrity.py`'s manifest check fail until `SKILL.md`'s routing bullet is updated and the heading manifest re-recorded. That is the self-check working as designed, and the plan should treat it as an expected step rather than a surprise.

## Stated limitations

To be reproduced in the reference doc, not buried here:

- This gate verifies a **declared bound against counted operations**. It does not prove a routine's true complexity. If instrumentation misses work — see the coverage map — the gate measures the wrong thing and can pass wrongly.
- It counts container access only. A routine doing heavy per-element arithmetic registers as O(n) regardless of the arithmetic's cost.
- It is narrower than the timing-based tools by construction. That is the price of determinism, and users who want broad coverage should run `bigocheck` in the discovery layer.

## Non-goals

- Automatic complexity inference — undecidable in general, and the existing inference tools are timing-based.
- Any timing-based measurement in the gate layer.
- LLM estimation **as a gate**. As discovery it is explicitly endorsed.
- An eighth gate. This lives inside Property (#4).
- A second language in this change.
