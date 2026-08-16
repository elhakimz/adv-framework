# Gate Integrity Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the narrow set of ideas from [old-coder](https://github.com/AmazingAng/old-coder) that ADV genuinely lacks — three deterministic checks absent from every pipeline, plus an explicit statement of the anti-gaming rules ADV currently enforces only structurally.

**Architecture:** Documentation-only. Two existing files change; no new files, no new assets, no new gates, and no changes to any shipped `gitlab-ci-*-adv.yml` or `pre-push.sh`. `references/gate-structure.md` gets the full treatment (agent-facing); `README.md` gets a condensed version plus a pointer (human-facing).

**Tech Stack:** Markdown only.

## Global Constraints

- **Two files change, no others**: `adv-framework/references/gate-structure.md` and `README.md`. No new files. Do not touch any `gitlab-ci-*-adv.yml`, any `pre-push.sh`, or any other reference doc.
- **Not a new gate.** ADV's seven-gate structure is its identity. Complexity folds into the existing **Static** gate; suite health is a scheduled job alongside the pipeline; real execution is a pre-push habit, not an automated stage. Nothing added here may be presented as an eighth gate.
- **Nothing added here may be presented as optional-to-skip once adopted**, and nothing may contradict the ratchet rule ("a gate is never quietly removed to unblock a release") or the seven-gate structure.
- **Language row order is `Java, Python, .NET, Go, Node.js, Bun, Rust`** in every new table — matching the existing isolation-mechanism table in `gate-structure.md` and the language table in `README.md`. (The existing mutation-testing list uses a different order; do not copy that one.)
- **Attribution required**: both new sections in `gate-structure.md` end with a credit line to old-coder (MIT, © AmazingAng) with a link. Text is paraphrased into ADV's voice, never lifted verbatim from the source repo.
- **Do not name an unverified Bun flag.** The Bun suite-health row is deliberately written as "check current docs before relying on one." Implementation must not replace this with an asserted flag name.
- **Two claims about ADV's own shipped configs are asserted in the new text** and were confirmed during design: `assets/golang/.golangci.yml` enables no complexity linter (it uses `disable-all: true` with an 11-linter allowlist), and `assets/python/pyproject-adv-fragment.toml` selects `C4` (flake8-comprehensions), not `C90` (mccabe). Task 1 re-verifies both before writing them.
- **Excluded from scope, deliberately**: old-coder's SPEC/EVIDENCE workflow loop, its independent-verifier protocol, and its Tier 1/2/3 calibration. Do not add them. (Rationale in the spec: the first two are agent process, which ADV does not govern; the tier calibration's "run fewer layers for small changes" half contradicts the ratchet rule.)

---

## Task 1: `gate-structure.md` — anti-gaming rules + further recommended checks

**Files:**
- Modify: `adv-framework/references/gate-structure.md` (two insertions: after line 25, and appended after the existing final section)

**Interfaces:**
- Produces: two new `##` sections — `## Anti-gaming rules` and `## Further recommended checks (not in the default pipelines)`. Task 2's README edits link to this file and reference both by name; the section titles must match exactly.

- [ ] **Step 1: Re-verify the two config claims before asserting them**

Run:
```bash
grep -nE "disable-all|gocyclo|cyclop|complexity" adv-framework/assets/golang/.golangci.yml
```
Expected: a hit on `disable-all: true` and **no** hit on `gocyclo`, `cyclop`, or `complexity`.

Run:
```bash
grep -nA3 'select = \[' adv-framework/assets/python/pyproject-adv-fragment.toml
```
Expected: the select list contains `"C4"` and does **not** contain `"C90"`.

If either expectation fails, the shipped configs changed since this plan was written — stop and report, rather than writing a now-false claim into the docs.

- [ ] **Step 2: Insert the anti-gaming rules section**

In `adv-framework/references/gate-structure.md`, insert the following **between** the end of the `## The anti-pattern this framework exists to prevent` section (the paragraph ending `...never stand in as the final merge gate itself.`) and the start of `## Why isolate property/regression tests from the default unit run`:

```markdown
## Anti-gaming rules

`CODEOWNERS` and agent permission scoping (see the README's "Guarding against agent-specific failure modes") prevent an agent from *committing* a weakened check. These rules name the behavior those guardrails exist to stop, so an agent working under ADV avoids the shapes deliberately rather than discovering them at a blocked merge:

1. **Never weaken a test to make it pass** — no broadened assertions, added skips, raised tolerances, or deleted failing tests.
2. **Never edit a test and its implementation in the same step** to reach green. Change one, observe the result, then change the other.
3. **Never mock the unit under test**, or mock so heavily that the test only exercises the mocks.
4. **Never add a test solely to raise a coverage number.** A test that executes lines without asserting behavior defeats the diff-coverage gate rather than satisfying it — it converts a real gate into a green light.
5. **Never report a check that wasn't run.** An honestly declared skip preserves trust; a fabricated pass destroys the only thing the gates are for.
6. **A failing gate blocks done.** Work is not complete while any gate is red — the ratchet rule applied at the scale of a single task.

Adapted from [old-coder](https://github.com/AmazingAng/old-coder) (MIT, © AmazingAng).
```

