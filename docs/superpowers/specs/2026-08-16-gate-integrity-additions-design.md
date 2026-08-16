# Gate Integrity Additions — Design

**Status**: Draft, pending review
**Date**: 2026-08-16

## Motivation

[old-coder](https://github.com/AmazingAng/old-coder) (MIT, © AmazingAng) proposes an evidence-first workflow for coding agents: "don't read the code — make it run the gauntlet." Its loop is SPEC → human approves the spec (not the code) → RED/GREEN/REFACTOR → GAUNTLET → EVIDENCE report.

Its core conviction is the same as ADV's — a human's confidence should rest on reproducible checks, not on reading a diff the agent wrote. But most of its loop is *agent process*, which ADV deliberately does not govern, and which is already covered for anyone running an agent-process skill set (the Superpowers plugin's `brainstorming`, `writing-plans`, `test-driven-development`, `verification-before-completion`, and `subagent-driven-development` map onto SPEC, RED/GREEN/REFACTOR, EVIDENCE, and independent verification respectively).

What old-coder contributes that ADV genuinely lacks is narrower: three deterministic checks absent from every ADV pipeline, and an explicit statement of the behavioral rules that ADV currently only enforces structurally. This spec covers exactly that, and nothing else.

## Scope

Two files change. No new files, no new assets, no new gates.

**Excluded deliberately** — old-coder's Tier 1/2/3 calibration ("scale effort to blast radius"). Its useful half is agent-process, already owned elsewhere; its other half ("Tier 1 typo fix: full suite + lint" — i.e. run fewer layers) contradicts ADV's ratchet rule that a gate is never skipped to unblock work. Including it scoped-and-caveated costs more words than it earns.

**Also excluded** — the SPEC/EVIDENCE/independent-verifier workflow, per the motivation above. ADV governs what must pass, not how an agent should sequence its work.

## Change 1: `adv-framework/references/gate-structure.md`

### 1a. Anti-gaming rules

Placed immediately after the existing "The anti-pattern this framework exists to prevent" section — these are the concrete, enumerated form of that same principle, so they belong adjacent to it rather than in a distant section.

Six rules, paraphrased into ADV's voice (not lifted verbatim), introduced as the **behavioral** counterpart to the **structural** prevention that `CODEOWNERS` and permission scoping already provide. The framing matters: ADV already makes it hard for an agent to commit a weakened test; these rules say don't attempt it, and name the specific shapes that attempt takes.

1. Never weaken a test to make it pass — no broadened assertions, added skips, raised tolerances, or deleted failing tests.
2. Never edit a test and its implementation in the same step to reach green.
3. Never mock the unit under test, or mock so heavily that the test only exercises mocks.
4. Never add a test solely to raise a coverage number — a test that touches lines without asserting behavior defeats the diff-coverage gate rather than satisfying it.
5. Never report a check that wasn't run. An honestly declared skip preserves trust; a fabricated pass destroys it.
6. A failing gate blocks done. Work is not complete while any gate is red.

Rule 4 connects directly to ADV's existing diff-coverage gate; rule 6 restates the ratchet rule's enforcement stance at the individual-task level. Both cross-references are made explicit in the text.

### 1b. "Further recommended checks"

A new section following the exact precedent and shape of the existing "Mutation testing (recommended addition, not in the default pipelines)" section — same framing ("recommended, not shipped in the default pipelines"), same per-language tool list format, same cost-based rationale for where each belongs.

**Complexity budget** — catches unmaintainable output, which agents produce readily since nothing in a passing test suite penalizes a 200-line function. Belongs in the **Static** gate; same cost profile as linting, no reason to defer it.

| Language | Tool |
|---|---|
| Go | `gocyclo` or `cyclop` — both bundled with golangci-lint; `assets/golang/.golangci.yml` uses `disable-all: true`, so this is a one-line addition to its `enable:` list |
| Python | ruff's `C901`, via adding `"C90"` to the `select` list in `[tool.ruff.lint]` plus a `[tool.ruff.lint.mccabe] max-complexity` setting (the shipped config selects `C4`, which is flake8-comprehensions, not mccabe) |
| Node.js / Bun | ESLint's `complexity` rule; Biome's `noExcessiveCognitiveComplexity` |
| Rust | `clippy::cognitive_complexity` |
| Java | Checkstyle's `CyclomaticComplexity` module |
| .NET | Roslyn analyzer `CA1502` |

**Suite health** — catches flaky and order-dependent tests. A suite that passes only in one order, or passes intermittently, is not a deterministic gate; it is a gate that sometimes lies, which is worse than no gate because it trains people to re-run rather than investigate. Best as a nightly/weekly job rather than per-commit, same cost rationale as mutation testing.

| Language | Tool |
|---|---|
| Python | `pytest-randomly`, or `pytest -p no:randomly` to isolate |
| Go | `go test -shuffle=on` |
| Node.js | `vitest --sequence.shuffle` |
| Bun | Verify against Bun's current docs before asserting a flag — Bun ships frequently and its test runner has had gaps in this area. If no randomizer exists, running `tests/unit/` in split invocations surfaces the coarsest ordering coupling. (Same hedging convention `gate-structure.md` already applies to Bun's isolation mechanism.) |
| Rust | `cargo nextest run` — already used in ADV's Rust pipeline; runs each test in its own process by default, which surfaces shared-state coupling without extra configuration |
| Java | JUnit 5's `@TestMethodOrder(MethodOrderer.Random.class)` |
| .NET | No first-party randomizer. `[assembly: CollectionBehavior(DisableTestParallelization = true)]` toggled on and off surfaces parallelism-dependent assumptions, but genuine order randomization needs a third-party runner extension — state this gap plainly rather than implying parity with the other six. |

**Real execution before push** — catches "passes tests, doesn't run": imports that resolve under the test harness but not at runtime, config the tests stub out, an entry point nobody actually invoked. ADV already has this as the Deploy Gate's smoke test, but that runs post-merge; the addition is running the CLI, endpoint, or app once locally on realistic input before pushing. No tooling needed — it is the check that requires the least setup and catches the most embarrassing class of failure.

### Attribution

A short credit line at the end of the "Further recommended checks" section noting these were adapted from old-coder (MIT, © AmazingAng), with a link. The anti-gaming rules section carries the same attribution.

## Change 2: `README.md`, "Guarding against agent-specific failure modes"

**2a.** Add the anti-gaming rules as item 4, framed as the behavioral counterpart to items 1 and 2 (`CODEOWNERS` and permission scoping). "Condensed" means specifically: a two-sentence framing paragraph plus the six rules as a bare one-line-each list, with no per-rule elaboration and no cross-reference discussion — that fuller treatment lives in `gate-structure.md`, which the item links to. Target roughly 12 lines, matching the length of the existing items 1–3 rather than dwarfing them.

**2b.** Add one sentence to the existing item 3 (mutation testing) pointing at `gate-structure.md`'s expanded recommended-checks list, so a README reader learns the other three exist.

**2c. Fix a pre-existing inconsistency found while reviewing this section.** Its intro currently reads "Two structural guardrails close that gap:" and is then followed by three items — mutation testing was evidently added later without updating the count. Adding a fourth item makes the mismatch worse. The fix is to drop the numeral from the intro sentence rather than keep incrementing it.

## Verification

No code changes, so no test suite applies. Verification is:

1. Every tool named in the two tables is real and correctly attributed to its ecosystem. Two claims about ADV's own shipped configs were confirmed during design and should be re-confirmed if those files change: `assets/golang/.golangci.yml` does not currently enable a complexity linter (`disable-all: true` with an 11-linter enable list, none of them complexity-related), and `assets/python/pyproject-adv-fragment.toml` selects `C4` (flake8-comprehensions), not `C90` (mccabe). The Bun suite-health entry is deliberately written as "verify before asserting" rather than naming a flag — implementation must not replace it with an unverified flag name.
2. The README's "Two structural guardrails" count fix is applied and the section reads correctly with four items.
3. Attribution to old-coder is present in both locations that carry adapted material.
4. No claim in either file contradicts the ratchet rule or the seven-gate structure — specifically, none of the three added checks is presented as a new gate or as optional-to-skip once adopted.

## Non-goals

- Not adding an eighth gate. The seven-gate structure is ADV's identity; these are recommended additions *within* existing gates (complexity → Static) or alongside the pipeline as scheduled jobs (suite health), following the precedent already set by mutation testing.
- Not wiring any of the three checks into the shipped `gitlab-ci-*-adv.yml` pipelines. They are documented recommendations, consistent with how mutation testing is already handled.
- Not importing old-coder's workflow loop, its tier calibration, or its independent-verifier protocol.
- Not modifying the seven `pre-push.sh` scripts. "Real execution before push" is advice to a developer, not another automated stage — and the hook's own docs are emphatic that it enforces nothing.
