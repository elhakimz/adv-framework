# Local Pre-Push Verification — Design

**Status**: Draft, pending review
**Date**: 2026-08-15

## Motivation

The ADV framework's seven gates today only run in CI. A developer (human or agent) discovers a static-lint or unit-test failure only after pushing and waiting for the pipeline — slow feedback for the cheapest, fastest gates, which is exactly backwards for the layer meant to catch the majority of issues (per `gate-structure.md`'s own incremental-adoption ordering: "static + build + unit... cheap, immediate payoff").

This adds an opt-in local pre-push hook, per language, that runs the same fast gates before the push leaves the machine — without changing what actually gates a merge.

## Non-negotiable framing

This asset **must not** read as "verification you can do locally instead of CI." The whole premise of ADV is that nothing merges on self-report, and a pre-push hook is trivially bypassed (`git push --no-verify`, or a dev who never ran the install step). `references/local-verification.md` opens with this explicitly, before any setup instructions:

> This hook is a fast-feedback convenience, not a gate. It catches problems before a push instead of after one. It is not part of what's enforced — the CI pipeline and `CODEOWNERS` remain the only things that actually gate a merge. Nothing about running this locally, or configuring it, weakens or replaces any CI stage.

Same framing gets one sentence in `SKILL.md`'s asset index and in `README.md`'s new section, so nobody encounters this feature without the caveat attached.

## Scope

**In**: Static (only the jobs that are real local CLI commands — see exclusion below), Build, Unit (incl. diff-coverage-gate), Property. These four need nothing but the language's own toolchain.

