---
name: adv-framework
description: Design, explain, or implement Automated Deterministic Verification (ADV) — a language-agnostic 7-stage CI/CD gate structure (static, build, unit, property, contract, regression, deploy-gate) for minimizing verification debt, especially where AI agents (Claude Code, Antigravity, Gemini CLI) generate code. Covers Java, Python, .NET, Go, Node.js, Bun, and Rust. Use whenever the user asks about CI/CD pipelines, GitLab CI, verification gates, test strategy, ASDLC, preventing "LLM reviews LLM output," property-based testing, mutation testing, security scanning gates, CODEOWNERS/agent permission scoping, or wiring pipeline results into Kanban/project tools — even without saying "ADV" explicitly. Also use for a `.gitlab-ci.yml`, build config (pom.xml, pyproject.toml, csproj, go tooling, package.json/vitest config, bunfig.toml, Cargo.toml/deny.toml), or CODEOWNERS file for any of these seven stacks where verification rigor matters.
---

# Automated Deterministic Verification (ADV) Framework

A pipeline pattern where every gate is pass/fail, reproducible, and free of judgment calls — nothing merges on an agent's self-report that its own work is correct.

## Core principle (state this whenever explaining ADV)

> Every gate in this pipeline is pass/fail, reproducible, and free of judgment calls. Nothing merges on an agent's self-report that its own work is correct.

The reason this framework exists: coding agents generate code far faster than a human can read every diff. That speed doesn't produce correctness by itself — it produces **verification debt**, a gap between "code was written" and "code was actually checked," which grows silently until it surfaces as a production incident.

