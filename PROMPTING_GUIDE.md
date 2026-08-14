# ADV Skill — Developer Prompting Guide

How to prompt Claude (chat, Claude Code, Cowork, or Antigravity with this skill installed) to get precise, non-generic output from the ADV framework skill. The skill triggers on natural language — no special syntax required — but the *specificity* of the prompt determines whether the output is immediately usable or something you'll spend time correcting.

---

## 1. What Claude assumes when you don't specify

Know these defaults so you know when it's safe to omit detail, and when omitting it will cost you a correction round-trip:

| If you don't specify... | Claude assumes... |
|---|---|
| CI platform | **GitLab CI** — every bundled asset targets it. Say "GitHub Actions" or "CircleCI" explicitly if that's your platform; the gate *structure* transfers but the YAML syntax doesn't, and Claude will need to translate rather than copy. |
| Coverage threshold | 80% diff-coverage (changed lines, not overall repo %) |
| Security severity policy | Critical/High blocks merge, Medium surfaces without blocking, Low is logged only |
| Which language | Claude will ask rather than guess if genuinely ambiguous — but a vague prompt with clues ("our Spring Boot service") will get Java assumed without asking, so confirm it picked correctly |
| Kanban tool | Nothing assumed — generic advice unless you name Plane, Asana, or another tool specifically. Naming the tool matters a lot here since Plane's GitLab integration is native and Asana's isn't; a generic prompt gets a generic (less useful) answer |
| Java build tool | Maven. Say "Gradle" if that's your project — the plugin mechanics differ enough that Claude shouldn't guess |

---

## 2. Prompt patterns by task, with before/after

### Generating a pipeline

**Weak**: "make me a ci pipeline"
**Better**: "Generate a GitLab CI ADV pipeline for our Java/Spring Boot service. We don't have an OpenAPI spec or Pact contracts yet — tell me which jobs to comment out for now."

The second version gets you a pipeline that matches your actual repo state on the first try, instead of one with jobs that immediately fail because infrastructure they assume doesn't exist yet.

### Explaining ADV conceptually

**Weak**: "what is ADV"
**Better**: "Explain ADV to a new engineer joining the team who's never worked with agentic coding tools before — keep it to the core principle and the anti-pattern, skip the tool-by-tool detail."

Naming the audience and the depth you want controls length and jargon level directly, rather than getting the default (thorough, assumes technical familiarity) explanation.

### Security-specific asks

**Weak**: "add security scanning"
**Better**: "We already run Trivy in our deploy stage. Add the Plane.so card-filing automation for Critical/High findings, using our existing severity policy."

Naming what you already have prevents Claude from regenerating a static-layer scanner setup you don't need and focuses effort on the actual gap.

### Guardrails (CODEOWNERS / agent permissions)

**Weak**: "stop the AI from breaking my tests"
**Better**: "We're using Claude Code with write access to the repo. Give me the CODEOWNERS + permission-scoping setup so it can't silently weaken a test or edit the pipeline config."

Naming the specific agent tool matters — the `claude-code-settings.json` asset is Claude-Code-specific syntax; for Antigravity or another tool, Claude needs to translate the *principle* since the config format isn't confirmed the same.

### Adding a language not yet covered

**Weak**: "add Rust support"
**Better**: "Add Rust support. We use `cargo nextest` for tests and `criterion` for benchmarks if there's a property-testing equivalent worth using — otherwise pick something idiomatic and explain the isolation mechanism choice like you did for Bun."

If you have existing tooling preferences, say so — otherwise Claude picks idiomatic defaults, but it's worth explicitly asking it to explain *why* it chose a given test-isolation mechanism (marker vs tag vs directory vs config-file split), since that reasoning is often the most transferable part of the answer.

### Kanban integration

**Weak**: "connect this to project management"
**Better**: "We use Plane.so. Show me how MR approval states should map to Plane work-item states, and where I'd need the API instead of the native integration."

Plane and Asana behave completely differently here (native state-sync vs comment-only integration needing custom webhook glue) — a tool-agnostic prompt gets a tool-agnostic (much less actionable) answer.

---

## 3. The anti-pattern to avoid *in your own prompts*

This is specific to ADV and worth calling out directly: don't ask Claude (or an agent using this skill) to **"review this and confirm it's correct"** as your final check before merging, deploying, or trusting agent-generated work. That request itself is the anti-pattern the whole framework exists to prevent — a second LLM opinion isn't independent verification, regardless of which model or tool gives it.

**Instead of**: "Review this PR and tell me if it's safe to merge."
**Ask for**: "What deterministic test or gate would catch it if this PR is wrong?" — then actually add that gate and let the pipeline decide, not the review.

This isn't a minor phrasing nitpick — it's the difference between using this skill correctly and quietly reintroducing the exact failure mode it was built to close.

---

## 4. Iterating on an existing pipeline

Once you have a pipeline in hand, refer back to it explicitly rather than re-describing the whole thing:

**Weak**: "make me a python pipeline" (again, from scratch, losing prior customization)
**Better**: "Bump the diff-coverage threshold in our Python pipeline from 80% to 90%, and add a mutation-testing job using mutmut, weekly not per-commit."

This gets you a targeted edit that preserves whatever you'd already customized, instead of a fresh regeneration that silently drops earlier decisions.

---

## 5. Controlling output format

Default output includes explanation of design decisions and caveats alongside the code/config — usually valuable, but say so explicitly if you want just the artifact:

- **"Just the YAML, no explanation"** — for when you already understand the pattern and want to move fast
- **"Explain the tradeoffs first, don't generate the file yet"** — for when you're still deciding, not ready to commit to an approach
- **"Here's our existing `.gitlab-ci.yml` — extend it to add the property-testing stage"** — pasting existing config gets you an edit that respects your current structure, rather than a parallel pipeline you have to manually reconcile

---

## Quick reference: phrases that reliably trigger this skill

You don't need exact keywords — natural descriptions of the underlying need work fine. These all trigger reliably:

- "verification debt" / "deterministic gates" / "CI/CD pipeline for [language]"
- "prevent the AI from marking its own homework"
- "ASDLC" / "agentic software development lifecycle"
- "CODEOWNERS for an agent-heavy repo"
- "property-based testing" / "mutation testing" / "golden-file testing"
- "wire pipeline results into [Plane/Asana/Jira]"

Simple one-line lookups ("what does `dotnet test --filter` do") may not trigger the skill even when related — Claude can usually answer those directly without consulting it, which is expected behavior, not a triggering failure.