**Out**: Contract (needs a Postgres service container), Regression (slow / has the snapshot-update-is-a-human-decision rule that's easy to trip over in a hook), Deploy Gate (needs a real environment). These stay CI-only; the doc says so explicitly rather than silently omitting them.

**Excluded from Static specifically**: `sast`, `dependency_scanning`, `secret_detection` are empty stub jobs in every base pipeline — they resolve via GitLab-native template `include:`s, not a shell command. There is no local command to "mirror." The hook scripts skip these three outright, and the reference doc says why (rather than a dev wondering why their hook doesn't check secrets).

## Structure

One script per language, living next to that language's CI yml — not a new top-level folder, since a hook is inherently single-language per repo, unlike `guardrails/` or `security/` which are cross-cutting:

```
adv-framework/assets/
├── java/
│   ├── gitlab-ci-java-adv.yml
│   └── pre-push.sh          # NEW
├── python/
│   ├── gitlab-ci-python-adv.yml
│   └── pre-push.sh          # NEW
├── dotnet/  ... pre-push.sh
├── golang/  ... pre-push.sh
├── nodejs/  ... pre-push.sh
├── bun/     ... pre-push.sh
└── rust/    ... pre-push.sh
```

Plus one new reference doc, `adv-framework/references/local-verification.md`, covering the framing above, the install step (shared across all seven — see below), and the per-language exclusion notes.

## Script behavior

Each `pre-push.sh`:

1. Runs every command in a stage, **collecting failures rather than stopping at the first one** — this is the opposite of what I initially proposed, and matters because GitLab CI runs a stage's jobs in parallel, so a dev today sees every static failure in one pipeline run. A hook that stops at the first `eslint` failure and forces four separate push attempts to discover four separate problems is worse UX than what CI already gives them.
2. Only advances to the next **stage** once every job in the current stage passed (mirrors the actual pipeline's stage-gating — Property never runs if Unit is red).
3. Prints a per-stage summary (`✅ static (4/4)`, `❌ unit (1/2) — diff-coverage-gate failed`) so failures are scannable, not buried in raw tool output.
4. Exits non-zero on any failure, which blocks the push (standard git pre-push hook semantics) unless the dev passes `--no-verify`.

Concretely, for Python (fullest worked example — other six follow the same shape with their own stage's commands, taken verbatim from the matching `gitlab-ci-*-adv.yml`):

```bash
#!/usr/bin/env sh
# pre-push.sh — Python
# Mirrors: gitlab-ci-python-adv.yml stages 1,2,3,4 (Static/Build/Unit/Property)
# KEEP IN SYNC — if a job's script: changes in the CI yml, update it here too.
# sast/dependency_scanning/secret_detection are GitLab-template jobs with no
# local CLI equivalent — intentionally not mirrored here.
set -u
fail=0

run_stage() {
  stage_name="$1"; shift
  echo "── $stage_name ──"
  stage_fail=0
  for cmd in "$@"; do
    if ! eval "$cmd"; then
      echo "  ✗ $cmd"
      stage_fail=1
    fi
  done
  if [ "$stage_fail" -eq 1 ]; then
    echo "❌ $stage_name failed"
    fail=1
  else
    echo "✅ $stage_name"
  fi
}

run_stage "static" \
  "ruff check ." \
  "ruff format --check ." \
  "mypy src/ --strict" \
  "bandit -r src/ -q"
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "python -m build"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "pytest tests/ -m 'not property and not regression' --cov=src --cov-report=xml" \
  "diff-cover coverage.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "pytest tests/ -m property"

exit $fail
```

Key details this example fixes vs. my first pass in chat:

- **Default-branch detection**, not a hardcoded `main` — `ADV_DEFAULT_BRANCH` env var override, falling back to `git remote show origin` parsing. CI has `$CI_DEFAULT_BRANCH` for free; locally we don't, so this has to be resolved explicitly.
- **`diff-cover` and `bandit` etc. are assumed already installed locally** — the hook doesn't silently `pip install` things into the dev's environment on every push. If a command isn't found, the shell's own "command not found" surfaces, and `local-verification.md`'s prerequisites section lists what to install once (`pip install diff-cover bandit ruff mypy`, per language).
- **`sed`-based default-branch parsing** is a known-fragile pattern (depends on `git remote show`'s output format) — flagged as a risk below, not silently assumed robust.

The other six scripts follow this identical shape (`run_stage` harness reused verbatim across all seven — the framework's "keep in sync via comment, not shared abstraction" call from earlier still holds: each script is a standalone file, not a sourced library, so a language's script can diverge without touching the others), with per-language commands taken directly from that language's CI yml:

| Language | Static commands (minus sast/dep-scan/secret-detect stubs) | Build | Unit | Property |
|---|---|---|---|---|
| Java | `mvn checkstyle:check`, `mvn pmd:check`, `semgrep scan --config .semgrep/rules.yml --error` | `mvn compile` | `mvn test` + `mvn jacoco:report` + diff-cover | `mvn test -Pproperty-tests` (jqwik profile) |
| Python | `ruff check .`, `ruff format --check .`, `mypy src/ --strict`, `bandit -r src/` | `python -m build` | `pytest -m "not property and not regression"` + diff-cover | `pytest -m property` |
| .NET | `dotnet format --verify-no-changes`, `dotnet build -warnaserror` | `dotnet build --configuration Release` | `dotnet test` + reportgenerator + diff-cover | `dotnet test --filter Category=Property` |
| Go | `golangci-lint run`, `gofmt -l .`, `gosec ./...`, `govulncheck ./...` | `go build ./...` | `go test -race` + gocov + diff-cover | `go test -tags=property ./...` |
| Node.js | `eslint .`, `prettier --check .`, `tsc --noEmit`, `npm audit --audit-level=high` | `npm run build` | `vitest run --coverage` + diff-cover | `vitest run -c vitest.property.config.ts` |
| Bun | `biome check .`, `tsc --noEmit` | `bun build` | `bun test tests/unit` + diff-cover | `bun test tests/property` |
| Rust | `cargo fmt --check`, `cargo clippy`, `cargo audit`, `cargo deny check` | `cargo build --release` | `cargo llvm-cov --lib nextest` + diff-cover | `cargo nextest run --test property_tests` |

All seven rows above are taken verbatim from each language's `gitlab-ci-*-adv.yml` (Java: `mvn test -Pproperty-tests`; .NET: `dotnet test --filter "Category=Property"` — both confirmed against the actual yml, not inferred from the summary table in `gate-structure.md`).

## Install mechanism

One shared snippet in `local-verification.md`, not a separate script (a `git config` one-liner doesn't need its own file):

```bash
mkdir -p .githooks
cp adv-framework/assets/<lang>/pre-push.sh .githooks/pre-push
chmod +x .githooks/pre-push
git config core.hooksPath .githooks
```

Documented caveat: `core.hooksPath` is a per-clone local git config, not something that ships automatically on `git clone` — every developer runs this once. It also **overrides** any other hooks already configured via `core.hooksPath` in that repo, which the doc calls out as something to check for before blindly running the snippet on an existing project.

## Documentation touch points

- New: `adv-framework/references/local-verification.md` (framing, prerequisites per language, install snippet, exclusion rationale).
- `adv-framework/SKILL.md`: one line in the asset index pointing at the new reference doc and scripts, with the advisory-only caveat.
- `README.md`: one new section, same shape as the existing "Security" / "Guarding against agent-specific failure modes" sections, front-loaded with the non-negotiable framing paragraph.

## Testing / validation plan

No unit-testable logic in the traditional sense — this is shell scripts wrapping CLI tools. Validation is manual, per language, against the bundled example tests already in each `assets/<lang>/` folder:

1. Clean checkout of the example assets → hook passes end to end.
2. Deliberately break one file per stage (an unformatted file for static, a failing assertion for unit, a falsifiable property for property) → confirm the hook reports that specific stage as failed and does **not** run later stages.
3. Confirm a stage with multiple failing commands reports all of them, not just the first (validates the "collect, don't stop" behavior).
4. Confirm diff-coverage resolves a default branch correctly on a repo where `origin/HEAD` is unset (common on fresh clones/shallow clones) — this is the known-fragile point flagged above, so it needs an explicit manual check, not an assumption.

## Non-goals

- Not a substitute for CI — restated once more here for the plan/implementation phase, not just the docs.
- Not wired into `assets/guardrails/` — a hook is opt-in tooling, not a permission-scoping guardrail; conflating the two would blur what `CODEOWNERS`/`claude-code-settings.json` are actually for.
- Not extending to Contract/Regression/Deploy Gate locally, per the scope decision above.
- Not building a shared command-list abstraction (Makefile/etc.) between the CI yml and the hook script — duplication-with-a-sync-comment was the explicit choice made earlier in this design conversation, accepted as a real maintenance tradeoff rather than solved.

## Open risk carried into implementation

`git remote show origin` for default-branch detection is a network call and its output format isn't guaranteed stable across git/hosting versions. The `ADV_DEFAULT_BRANCH` env var override exists specifically so a team can sidestep this if it proves flaky — implementation should make sure that override path is documented as the primary recommended setup, not just a fallback nobody notices.
