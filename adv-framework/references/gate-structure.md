# ADV Gate Structure — Reference

## The 7 gates, in order

Each gate only runs once the previous one is green. Every gate is pass/fail — never "looks mostly fine."

| # | Stage | Purpose | Examples |
|---|---|---|---|
| 1 | Static | Type checks, linting, formatting, SAST, dependency/secret scanning | tsc, ruff, mypy, Checkstyle, golangci-lint, Semgrep, Trivy |
| 2 | Build | Compiles / bundles | mvn compile, go build, dotnet build |
| 3 | Unit | Fixed input → expected output, + diff-coverage gate | JUnit, pytest, xUnit, go test |
| 4 | Property / Invariant | A rule holds for ALL inputs, not just examples | jqwik, Hypothesis, FsCheck, rapid |
| 5 | Contract / Integration | API schemas, DB migrations, service contracts | Schemathesis, Pact, Flyway/Alembic/EF/golang-migrate |
| 6 | Regression | Golden-file / snapshot diff vs known-good output | syrupy, Verify, goldie, custom golden-file |
| 7 | Deploy Gate | Smoke test + rollback trigger | Playwright smoke, health-check-gated CD |

## The ratchet rule

When something escapes to production despite a green pipeline, the fix is never just patching the bug — it's adding the deterministic gate that would have caught it. The verification suite only grows. A gate is never quietly removed to unblock a release; that is how verification debt re-enters a project that thought it had eliminated it.

## The anti-pattern this framework exists to prevent

**An LLM reviewing LLM-generated output is not a deterministic gate**, no matter how it's framed — an explicit "does this look correct?" review prompt, an agent's own self-reported confidence, or a platform feature that shows agent-generated screenshots/recordings as "proof" of correctness. All of these are the same failure mode: the system that produced the work is also the system certifying the work, so systematic blind spots in the implementation are systematic blind spots in the review.

LLM review still has a legitimate place — flagging ambiguity, suggesting what to test, summarizing a large diff for a human — but it should always route work *toward* a human or *toward* a new deterministic check, never stand in as the final merge gate itself.

## Anti-gaming rules

