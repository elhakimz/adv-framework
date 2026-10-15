# Local Pre-Push Verification — Reference

This hook is a fast-feedback convenience, not a gate. It catches problems
before a push instead of after one. It is not part of what's enforced —
the CI pipeline and `CODEOWNERS` remain the only things that actually
gate a merge. Nothing about running this locally, or configuring it,
weakens or replaces any CI stage. `git push --no-verify` skips it
entirely, and a fresh clone has it disabled until someone runs the
install step below — this hook is convenience by design, not a control.

## What it runs

Each `assets/<lang>/pre-push.sh` runs, in order, the same commands as
that language's `gitlab-ci-<lang>-adv.yml`, for the four gates that need
nothing but the local toolchain:

- **Static** — linting, formatting, type-checking, the SAST tools that
  have a real local CLI (not the three GitLab-template `sast` /
  `dependency_scanning` / `secret_detection` stub jobs — those resolve
  via GitLab's own `include:` templates and have no local command to
  mirror; the hook does not attempt to replicate them)
- **Build**
- **Unit**, including the diff-coverage gate — the script fetches
  `origin/<default-branch>` first, exactly as CI diffs against it
- **Property**

**Not included**: Contract (needs a Postgres service container),
Regression (slow, and CI deliberately treats snapshot-updates as a human
decision — not something to rush through in a pre-push hook), Deploy Gate
(needs a real environment). These stay CI-only.

## What it writes to your working tree

Running these scripts produces per-language build/coverage artifacts in
the checkout — e.g. `coverage.xml`, `coverage.out`, `security-scan.log`,
`coverage/`, `coverage-report/`, `TestResults/`, `dist/`, `target/`,
depending on language — and they
persist after the script exits. Make sure these are in the project's
`.gitignore` (and any linter's ignore file), since a stale artifact left
over from one push can otherwise make the *next* push's static stage
fail on files the hook itself created.

## Prerequisites

Each script assumes its language's linters/scanners/coverage tools are
**already installed** — it does not install them on every push (that
would make every push slow and mutate your environment silently). Install
once per machine:

| Language | Install once |
|---|---|
| Java | Semgrep CLI, `pip install diff-cover` |
| Python | `pip install ruff mypy bandit build diff-cover` |
| .NET | `dotnet tool install -g dotnet-reportgenerator-globaltool`, `pip install diff-cover` |
| Go | `go install github.com/securego/gosec/v2/cmd/gosec@latest`, `go install golang.org/x/vuln/cmd/govulncheck@latest`, `go install github.com/AlekSi/gocov-xml@latest`, `go install github.com/axw/gocov/gocov@latest`, `pip install diff-cover`, golangci-lint (see its own install docs) |
| Node.js | `npm install` (uses `npx`, no separate global install), `pip install diff-cover` |
| Bun | `bun install --frozen-lockfile`, `pip install lcov_cobertura`, `pip install diff-cover` |
| Rust | `cargo install cargo-nextest cargo-llvm-cov cargo-audit cargo-deny --locked`, `rustup component add llvm-tools-preview`, `pip install diff-cover` |

## Autofix tier

An opt-in step, Java only so far, that *fixes* what the static gate
*verifies*. It is kept apart from the gates because the two have opposite
properties: a gate is read-only and reproducible; a fixer rewrites code.

Rules that keep it from becoming a loophole:

- **Fixing is local; CI only verifies.** CI runs `spotless:check`,
  `checkstyle:check` and `pmd:check` and never applies anything — a
  pipeline that rewrites code after review means what merges is not what
  was reviewed. The pre-push hook also only verifies: a hook that edits the
  working tree mid-push would push the unfixed commits.
- **A fix is not trusted until the gates pass on it.** `autofix.sh` never
  stages or commits, prints the diff for review, re-runs the CI static
  commands to list whatever it could not fix, and re-runs unit tests when
  OpenRewrite ran (it changes code, a formatter only changes layout).
- **The config sits behind the existing guardrails.** The Spotless
  version pins and the OpenRewrite recipe list live in `pom.xml`, which is
  already `CODEOWNERS`-protected and `ask` in the agent permission scope;
  the `-Dspotless.skip`, `-Dcheckstyle.skip` and `-Dpmd.skip` flags are
  denied there, so an agent cannot go green by switching a check off.

What it can and cannot fix:

| Finding | Fixed by | Autofix? |
|---|---|---|
| Formatting, import order, unused imports (Checkstyle `google_checks.xml`) | Spotless + google-java-format | Yes |
| Unused locals / private fields / private methods, missing `@Override`, final utility classes, literals-first comparisons (PMD) | OpenRewrite recipes in the pom's `autofix` profile | Yes, mechanical cases only |
| Any other PMD rule (most design and error-prone rules) | — | No: fix by hand or with an agent, then the gates verify it |

The shipped PMD rulesets are `bestpractices`, `errorprone` and `design`, not
`codestyle`, so Spotless mostly clears **Checkstyle** findings here, not PMD
ones. If you add PMD's codestyle category, run the tools and confirm they
agree rather than assuming the formatter satisfies it.

Install once per project, next to the pre-push hook:

```bash
cp adv-framework/assets/java/autofix.sh .githooks/autofix.sh
chmod +x .githooks/autofix.sh
sh .githooks/autofix.sh
```

It refuses to run on a dirty tree so the autofix diff can be reviewed on its
own (`ADV_AUTOFIX_ALLOW_DIRTY=1` overrides). `ADV_AUTOFIX_REWRITE=0` runs
Spotless only.

## Installing the hook

A runnable example with the hook already wired up lives at
`examples/python/`, relative to this bundle's root — try it there first
if you want to see the hook work before setting one up in your own
project.

```bash
mkdir -p .githooks
cp adv-framework/assets/<lang>/pre-push.sh .githooks/pre-push
chmod +x .githooks/pre-push
git config core.hooksPath .githooks
```

`core.hooksPath` is a **per-clone local git config** — it isn't set
automatically by `git clone`, so every developer runs this once. It also
**overrides** any hooks already configured via `core.hooksPath` in that
repo (e.g. Husky) — check for an existing `core.hooksPath` before running
this on a project that already has one.

## Default branch detection

The diff-coverage step needs to know your default branch, which — unlike
CI's `$CI_DEFAULT_BRANCH` — isn't available for free locally. Each script
resolves it via `ADV_DEFAULT_BRANCH` if set, falling back to parsing
`git remote show origin`. That fallback is a network call whose output
format isn't guaranteed stable across git/hosting versions — if it proves
flaky in your environment, set `ADV_DEFAULT_BRANCH` explicitly (e.g. in
your shell profile) rather than relying on the fallback:

```bash
export ADV_DEFAULT_BRANCH=main
```

## Keeping scripts in sync with CI

Each script's commands are copied verbatim from its `gitlab-ci-*-adv.yml`
at the time it was written, with a `KEEP IN SYNC` comment at the top as
the only enforcement mechanism — there's no shared source of truth
between the two files (a deliberate tradeoff: this framework favors
plain, standalone files over a shared abstraction layer). When you change
a job's `script:` in the CI yml, update the matching line in
`pre-push.sh` in the same commit.
