# adv-framework
# Automated Deterministic Verification (ADV) Framework

A language-agnostic CI/CD pipeline pattern for minimizing **verification debt** in agentic software development — where AI agents (Claude Code, Antigravity, Gemini CLI, or others) generate a meaningful share of the code.

> **Core principle:** every gate in this pipeline is pass/fail, reproducible, and free of judgment calls. Nothing merges on an agent's self-report that its own work is correct.

---

## Why this exists

Coding agents can generate large volumes of code far faster than a human can read every diff line by line. That speed doesn't automatically produce correct software — it produces **verification debt**: a gap between "code was written" and "code was actually checked," which grows silently until it surfaces as a production incident.

ADV closes that gap by replacing manual, judgment-based review with a layered pipeline of deterministic checks: same input always produces the same verdict, and every gate is either green or red — never "looks mostly fine."

### The anti-pattern this framework exists to prevent

The most common shortcut in agentic workflows is substituting an **LLM-based review** for deterministic verification — asking a model "does this diff look correct?" and treating a "yes" as a passing gate. This is not verification. It's a second opinion from the same class of system that produced the code, inheriting the same blind spots. This applies whether the "second opinion" is an explicit review prompt, or a platform feature (e.g. agent-generated screenshots/recordings presented as proof of correctness) — **if the agent that did the work is also the one certifying the work, nothing independent has checked it.**

LLM review still has a legitimate place: flagging ambiguity, suggesting what to test, summarizing a large diff for a human. It should route work *toward* a human or *toward* a new deterministic check — it should never itself be the reason something merges.

---

## The gate structure

Gates run from cheapest/fastest to most expensive/slowest. A failure at any layer stops the pipeline — later, costlier layers only run once everything before them is green.

| Stage | Purpose | Runs on |
|---|---|---|
| **1. Static** | Type checks, linting, formatting, SAST, dependency/secret scanning | Every commit / MR |
| **2. Build** | Compiles or bundles successfully | Every commit / MR |
| **3. Unit** | Fixed input → expected output tests, with diff-coverage gate | Every commit / MR |
| **4. Property / Invariant** | A rule holds for *all* inputs, not just hand-picked examples | Every commit / MR |
| **5. Contract / Integration** | API schemas, service contracts, DB migrations | Every commit / MR |
| **6. Regression** | Golden-file / snapshot comparison against known-good output | Every commit / MR |
| **7. Deploy Gate** | Smoke test + auto-rollback trigger | Merge to default branch |

**Ratchet rule:** when something escapes to production despite a green pipeline, the fix is not just patching the bug — it's adding the deterministic gate that would have caught it. The suite only grows; a gate is never quietly removed to unblock a release.

---

## Language implementations

Each implementation follows the same 7-stage structure with stack-appropriate tools. The **isolation mechanism** (how property/regression tests are kept out of the fast default test run) differs per ecosystem — see the note under each.

| Stage | Java | Python | .NET | Go |
|---|---|---|---|---|
| Static | Checkstyle, PMD | ruff, mypy, bandit | `dotnet format`, Roslyn analyzers, SecurityCodeScan | golangci-lint, gosec, govulncheck |
| Build | Maven | `python -m build` | `dotnet build` | `go build` |
| Unit + coverage | JUnit 5 + JaCoCo | pytest + coverage.py | xUnit + coverlet | `go test -race` + gocov |
| Property | jqwik | Hypothesis | FsCheck | rapid |
| Contract | Pact, Schemathesis, Flyway | Pact, Schemathesis, Alembic | Pact.NET, Schemathesis, EF Core | pact-go, Schemathesis, golang-migrate |
| Regression | golden-file (custom) | syrupy | Verify | goldie |
| Isolation mechanism | file suffix (`*PropertyTest.java`) | pytest marker (`@pytest.mark.property`) | xUnit trait (`[Trait("Category","Property")]`) | build tag (`//go:build property`) |

### Repo structure

```
.
├── .gitlab-ci.yml                  # pick the variant matching your stack
├── CODEOWNERS                      # human-approval gate on test/pipeline files
├── .claude/
│   └── settings.json               # agent permission scoping (deny/ask lists)
│
├── java/
│   ├── gitlab-ci-java-adv.yml
│   └── pom-adv-fragment.xml
├── python/
│   ├── gitlab-ci-python-adv.yml
│   ├── pyproject-adv-fragment.toml
│   └── test_example_markers.py
├── dotnet/
│   ├── gitlab-ci-dotnet-adv.yml
│   ├── Directory.Build.props
│   └── ExampleTests.cs
└── golang/
    ├── gitlab-ci-golang-adv.yml
    ├── .golangci.yml
    ├── calculator_test.go
    ├── calculator_property_test.go
    └── report_regression_test.go
```

---

## Guarding against agent-specific failure modes

Deterministic gates catch *incorrect* code. They don't, by themselves, stop an agent with broad write access from "fixing" a red pipeline by weakening the thing that checks it — skipping a test, loosening an assertion, or editing the pipeline config directly. Two structural guardrails close that gap:

### 1. `CODEOWNERS`
Requires explicit human approval on any change to test files, pipeline configs, lint rulesets, golden/snapshot files, and dependency manifests — regardless of whether a human or an agent authored the diff. An agent can freely modify implementation code; it cannot silently modify what "correct" means.

### 2. Agent permission scoping
Tool-level deny/ask rules (e.g. Claude Code's `.claude/settings.json`) prevent an agent from editing pipeline/test-quality files even mid-session, or force an explicit approval prompt before it does. Configure the equivalent wherever your agent tooling exposes permission scoping — the principle transfers even where the config format doesn't.

### 3. Mutation testing (recommended, not yet wired into the pipelines above)
Coverage percentage measures whether a line *executed* during tests, not whether a test would actually *catch* a bug in that line — a real gap when the same agent both implements and writes its own tests. Mutation testing tools (`PIT` / Java, `Stryker` / .NET & JS, `mutmut` / Python, `go-mutesting` / Go) inject small bugs and check whether the suite catches them, surfacing tests that pass without verifying anything. Recommended as a nightly/weekly job rather than per-commit, given the runtime cost.

---

## Adopting incrementally

Don't stand up all seven layers at once — a pipeline nobody trusts as blocking is worse than no pipeline. Suggested order:

1. **Static + build + unit** — cheap, immediate payoff, catches the majority of issues.
2. **Diff-coverage gate** — the single highest-leverage addition once unit tests exist; prevents agent-generated changes from shipping with tests only on the easy path.
3. **Property testing** on your most bug-prone or highest-risk module, as a pilot.
4. **Contract testing** once more than one service/consumer exists.
5. **Regression + deploy gate** once the above are trusted and stable.
6. **`CODEOWNERS` + agent permission scoping** — set up early, not as an afterthought, once agents have repo write access at all.

---

## Non-goals

- **Not a replacement for human judgment on architecture, product fit, or requirement correctness.** Deterministic gates verify that code does what the spec says — they can't verify the spec was the right spec.
- **Not a guarantee against a sufficiently sophisticated adversarial input** (e.g. prompt injection reaching an agent with broad tool access). Permission scoping reduces blast radius; it doesn't eliminate the risk of an agent acting on untrusted content it reads during a task.
- **Not "no LLM involvement in review."** LLM-assisted review is fine and useful as a *signal generator* — it should never be the *final gate*.