- [ ] **Step 3: Append the further-recommended-checks section**

Append the following to the **end** of `adv-framework/references/gate-structure.md`, after the existing `## Mutation testing (recommended addition, not in the default pipelines)` section (which currently ends with `Recommended as a nightly/weekly job rather than per-commit, given the runtime cost.`):

```markdown
## Further recommended checks (not in the default pipelines)

Like mutation testing above, these are recommended additions rather than shipped pipeline stages. Each is deterministic; none is a new gate — complexity folds into **Static**, suite health runs on a schedule alongside the pipeline, and real execution is a pre-push habit rather than an automated stage.

### Complexity budget

Nothing in a passing test suite penalizes a 200-line function, so agent-generated code drifts toward unmaintainable shapes that every existing gate happily approves. A complexity ceiling belongs in the **Static** gate — same cost profile as linting, no reason to defer it.

| Language | Tool |
|---|---|
| Java | Checkstyle's `CyclomaticComplexity` module |
| Python | ruff's `C901` — add `"C90"` to `select` in `[tool.ruff.lint]` plus a `[tool.ruff.lint.mccabe] max-complexity` value (the shipped fragment selects `C4`, which is flake8-comprehensions, not mccabe) |
| .NET | Roslyn analyzer `CA1502` |
| Go | `gocyclo` or `cyclop` — both bundled with golangci-lint; `assets/golang/.golangci.yml` uses `disable-all: true`, so enabling one is a single line in its `enable:` list |
| Node.js | ESLint's `complexity` rule |
| Bun | Biome's `noExcessiveCognitiveComplexity` |
| Rust | `clippy::cognitive_complexity` |

### Suite health

A suite that passes only in one order, or passes only intermittently, is not a deterministic gate — it is a gate that sometimes lies, which is worse than no gate because it trains people to re-run instead of investigate. Best as a nightly/weekly job, same cost rationale as mutation testing.

| Language | Tool |
|---|---|
| Java | JUnit 5's `@TestMethodOrder(MethodOrderer.Random.class)` |
| Python | `pytest-randomly` |
| .NET | No first-party randomizer. Toggling `[assembly: CollectionBehavior(DisableTestParallelization = true)]` surfaces parallelism-dependent assumptions, but genuine order randomization needs a third-party runner extension — the weakest story of the seven ecosystems here. |
| Go | `go test -shuffle=on` |
| Node.js | `vitest --sequence.shuffle` |
| Bun | Check Bun's current test-runner docs for a randomization flag before relying on one — Bun ships frequently and has had gaps here. Absent a flag, splitting `tests/unit/` across separate `bun test` invocations surfaces the coarsest ordering coupling. |
| Rust | `cargo nextest run` — already the runner in ADV's Rust pipeline; it runs each test in its own process by default, which surfaces shared-state coupling with no extra configuration |

### Real execution before push

The failure this catches is "passes tests, doesn't run": an import that resolves under the test harness but not at runtime, config the tests stub out, an entry point nobody actually invoked. ADV covers this as the Deploy Gate's smoke test — but that runs after merge. Running the CLI, endpoint, or app once locally on realistic input needs no tooling and catches the most embarrassing class of failure before it reaches a pipeline.

Adapted from [old-coder](https://github.com/AmazingAng/old-coder) (MIT, © AmazingAng).
```

- [ ] **Step 4: Verify structure and constraints**

Run:
```bash
grep -c "AmazingAng/old-coder" adv-framework/references/gate-structure.md
```
Expected: `2` (one attribution per new section).

Run:
```bash
grep -n "^## " adv-framework/references/gate-structure.md
```
Expected: `## Anti-gaming rules` appears **after** `## The anti-pattern this framework exists to prevent` and **before** `## Why isolate property/regression tests from the default unit run`; `## Further recommended checks (not in the default pipelines)` appears **last** in the file.

Run:
```bash
grep -nE "^\| (Java|Python|\.NET|Go|Node\.js|Bun|Rust) \|" adv-framework/references/gate-structure.md
```
Expected: two runs of seven rows each, both in the order Java, Python, .NET, Go, Node.js, Bun, Rust.