`CODEOWNERS` and agent permission scoping (see SKILL.md's "Guardrails against agent-specific failure modes") prevent an agent from *committing* a weakened check. These rules name the behavior those guardrails exist to stop, so an agent working under ADV avoids the shapes deliberately rather than discovering them at a blocked merge:

1. **Never weaken a test to make it pass** — no broadened assertions, added skips, raised tolerances, or deleted failing tests.
2. **Never edit a test and its implementation in the same step** to reach green. Change one, observe the result, then change the other.
3. **Never mock the unit under test**, or mock so heavily that the test only exercises the mocks.
4. **Never add a test solely to raise a coverage number.** A test that executes lines without asserting behavior defeats the diff-coverage gate rather than satisfying it — it converts a real gate into a green light.
5. **Never report a check that wasn't run.** An honestly declared skip preserves trust; a fabricated pass destroys the only thing the gates are for.
6. **A failing gate blocks done.** Work is not complete while any gate is red — the ratchet rule applied at the scale of a single task.

Adapted from [old-coder](https://github.com/AmazingAng/old-coder) (MIT, © AmazingAng).

## Why isolate property/regression tests from the default unit run

Property-based tests and golden-file/snapshot tests are valuable but slow (property tests run hundreds of generated inputs; snapshot tests often touch the filesystem). Every language ecosystem in this skill uses a different mechanism to keep them out of the fast default test run, and only pull them in during their own CI stage:

| Language | Isolation mechanism |
|---|---|
| Java | File suffix convention (`*PropertyTest.java`, `*RegressionTest.java`) + separate Maven profiles |
| Python | pytest markers (`@pytest.mark.property`, `@pytest.mark.regression`) + `-m` filter |
| .NET | xUnit traits (`[Trait("Category","Property")]`) + `--filter` |
| Go | Build tags (`//go:build property`) — the file is invisible to a plain `go test ./...` |
| Node.js | Multiple Vitest config files (`vitest.config.ts` excludes `*.property.test.ts`/`*.regression.test.ts`; `vitest.property.config.ts` and `vitest.regression.config.ts` each include only their own suffix) |
| Bun | **Directory structure**, not naming/markers/tags — `tests/unit/`, `tests/property/`, `tests/regression/`, selected via an explicit path argument to `bun test`. Bun's test runner has no built-in include/exclude glob mechanism as of early 2026 (open upstream issue); directory scoping sidesteps that limitation entirely rather than working around it. Verify against Bun's current release notes before assuming this is still the constraint — Bun ships frequently. |
| Rust | **Cargo's own test-target system** — no config file or naming convention needed at all. Inline `#[cfg(test)]` modules in `src/` are the `--lib` target; each file under `tests/` compiles as its own separate integration-test binary. `cargo nextest run --lib` = unit only; `cargo nextest run --test property_tests` = only that file. The isolation is structural, native to how Cargo already organizes a project — the cleanest mechanism of the seven languages in this skill precisely because nothing extra had to be invented for it. |

This distinction matters when generating code for a specific stack — use the idiom native to that ecosystem, not a generic pattern translated awkwardly. Bun in particular should not be treated as "Node.js with a different install command" — its test-isolation mechanism is structurally different, not just syntactically different. Rust should not be given a suffix/marker convention by default — that would be actively less idiomatic than just using Cargo's existing `tests/` directory semantics.

## Adopting incrementally

Don't stand up all seven gates at once — a pipeline nobody trusts as blocking is worse than no pipeline. Suggested order when a user is starting from zero:

1. Static + build + unit (cheap, immediate payoff)
2. Diff-coverage gate (highest-leverage single addition — catches agent-generated changes with tests only on the easy path)
3. Property testing, piloted on one high-risk module
4. Contract testing, once more than one service/consumer exists
5. Regression + deploy gate, once the above are trusted
6. `CODEOWNERS` + agent permission scoping — set up early, not as an afterthought, once any agent has repo write access at all

## Non-goals (state these if a user seems to expect ADV to do more than it does)

- Not a replacement for human judgment on architecture, product fit, or requirement correctness — gates verify code matches spec, not that the spec was the right spec.
- Not a guarantee against a sufficiently adversarial input reaching an agent with broad tool access (e.g. prompt injection). Permission scoping reduces blast radius, doesn't eliminate the risk.
- Not "no LLM involvement in review" — LLM-assisted review is a useful signal generator, never the final gate.

## Mutation testing (recommended addition, not in the default pipelines)

Coverage percentage measures whether a line *executed* during tests, not whether a test would actually *catch* a bug in that line — a real gap when the same agent both implements and writes its own tests. Mutation testing tools inject small bugs and check whether the suite catches them:

- Java: `PIT`
- .NET / JS / Node.js / Bun: `Stryker` (StrykerJS covers Node.js, TypeScript, and Bun-run projects — same mutation engine, since it operates on the JS/TS source, not the runtime)
- Python: `mutmut`
- Go: `go-mutesting`
- Rust: `cargo-mutants`

Recommended as a nightly/weekly job rather than per-commit, given the runtime cost.

## Further recommended checks (not in the default pipelines)

Like mutation testing above, these are recommended additions rather than shipped pipeline stages. Each is deterministic; none is a new gate — complexity folds into **Static**, suite health runs on a schedule alongside the pipeline, and real execution is a pre-push habit rather than an automated stage.

### Complexity budget

Nothing in a passing test suite penalizes a 200-line function, so agent-generated code drifts toward unmaintainable shapes that every existing gate happily approves. A complexity ceiling belongs in the **Static** gate — same cost profile as linting, no reason to defer it.

| Language | Tool |
|---|---|
| Java | Checkstyle's `CyclomaticComplexity` module |
| Python | ruff's `C901` — add `"C90"` to `select` in `[tool.ruff.lint]` plus a `[tool.ruff.lint.mccabe] max-complexity` value (the shipped fragment selects `C4`, which is flake8-comprehensions, not mccabe) |
| .NET | Roslyn analyzer `CA1502` (off by default — enable explicitly, e.g. via `.editorconfig` severity configuration) |
| Go | `gocyclo` or `cyclop` — both bundled with golangci-lint; `assets/golang/.golangci.yml` uses `disable-all: true`, so enabling one is a single line in its `enable:` list |
| Node.js | ESLint's `complexity` rule |
| Bun | Biome's `noExcessiveCognitiveComplexity` |
| Rust | `clippy::cognitive_complexity` (allow-by-default nursery lint — does nothing until enabled; carries nursery false-positive caveats) |

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
