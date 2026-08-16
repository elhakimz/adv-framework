# Automated Deterministic Verification (ADV) Framework

A language-agnostic CI/CD pipeline pattern for minimizing **verification debt** in agentic software development — where AI agents (Claude Code, Antigravity, Gemini CLI, or others) generate a meaningful share of the code.

> **Core principle:** every gate in this pipeline is pass/fail, reproducible, and free of judgment calls. Nothing merges on an agent's self-report that its own work is correct.

---

## Installing this skill

This repo's skill is the `adv-framework/` folder (the one containing `SKILL.md`, `references/`, and `assets/`) — Claude Code auto-discovers skills placed in a `skills/` directory, either user-wide or per-project.

**User-wide** (available in every project):

```bash
cp -r adv-framework ~/.claude/skills/adv-framework
```

**Project-only** (available just in one project):

```bash
cp -r adv-framework /path/to/your-project/.claude/skills/adv-framework
```

Start a new Claude Code session afterward — skills load at session start, not mid-session.

To keep the installed copy updated via `git pull` in this repo instead of re-copying, symlink instead of copying:

```bash
ln -s "$(pwd)/adv-framework" ~/.claude/skills/adv-framework
```

(On Windows, use `New-Item -ItemType SymbolicLink` from an elevated PowerShell, or `Copy-Item -Recurse` if you'd rather not deal with elevation.)

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

| Stage | Java | Python | .NET | Go | Node.js | Bun | Rust |
|---|---|---|---|---|---|---|---|
| Static | Checkstyle, PMD | ruff, mypy, bandit | `dotnet format`, Roslyn analyzers, SecurityCodeScan | golangci-lint, gosec, govulncheck | ESLint, Prettier, `tsc`, `npm audit` | Biome, `tsc` typecheck | rustfmt, clippy, cargo-audit, cargo-deny |
| Build | Maven | `python -m build` | `dotnet build` | `go build` | `npm run build` | `bun build` | `cargo build --release` |
| Unit + coverage | JUnit 5 + JaCoCo | pytest + coverage.py | xUnit + coverlet | `go test -race` + gocov | Vitest + coverage | `bun test` + coverage | cargo-nextest + cargo-llvm-cov |
| Property | jqwik | Hypothesis | FsCheck | rapid | fast-check | fast-check | proptest |
| Contract | Pact, Schemathesis, Flyway | Pact, Schemathesis, Alembic | Pact.NET, Schemathesis, EF Core | pact-go, Schemathesis, golang-migrate | Pact, Schemathesis, Prisma | Pact, Schemathesis, Drizzle Kit | Pact, Schemathesis, sqlx |
| Regression | golden-file (custom) | syrupy | Verify | goldie | Vitest snapshot | bun:test snapshot | insta |
| Isolation mechanism | file suffix (`*PropertyTest.java`) | pytest marker (`@pytest.mark.property`) | xUnit trait (`[Trait("Category","Property")]`) | build tag (`//go:build property`) | separate Vitest config files | directory structure (`tests/unit/`, `tests/property/`, `tests/regression/`) | Cargo's native test-target system (`tests/*.rs`) |

### Repo structure

```
.
├── CODEOWNERS                      # human-approval gate on test/pipeline files
├── claude-code-settings.json       # agent permission scoping (deny/ask lists)
│
└── adv-framework/                  # the skill itself
    ├── SKILL.md
    ├── references/
    │   ├── gate-structure.md       # full 7-gate table, ratchet rule, isolation mechanisms, anti-gaming rules, further checks
    │   ├── security.md             # security's expanded tool set, blocking policy
    │   ├── kanban-integration.md   # pipeline state → Kanban board state
    │   └── local-verification.md   # pre-push hook: what it runs, prerequisites, install
    └── assets/
        ├── java/
        │   ├── gitlab-ci-java-adv.yml
        │   ├── pom-adv-fragment.xml
        │   └── pre-push.sh
        ├── python/
        │   ├── gitlab-ci-python-adv.yml
        │   ├── pyproject-adv-fragment.toml
        │   ├── test_example_markers.py
        │   └── pre-push.sh
        ├── dotnet/
        │   ├── gitlab-ci-dotnet-adv.yml
        │   ├── Directory.Build.props
        │   ├── ExampleTests.cs
        │   └── pre-push.sh
        ├── golang/
        │   ├── gitlab-ci-golang-adv.yml
        │   ├── .golangci.yml
        │   ├── calculator_test.go
        │   ├── calculator_property_test.go
        │   ├── report_regression_test.go
        │   └── pre-push.sh
        ├── nodejs/
        │   ├── gitlab-ci-nodejs-adv.yml
        │   ├── eslint.config.js
        │   ├── vitest.config.ts / vitest.property.config.ts / vitest.regression.config.ts
        │   ├── calculator.test.ts, calculator.property.test.ts, report.regression.test.ts
        │   └── pre-push.sh
        ├── bun/
        │   ├── gitlab-ci-bun-adv.yml
        │   ├── biome.json, bunfig.toml
        │   ├── tests/{unit,property,regression}/  # isolation is directory structure, not naming
        │   └── pre-push.sh
        ├── rust/
        │   ├── gitlab-ci-rust-adv.yml
        │   ├── deny.toml
        │   ├── src/, tests/  # Cargo's own test-target system provides isolation
        │   └── pre-push.sh
        ├── guardrails/
        │   ├── CODEOWNERS                  # complete, all-7-ecosystems version
        │   └── claude-code-settings.json
        ├── security/
        │   ├── security-debt-ci-job.yml    # ready-to-use container-scan + Kanban card job
        │   └── create_security_debt_cards.py
        └── diagrams/
            └── adv-framework-diagram.mermaid
```

---

## Security

Security checks are not one line item in the static layer — they span multiple stages of the pipeline, and like every other gate in this framework, **they must be deterministic**. A model saying "this looks safe" is the same anti-pattern as an LLM reviewing LLM-written code; a security gate that isn't reproducible isn't a gate.

### Where security sits across the pipeline

| Stage | Security checks | Blocks on |
|---|---|---|
| Static | SAST (language-specific: Semgrep, bandit, gosec, SecurityCodeScan), dependency/SCA scanning, secret detection | Any high/critical finding |
| Build | SBOM generation (attached as artifact, not blocking by itself) | — |
| Contract | Schema validation prevents unvalidated input shapes reaching handlers | Contract violation |
| Regression | Security-relevant golden tests (auth bypass attempts, injection payloads as fixed test cases) | Any regression |
| Deploy Gate | Container image scan, DAST against staging, artifact signing/provenance check | Critical CVE in final image, failed signature verification |

This table is the target end state, not what ships by default — the base `gitlab-ci-*-adv.yml` pipelines only wire up the seven core gates (their deploy-gate stage is just smoke-test/deploy/rollback). Everything in this row is opt-in hardening; today only container-scan has a ready-made CI job (`adv-framework/assets/security/security-debt-ci-job.yml`) — IaC scanning, DAST, and provenance signing are documented patterns you add the same way.

### Expanded tool set

Beyond the SAST/dependency-scanning already in each language's static stage:

**Container & image scanning**
- `Trivy` or `Grype` — scans the final built container image, not just source dependencies. Catches vulnerabilities introduced by the base image itself (`FROM` line), which source-level SCA never sees.
- Run this in the **deploy-gate** stage against the actual artifact being shipped, not earlier against source — a clean dependency scan at build time doesn't guarantee a clean final image if the base image has known CVEs.

**Infrastructure-as-Code scanning** (if Terraform/Helm/K8s manifests are in the repo)
- `checkov` or `tfsec` — catches misconfigurations before they're applied: overly permissive IAM, public S3 buckets, missing encryption, containers running as root.
- Runs in the static stage, same cost profile as linting — no reason to defer it to deploy time.

**SBOM (Software Bill of Materials)**
- `Syft` (generates) — produces a CycloneDX or SPDX manifest of every dependency in the built artifact.
- Not a blocking gate on its own, but the artifact that makes every other security check *auditable* later — when a new CVE is disclosed next month, the SBOM is what tells you in seconds whether you're affected, instead of re-scanning every historical release.

**Dynamic Application Security Testing (DAST)**
- `OWASP ZAP` — runs against the actual deployed staging environment, not source code. Catches runtime-only issues static analysis structurally can't see: misconfigured headers, session handling flaws, actual exploitability of an endpoint rather than a theoretical pattern match.
- Belongs in the deploy-gate stage, after smoke tests confirm the environment is actually up.

**Supply chain / provenance**
- `cosign` (sigstore) — signs build artifacts and container images; the deploy-gate verifies the signature before allowing a deploy to proceed. This is what stops a compromised CI runner or a tampered artifact from reaching production undetected — the deploy step trusts a cryptographic signature, not "this artifact came from the pipeline, probably."
- Relevant especially once agents have write access to the repo: provenance verification means a deploy is gated on *what was actually built and signed*, not on trusting that nothing was altered between build and deploy.

### Severity-based blocking, not blanket blocking

A pipeline that fails the build on every low-severity finding trains people to ignore it — the alert fatigue itself becomes a security risk. The practical policy:

- **Critical / High** → blocks merge, no exceptions without an explicit, logged suppression with a reason and an expiry date.
- **Medium** → surfaces in the MR as a comment/report, doesn't block, tracked for scheduled remediation.
- **Low / informational** → logged, visible in the security dashboard, not surfaced per-MR.

Suppressions should live in a committed file (e.g. `.trivyignore`, `.semgrepignore` with an inline reason comment), not in someone's memory — an unreviewed suppression is a silent hole in the deterministic gate, same failure mode as an agent quietly weakening a test.

### Agent-specific consideration

The `CODEOWNERS` and permission-scoping guardrails from the next section apply directly here: an agent "fixing" a failing security scan by adding a suppression file, rather than fixing the underlying vulnerability, is the security-specific version of the same anti-pattern already covered for tests and pipeline config. Suppression files belong on the `CODEOWNERS`-protected list alongside test files and CI config.

---

## Guarding against agent-specific failure modes

Deterministic gates catch *incorrect* code. They don't, by themselves, stop an agent with broad write access from "fixing" a red pipeline by weakening the thing that checks it — skipping a test, loosening an assertion, or editing the pipeline config directly. These guardrails close that gap:

### 1. `CODEOWNERS`
Requires explicit human approval on any change to test files, pipeline configs, lint rulesets, golden/snapshot files, and dependency manifests — regardless of whether a human or an agent authored the diff. An agent can freely modify implementation code; it cannot silently modify what "correct" means.

### 2. Agent permission scoping
Tool-level deny/ask rules (e.g. Claude Code's `.claude/settings.json`) prevent an agent from editing pipeline/test-quality files even mid-session, or force an explicit approval prompt before it does. Configure the equivalent wherever your agent tooling exposes permission scoping — the principle transfers even where the config format doesn't.

### 3. Mutation testing (recommended, not yet wired into the pipelines above)
Coverage percentage measures whether a line *executed* during tests, not whether a test would actually *catch* a bug in that line — a real gap when the same agent both implements and writes its own tests. Mutation testing tools (`PIT` / Java, `Stryker` / .NET & JS, `mutmut` / Python, `go-mutesting` / Go) inject small bugs and check whether the suite catches them, surfacing tests that pass without verifying anything. Recommended as a nightly/weekly job rather than per-commit, given the runtime cost. Three further recommended checks — a complexity budget, suite-health runs for flaky and order-dependent tests, and real execution before push — are documented alongside it in `adv-framework/references/gate-structure.md`.

### 4. Anti-gaming rules
Items 1 and 2 stop an agent from *committing* a weakened check. These name the behavior those guardrails exist to prevent, so an agent working under ADV avoids the shapes deliberately rather than discovering them at a blocked merge:

- Never weaken a test to make it pass.
- Never edit a test and its implementation in the same step to reach green.
- Never mock the unit under test.
- Never add a test solely to raise a coverage number.
- Never report a check that wasn't run.
- A failing gate blocks done.

Full treatment, with the rationale for each, in `adv-framework/references/gate-structure.md`.

---

## Running gates locally before push

This is a fast-feedback convenience, not a gate — it catches problems
before a push instead of after one. It doesn't change what's enforced:
the CI pipeline and `CODEOWNERS` remain the only things that actually
gate a merge, and `git push --no-verify` skips it entirely.

Each language ships an opt-in pre-push hook (`adv-framework/assets/<lang>/pre-push.sh`)
that runs Static, Build, Unit (with diff-coverage), and Property locally
— the four gates that need nothing but your own toolchain. Contract,
Regression, and Deploy Gate stay CI-only. See
`adv-framework/references/local-verification.md` for prerequisites,
the install step, and why three of the CI's static jobs (`sast`,
`dependency_scanning`, `secret_detection`) aren't mirrored locally.

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