**The anti-pattern this framework exists to prevent**: substituting an LLM-based review (an explicit "does this look right?" prompt, an agent's own confidence claim, or agent-generated screenshots presented as "proof") for deterministic verification. This is not verification — it's a second opinion from the same system that produced the work, inheriting the same blind spots. Always name this explicitly when a user's plan risks it (e.g. "have Claude Code review its own PR before merge" or "let the agent verify its own tests pass and merge automatically").

## When to go deeper — read the reference files

Don't try to hold all of ADV's detail in working memory for a specific task. Load what's relevant:

- **`references/gate-structure.md`** — the full 7-gate table, the ratchet rule, why property/regression tests are isolated per-language (different mechanism per ecosystem), incremental adoption order, non-goals, and mutation testing. Read this before explaining ADV conceptually or designing a pipeline from scratch.
- **`references/security.md`** — how security spans multiple gates (not just static), the expanded tool set (Trivy, Syft, ZAP, cosign), severity-based blocking policy, and the agent-specific suppression-file risk. Read this when the user's request touches security scanning, SAST/DAST, container scanning, or CVE handling.
- **`references/kanban-integration.md`** — mapping pipeline state to Kanban board state (Plane.so native integration vs Asana's comment-only integration requiring custom webhook glue), and the "Human Gate" column pattern. Read this when the user wants pipeline results visible on a project board.
- **`references/local-verification.md`** — the opt-in pre-push hook scripts (`assets/<lang>/pre-push.sh`), what they run locally vs. leave to CI, and the prerequisites per language. Read this when the user wants faster local feedback before pushing — and note explicitly that this is a convenience layer, not a merge gate; CI + CODEOWNERS remain what's actually enforced.

## When the user wants a working pipeline — use the bundled assets, don't regenerate from scratch

Each language has a complete, tested `.gitlab-ci.yml` plus the matching build-tool config already written. **Copy and adapt these rather than writing new ones from first principles** — they already encode the correct per-ecosystem isolation mechanism for property/regression tests, which is easy to get wrong if generated ad hoc.

| Language | CI pipeline | Build-tool config | Example tests | Local hook |
|---|---|---|---|---|
| Java (Maven) | `assets/java/gitlab-ci-java-adv.yml` | `assets/java/pom-adv-fragment.xml` | — | `assets/java/pre-push.sh` |
| Python | `assets/python/gitlab-ci-python-adv.yml` | `assets/python/pyproject-adv-fragment.toml` | `assets/python/test_example_markers.py` | `assets/python/pre-push.sh` |
| .NET (ASP.NET) | `assets/dotnet/gitlab-ci-dotnet-adv.yml` | `assets/dotnet/Directory.Build.props` | `assets/dotnet/ExampleTests.cs` | `assets/dotnet/pre-push.sh` |
| Go | `assets/golang/gitlab-ci-golang-adv.yml` | `assets/golang/.golangci.yml` | `assets/golang/calculator_test.go`, `calculator_property_test.go`, `report_regression_test.go` | `assets/golang/pre-push.sh` |
| Node.js (TypeScript) | `assets/nodejs/gitlab-ci-nodejs-adv.yml` | `assets/nodejs/eslint.config.js` + three Vitest configs (`vitest.config.ts`, `vitest.property.config.ts`, `vitest.regression.config.ts`) | `assets/nodejs/calculator.test.ts`, `calculator.property.test.ts`, `report.regression.test.ts` | `assets/nodejs/pre-push.sh` |
| Bun | `assets/bun/gitlab-ci-bun-adv.yml` | `assets/bun/biome.json`, `assets/bun/bunfig.toml` | `assets/bun/tests/{unit,property,regression}/*.test.ts` — directory placement is the isolation mechanism, not the filename | `assets/bun/pre-push.sh` |
| Rust | `assets/rust/gitlab-ci-rust-adv.yml` | `assets/rust/deny.toml` | `assets/rust/src/calculator.rs` (inline unit tests), `assets/rust/tests/property_tests.rs`, `assets/rust/tests/regression_tests.rs` — Cargo's own `tests/` directory convention is the isolation mechanism, nothing extra needed | `assets/rust/pre-push.sh` |

Each pipeline follows the identical 7-stage structure (static → build → unit → property → contract → regression → deploy-gate) with stack-appropriate tools. When presenting one to a user:
1. Copy the relevant `.gitlab-ci.yml` and build-config fragment.
2. Flag which jobs assume infrastructure that may not exist yet (OpenAPI spec, Pact contracts, a migration tool) — comment those out rather than shipping permanently red jobs, per the pattern established in the assets themselves.
3. Explain the isolation mechanism for that specific language (see `references/gate-structure.md` table) so the user understands *why* the test file naming/marker/trait/tag/directory convention matters, not just that it's there.

**Bun needs extra care, don't treat it as "Node.js with a faster installer."** Two things are structurally different, not just syntactically:
- Test isolation is **directory-based** (`tests/unit/`, `tests/property/`, `tests/regression/`), because Bun's test runner has no built-in glob include/exclude mechanism as of early 2026 — this is an open upstream limitation, not a design choice made for this skill. Verify against Bun's current changelog before assuming it's still true; Bun ships releases frequently and this may since have been added.
- `bunfig.toml`'s `coverageThreshold` has a documented gotcha: it's been reported to apply **per-file**, not as an aggregate — a project comfortably above its overall target can still fail the gate because one low-coverage file trips it individually. If a user's Bun coverage gate fails unexpectedly with all tests green, check per-file numbers before assuming the pipeline itself is broken.
- Bun's lockfile is `bun.lock` (text-based, git-diffable) as the current default — not the older binary `bun.lockb`. This matters for the static/dependency-scanning stage: a readable lockfile is what makes automated scanning and human review of dependency changes actually work.

**Rust needs the opposite correction — resist adding unnecessary machinery.** Every other language in this skill needed *something* invented for test isolation (a suffix convention, a marker, a trait, a build tag, a directory convention). Rust doesn't — Cargo's existing distinction between the `--lib` target (inline `#[cfg(test)]` modules) and each file under `tests/` (a separate integration-test binary) already does the job natively. If a user asks for a suffix or marker convention for Rust "to match the other languages," explain that Cargo's structure already provides this for free and adding a parallel convention on top would be redundant, not more consistent.

## Guardrails against agent-specific failure modes

Deterministic gates catch incorrect code. They don't stop an agent with broad write access from "fixing" a red pipeline by weakening what checks it — skipping a test, loosening an assertion, editing the pipeline config directly, or adding a security suppression instead of fixing the vulnerability.

Two ready-to-use assets close this gap:

- **`assets/guardrails/CODEOWNERS`** — requires human approval on any change to test files, CI config, lint rulesets, golden/snapshot files, dependency manifests, and security suppression files, regardless of whether a human or an agent authored the diff.
- **`assets/guardrails/claude-code-settings.json`** — a `deny`/`ask` permission scope for Claude Code specifically. `deny` files can't be touched even if the agent decides that's the fix; `ask` files trigger an explicit approval prompt mid-session rather than a silent edit. The same deny/ask principle applies to any other agent tool (Antigravity, Gemini CLI) that exposes permission scoping — the config format differs, the principle doesn't.

When a user is setting up agent tooling (Claude Code, Antigravity, etc.) with write access to a repo, proactively suggest these two files even if not explicitly asked — this is the highest-leverage, lowest-effort guardrail against the core anti-pattern.

## Visual explanation

`assets/diagrams/adv-framework-diagram.mermaid` — a complete Mermaid flowchart showing the 7-gate pipeline, the `CODEOWNERS` human-gate decision point, the ratchet feedback loop, and the anti-pattern called out as a visually distinct, disconnected node. Paste directly into a GitHub/GitLab markdown file (renders natively in both) or into a chat response inside a ```` ```mermaid ```` fence when a user asks for a diagram of ADV, the pipeline, or the gate flow.

## Security debt → Kanban automation

`assets/security/security-debt-ci-job.yml` + `assets/security/create_security_debt_cards.py` — a working GitLab CI job pair (Trivy container scan → Plane.so work-item creation for Critical/High findings) demonstrating the security + Kanban integration patterns together. Use as a template when a user wants security findings to surface automatically as tracked work rather than only living in a pipeline log. Read `references/security.md` and `references/kanban-integration.md` together before adapting this for a different scanner or board tool.

## Applying this conceptually (non-code requests)

When a user asks a conceptual question ("what is ADV," "why deterministic verification," "how does this relate to ASDLC") rather than requesting a pipeline, answer from `references/gate-structure.md` directly — don't reach for the code assets. Key framings to reuse:

- ADV is how ASDLC (Agentic Software Development Lifecycle) avoids verification debt: the human's role shifts from executor to validator/constraint-setter, and deterministic gates are what makes that shift trustworthy instead of just faster-and-riskier.
- The distinction between non-determinism at **development time** (gateable — an agent writes code, ADV verifies it once, the resulting artifact is deterministic forever after) versus non-determinism at **runtime** (not practically gateable — an LLM called live inside a production workflow re-introduces uncertainty on every single invocation) is the sharpest way to explain why "LLM writes code" and "LLM makes live business decisions" are different risk categories, not the same thing with different confidence levels.
- LLMs belong in a workflow as a **non-authoritative interpretation/routing/drafting layer**, with a deterministic gate between the LLM's output and any real effect (a transaction, an approval, a compliance record) — never as the source of truth for core business logic.