Confirm by reading the two new tables that every row has exactly two `|`-delimited cells plus leading/trailing pipes (a malformed row silently breaks the whole table's rendering).

- [ ] **Step 5: Commit**

```bash
git add adv-framework/references/gate-structure.md
git commit -m "$(cat <<'EOF'
Add anti-gaming rules and further recommended checks to gate-structure

Anti-gaming rules state the behavior CODEOWNERS and permission scoping
already prevent structurally, so an agent avoids those shapes rather
than discovering them at a blocked merge. Further recommended checks
covers three deterministic checks absent from every ADV pipeline:
complexity budget (belongs in Static), suite health (flaky and
order-dependent tests), and real execution before push.

Adapted from AmazingAng/old-coder (MIT).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `README.md` — condensed rules, pointer, and a count fix

**Files:**
- Modify: `README.md` (three edits, all within the `## Guarding against agent-specific failure modes` section, currently at lines 203–214)

**Interfaces:**
- Consumes: the two section titles created in Task 1 — `## Anti-gaming rules` and `## Further recommended checks (not in the default pipelines)` in `adv-framework/references/gate-structure.md`. Both are referenced by path from this file.

- [ ] **Step 1: Fix the pre-existing count mismatch in the section intro**

The intro sentence currently claims two guardrails and is followed by three items — mutation testing was added later without updating the count, and this task adds a fourth. Replace the intro paragraph's final clause.

Find, in `README.md`:
```
Deterministic gates catch *incorrect* code. They don't, by themselves, stop an agent with broad write access from "fixing" a red pipeline by weakening the thing that checks it — skipping a test, loosening an assertion, or editing the pipeline config directly. Two structural guardrails close that gap:
```

Replace with:
```
Deterministic gates catch *incorrect* code. They don't, by themselves, stop an agent with broad write access from "fixing" a red pipeline by weakening the thing that checks it — skipping a test, loosening an assertion, or editing the pipeline config directly. These guardrails close that gap:
```

- [ ] **Step 2: Add the pointer sentence to item 3**

Find the end of item 3's paragraph in `README.md`:
```
Recommended as a nightly/weekly job rather than per-commit, given the runtime cost.
```

Replace with:
```
Recommended as a nightly/weekly job rather than per-commit, given the runtime cost. Three further recommended checks — a complexity budget, suite-health runs for flaky and order-dependent tests, and real execution before push — are documented alongside it in `adv-framework/references/gate-structure.md`.
```

Note: the identical sentence `Recommended as a nightly/weekly job rather than per-commit, given the runtime cost.` also exists in `adv-framework/references/gate-structure.md`. This edit applies **only** to `README.md` — do not use a replace-all.

- [ ] **Step 3: Add item 4**

Insert immediately after item 3's (now-extended) paragraph and before the `---` that closes the section:

```markdown
### 4. Anti-gaming rules
Items 1 and 2 stop an agent from *committing* a weakened check. These name the behavior those guardrails exist to prevent, so an agent working under ADV avoids the shapes deliberately rather than discovering them at a blocked merge:

- Never weaken a test to make it pass.
- Never edit a test and its implementation in the same step to reach green.
- Never mock the unit under test.
- Never add a test solely to raise a coverage number.
- Never report a check that wasn't run.
- A failing gate blocks done.

Full treatment, with the rationale for each, in `adv-framework/references/gate-structure.md`.
```

- [ ] **Step 4: Verify**

Run:
```bash
grep -n "Two structural guardrails" README.md
```
Expected: no output (exit 1) — the stale count is gone.

Run:
```bash
grep -n "^### [0-9]\." README.md
```
Expected: items 1 through 4, in order, with no gap or duplicate numbering.

Run:
```bash
grep -c "references/gate-structure.md" README.md
```
Expected: `2` — one pointer from item 3, one from item 4.

Read the section start-to-finish once and confirm item 4 reads at a comparable length to items 1–3 (roughly 12 lines) rather than dwarfing them, and that it sits before the `---` closing the section.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Add anti-gaming rules to README's agent-failure-modes section

Adds the six rules as item 4 (condensed; full treatment lives in
gate-structure.md), points item 3 at the three further recommended
checks, and fixes a pre-existing mismatch where the intro claimed "two
structural guardrails" above a list of three.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Plan self-review notes

- **Spec coverage**: anti-gaming rules → Task 1 Step 2 and Task 2 Step 3; the three further checks → Task 1 Step 3; README item 4 → Task 2 Step 3; README item-3 pointer → Task 2 Step 2; the "Two structural guardrails" count fix → Task 2 Step 1; attribution → Task 1 Steps 2–3, verified in Step 4; the two shipped-config claims → re-verified in Task 1 Step 1 before being written; Bun hedging → carried into Task 1 Step 3's table verbatim and protected by a Global Constraint; tier calibration and the workflow loop → excluded, stated in Global Constraints so no implementer adds them back.
- **Placeholder scan**: no TBD/TODO. Every step has either the complete markdown to insert or an exact command with its expected result, including the failure path in Task 1 Step 1 (stop and report rather than write a false claim).
- **Consistency**: the two section titles created in Task 1 are the exact strings Task 2 references and Task 1 Step 4 greps for. Language row order (Java, Python, .NET, Go, Node.js, Bun, Rust) is fixed in Global Constraints and checked by a grep in Task 1 Step 4. Task 2 Step 2 flags the duplicate-sentence hazard that would otherwise make a naive replace-all corrupt `gate-structure.md`.
