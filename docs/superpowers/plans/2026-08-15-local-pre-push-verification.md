# Local Pre-Push Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, per-language pre-push git hook to the ADV framework skill that runs Static/Build/Unit(+diff-coverage)/Property locally before a push, as fast-feedback convenience — without becoming, or being read as, a substitute for the CI gates.

**Architecture:** Seven standalone POSIX-sh scripts (`assets/<lang>/pre-push.sh`), one per language, each embedding an identical `run_stage` harness (collects every failing command in a stage before reporting, only advances to the next stage if the current one is fully green) plus that language's own stage commands, copied verbatim from its `gitlab-ci-*-adv.yml`. A new reference doc explains setup and — first, prominently — that this hook enforces nothing; CI + CODEOWNERS remain the only real gate.

**Tech Stack:** POSIX `sh` (no bashisms — must run under `sh`, not just `bash`), the existing per-language toolchains already referenced by each CI pipeline (Maven, ruff/mypy/bandit, dotnet, go, npm/vitest, bun, cargo).

## Global Constraints

- Advisory-only framing must be the **opening paragraph** of `local-verification.md`, not a caveat buried later — restated in one sentence in the `SKILL.md` pointer and the `README.md` section too.
- Scripts collect **all** failing commands in a stage before reporting (not fail-fast on the first command) — mirrors CI running a stage's jobs in parallel.
- A script advances to the next stage **only if** the current stage had zero failures.
- `sast` / `dependency_scanning` / `secret_detection` are excluded from every script — they're empty GitLab-template-`include:` stubs in the CI ymls with no local CLI equivalent to mirror.
- Contract, Regression, and Deploy Gate are excluded entirely (need a DB service container / are slow or update-ambiguous / need a real environment).
- Default branch is resolved via `ADV_DEFAULT_BRANCH` env var, falling back to parsing `git remote show origin` — never hardcoded to `main`.
- Diff-coverage **is** included in the Unit stage (`git fetch origin "$DEFAULT_BRANCH"` first, then `diff-cover ... --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80`), matching every language's CI job.
- Every stage command is copied **verbatim** from that language's `gitlab-ci-*-adv.yml` — no invented flags. One-time tool-installation lines (`mvn install`-style `cargo install X --locked`, `go install .../x@latest`, `dotnet tool install -g ...`, `pip install diff-cover`) are **not** re-run on every push — they become one-line prerequisites in `local-verification.md` instead, and the script assumes the tool is already on `PATH`.
- Scripts live at `assets/<lang>/pre-push.sh`, next to that language's CI yml — not a new top-level folder.
- Every script's header comment says `KEEP IN SYNC — if a job's script: changes in the CI yml, update it here too.`

---

## Task 1: Validate the shared `run_stage` harness

This harness is pasted verbatim into all seven language scripts in Tasks 2–8, so its behavior must be verified once, standalone, before it's replicated seven times.

**Files:**
- None created — this task validates the harness logic interactively via the Bash tool, using throwaway fixtures. Nothing is committed by this task.

**Interfaces:**
- Produces: the validated `run_stage` function body (shown in Step 3below), consumed verbatim by Tasks 2–8. Contract: `run_stage "<stage-name>" "<cmd1>" ["<cmd2>" ...]` — runs each `<cmdN>` via `eval`, prints `  ✗ <cmd>` for every failing command, prints `✅ <stage-name>` if all commands passed or `❌ <stage-name> failed` otherwise, and sets the caller's `fail` variable to `1` if any command in the stage failed (never resets it to `0`, so an earlier stage's failure survives).

- [ ] **Step 1: Write the harness to a scratch file**

Write this exact content to `C:\Users\HP\AppData\Local\Temp\claude\C--Dev-adv-framework\13d10e1f-e843-4e2c-a070-ff56f16aef83\scratchpad\harness-test.sh`:

```sh
#!/usr/bin/env sh
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

echo "=== scenario 1: all pass ==="
fail=0
run_stage "static" "true" "true"
echo "fail=$fail (expect 0)"

echo "=== scenario 2: one of two fails ==="
fail=0
run_stage "static" "true" "false"
echo "fail=$fail (expect 1)"

echo "=== scenario 3: both fail (collect-all check) ==="
fail=0
run_stage "static" "false" "false"
echo "fail=$fail (expect 1)"

echo "=== scenario 4: stage-gating — later stage must not run after earlier failure ==="
fail=0
run_stage "static" "false"
[ "$fail" -eq 1 ] && echo "STOPPED before build (correct)" && exit 0
run_stage "build" "echo SHOULD_NOT_RUN"
```

- [ ] **Step 2: Run it and check the output**

Run: `sh "C:\Users\HP\AppData\Local\Temp\claude\C--Dev-adv-framework\13d10e1f-e843-4e2c-a070-ff56f16aef83\scratchpad\harness-test.sh"`

Expected output (in order):
```
=== scenario 1: all pass ===
── static ──
✅ static
fail=0 (expect 0)
=== scenario 2: one of two fails ===
── static ──
  ✗ false
❌ static failed
fail=1 (expect 1)
=== scenario 3: both fail (collect-all check) ===
── static ──
  ✗ false
  ✗ false
❌ static failed
fail=1 (expect 1)
=== scenario 4: stage-gating — later stage must not run after earlier failure ===
── static ──
  ✗ false
❌ static failed
STOPPED before build (correct)
```

Critically: `SHOULD_NOT_RUN` must **not** appear anywhere in the output — that's the stage-gating check. Both `✗ false` lines in scenario 3 confirm collect-all-failures (not stop-at-first-failure) works.

If any line doesn't match — especially if `SHOULD_NOT_RUN` prints, or scenario 3 only shows one `✗ false` — fix the harness function and re-run before proceeding. Do not move to Task 2 until this passes exactly as shown.

- [ ] **Step 3: Delete the scratch file**

Run: `rm "C:\Users\HP\AppData\Local\Temp\claude\C--Dev-adv-framework\13d10e1f-e843-4e2c-a070-ff56f16aef83\scratchpad\harness-test.sh"`

No commit for this task — nothing in the repo changed. The validated harness snippet from Step 1 is what gets pasted into every script in Tasks 2–8.

---

## Task 2: Python pre-push script

**Files:**
- Create: `adv-framework/assets/python/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/python/pre-push.sh`, referenced by Task 9's install snippet.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — Python
# Mirrors: gitlab-ci-python-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites (install once, not on every push):
#   pip install ruff mypy bandit build diff-cover
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
  "pytest tests/ -m \"not property and not regression\" --cov=src --cov-report=xml" \
  "diff-cover coverage.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "pytest tests/ -m property"

exit $fail
```

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/python/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real Python project)**

This script can't run end-to-end inside this repo — `adv-framework/assets/python/` only ships `pyproject-adv-fragment.toml` (a fragment to merge into a consuming project's own `pyproject.toml`), not a full runnable project. Document this as a one-time manual check before shipping: copy `pre-push.sh` into a real Python project that already has `src/`, `tests/`, and the prerequisites installed, run it once with everything passing (expect `exit $fail` → 0), then break one file per stage (e.g. an unformatted file, a failing assert, a falsifiable property test) one at a time and confirm each stage reports failure and later stages don't run. This is a real toolchain dependency this plan can't automate away — flag it to whoever merges this task if no such project is available to test against.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/python/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for Python

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-python-adv.yml. Advisory only — see the local-verification
reference doc (added in a later task) for the framing this depends on.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Node.js pre-push script

**Files:**
- Create: `adv-framework/assets/nodejs/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/nodejs/pre-push.sh`.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — Node.js
# Mirrors: gitlab-ci-nodejs-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites: `npm install` already run (node_modules present) — this
# script does not run `npm ci` on every push.
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
  "npx eslint . --max-warnings=0" \
  "npx prettier --check ." \
  "npx tsc --noEmit" \
  "npm audit --audit-level=high"
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "npm run build"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "npx vitest run --coverage --reporter=junit --outputFile=unit-report.xml" \
  "diff-cover coverage/cobertura-coverage.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "npx vitest run -c vitest.property.config.ts"

exit $fail
```

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/nodejs/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real Node.js project)**

`adv-framework/assets/nodejs/` has example test files and vitest configs but no `package.json` — not a runnable project as-is. Same caveat as Task 2 Step 3: verify against a real project once available, in the same all-pass → break-one-stage-at-a-time → confirm sequence.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/nodejs/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for Node.js

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-nodejs-adv.yml.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Bun pre-push script

**Files:**
- Create: `adv-framework/assets/bun/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/bun/pre-push.sh`.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — Bun
# Mirrors: gitlab-ci-bun-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites: `bun install --frozen-lockfile` already run, and
# lcov_cobertura installed for python3 (`pip install lcov_cobertura`) —
# this script does not install either on every push.
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
  "bunx biome ci ." \
  "bunx tsc --noEmit"
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "bun build ./src/index.ts --outdir ./dist --target=bun"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "bun test tests/unit --coverage --coverage-reporter=lcov --coverage-dir=coverage" \
  "python3 -c \"from lcov_cobertura import LcovCobertura; LcovCobertura(open('coverage/lcov.info').read()).convert().writexml or open('coverage/cobertura.xml','w').write(LcovCobertura(open('coverage/lcov.info').read()).convert())\"" \
  "diff-cover coverage/cobertura.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "bun test tests/property"

exit $fail
```

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/bun/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real Bun project)**

`adv-framework/assets/bun/` ships `tests/unit/`, `tests/property/`, `tests/regression/`, `biome.json`, `bunfig.toml` — no `package.json`/`src/index.ts`, not a runnable project as-is. Same caveat: verify against a real project once available.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/bun/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for Bun

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-bun-adv.yml, including the lcov-to-cobertura conversion step
CI uses so diff-cover can read Bun's native coverage output.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Rust pre-push script

**Files:**
- Create: `adv-framework/assets/rust/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/rust/pre-push.sh`.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — Rust
# Mirrors: gitlab-ci-rust-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites (install once, not on every push):
#   cargo install cargo-nextest cargo-llvm-cov cargo-audit cargo-deny --locked
#   rustup component add llvm-tools-preview
#   pip install diff-cover
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
  "cargo fmt --check" \
  "cargo clippy --all-targets --all-features -- -D warnings" \
  "cargo audit" \
  "cargo deny check"
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "cargo build --release"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "cargo llvm-cov --lib nextest --cobertura --output-path coverage.xml" \
  "diff-cover coverage.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "cargo nextest run --test property_tests"

exit $fail
```

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/rust/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real Rust project)**

`adv-framework/assets/rust/` ships `src/calculator.rs` and `tests/{property_tests.rs,regression_tests.rs}` but no `Cargo.toml` — not a runnable project as-is. Same caveat: verify against a real project once available.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/rust/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for Rust

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-rust-adv.yml.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Go pre-push script

**Files:**
- Create: `adv-framework/assets/golang/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/golang/pre-push.sh`.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — Go
# Mirrors: gitlab-ci-golang-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites (install once, not on every push):
#   go install github.com/securego/gosec/v2/cmd/gosec@latest
#   go install golang.org/x/vuln/cmd/govulncheck@latest
#   go install github.com/AlekSi/gocov-xml@latest
#   go install github.com/axw/gocov/gocov@latest
#   pip install diff-cover
#   golangci-lint on PATH (see https://golangci-lint.run/usage/install/)
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
  "golangci-lint run --timeout=5m ./..." \
  "test -z \"\$(gofmt -l .)\"" \
  "gosec -fmt=junit-xml -out=gosec-report.xml ./..." \
  "govulncheck ./..."
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "go build ./..."
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "go test ./... -race -coverprofile=coverage.out -covermode=atomic" \
  "gocov convert coverage.out | gocov-xml > coverage.xml" \
  "diff-cover coverage.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "go test -tags=property ./... -run TestProperty -v"

exit $fail
```

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/golang/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real Go project)**

`adv-framework/assets/golang/` ships example `_test.go` files and `.golangci.yml` but no `go.mod` — not a runnable project as-is. Same caveat: verify against a real project once available.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/golang/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for Go

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-golang-adv.yml.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: .NET pre-push script

**Files:**
- Create: `adv-framework/assets/dotnet/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/dotnet/pre-push.sh`.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — .NET
# Mirrors: gitlab-ci-dotnet-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites (install once, not on every push):
#   dotnet tool install -g dotnet-reportgenerator-globaltool
#   pip install diff-cover
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
  "dotnet format --verify-no-changes --severity warn" \
  "dotnet build --no-incremental -warnaserror" \
  "dotnet build --no-incremental -p:RunAnalyzersDuringBuild=true 2>&1 | tee security-scan.log && ! grep -q \"SCS[0-9]\" security-scan.log"
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "dotnet restore" \
  "dotnet build --configuration Release --no-restore"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "dotnet test --configuration Release --no-build --filter \"Category!=Property&Category!=Regression\" --collect:\"XPlat Code Coverage\" --results-directory ./TestResults" \
  "reportgenerator -reports:./TestResults/**/coverage.cobertura.xml -targetdir:./coverage-report -reporttypes:Cobertura" \
  "diff-cover coverage-report/Cobertura.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "dotnet test --configuration Release --no-build --filter \"Category=Property\""

exit $fail
```

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/dotnet/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real .NET project)**

`adv-framework/assets/dotnet/` ships `Directory.Build.props` and `ExampleTests.cs` but no `.csproj`/`.sln` — not a runnable project as-is. Same caveat: verify against a real project once available.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/dotnet/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for .NET

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-dotnet-adv.yml, including the reportgenerator conversion step
so diff-cover can read the coverage output.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Java pre-push script

**Files:**
- Create: `adv-framework/assets/java/pre-push.sh`

**Interfaces:**
- Consumes: the `run_stage` harness validated in Task 1.
- Produces: `adv-framework/assets/java/pre-push.sh`.

- [ ] **Step 1: Write the script**

```sh
#!/usr/bin/env sh
# pre-push.sh — Java
# Mirrors: gitlab-ci-java-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# references/local-verification.md before wiring this up.
#
# sast/dependency_scanning/secret_detection are GitLab-template jobs with
# no local CLI equivalent — intentionally not mirrored here.
#
# Prerequisites: Semgrep CLI on PATH, pip install diff-cover.
# --fail-at-end (no --batch-mode) is used instead of CI's full
# MAVEN_CLI_OPTS so local output stays readable in an interactive shell.
set -u
fail=0
MAVEN_CLI_OPTS="--errors --fail-at-end"

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
  "mvn $MAVEN_CLI_OPTS checkstyle:check" \
  "mvn $MAVEN_CLI_OPTS pmd:check" \
  "semgrep scan --config .semgrep/rules.yml --error"
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "mvn $MAVEN_CLI_OPTS compile"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "mvn $MAVEN_CLI_OPTS test" \
  "mvn jacoco:report" \
  "diff-cover target/site/jacoco/jacoco.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "mvn $MAVEN_CLI_OPTS test -Pproperty-tests"

exit $fail
```

Note: `MAVEN_CLI_OPTS` deliberately drops CI's `--batch-mode -DinstallAtEnd=true -DdeployAtEnd=true` — those exist for non-interactive CI output and multi-module install/deploy ordering, neither of which applies to a single local `mvn test` run. `--errors --fail-at-end` (surface every reactor failure, not just the first) is kept because it matters just as much locally as in CI, per this plan's collect-all-failures rule.

- [ ] **Step 2: Verify syntax**

Run: `sh -n adv-framework/assets/java/pre-push.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual smoke test (requires a real Java project)**

`adv-framework/assets/java/` ships `pom-adv-fragment.xml` (a fragment to merge into a consuming project's own `pom.xml`) — not a runnable project as-is. Same caveat: verify against a real project once available.

- [ ] **Step 4: Commit**

```bash
git add adv-framework/assets/java/pre-push.sh
git commit -m "$(cat <<'EOF'
Add local pre-push verification script for Java

Runs Static/Build/Unit+diff-coverage/Property locally, mirroring
gitlab-ci-java-adv.yml.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `references/local-verification.md`

**Files:**
- Create: `adv-framework/references/local-verification.md`

**Interfaces:**
- Consumes: the seven `pre-push.sh` files from Tasks 2–8 (referenced by path in the install snippet).
- Produces: a doc referenced by `SKILL.md` (Task 10) and `README.md` (Task 11).

- [ ] **Step 1: Write the doc**

```markdown
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
| Node.js | `npm install` (uses `npx`, no separate global install) |
| Bun | `bun install --frozen-lockfile`, `pip install lcov_cobertura` |
| Rust | `cargo install cargo-nextest cargo-llvm-cov cargo-audit cargo-deny --locked`, `rustup component add llvm-tools-preview`, `pip install diff-cover` |

## Installing the hook

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
```

- [ ] **Step 2: Commit**

```bash
git add adv-framework/references/local-verification.md
git commit -m "$(cat <<'EOF'
Add local-verification reference doc

Documents the pre-push scripts added in prior tasks: what they run, what
they intentionally don't, prerequisites per language, the install
snippet, and the advisory-only framing that keeps this from contradicting
ADV's core principle that only CI + CODEOWNERS gate a merge.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `SKILL.md` pointer

**Files:**
- Modify: `adv-framework/SKILL.md`

**Interfaces:**
- Consumes: `adv-framework/references/local-verification.md` (Task 9).

- [ ] **Step 1: Read the current asset-index section**

Run: `grep -n "When the user wants a working pipeline" -A 15 adv-framework/SKILL.md`

Confirm the table of bundled assets is still there in the shape seen during brainstorming (a row per language, plus `references/` bullets above it). Use the exact surrounding text you see as the anchor for Step 2's edit — the plan can't hardcode line numbers here since Tasks 1–9 haven't touched this file.

- [ ] **Step 2: Add a `references/` bullet and an asset-table row**

In the `references/` bullet list (the one already containing `gate-structure.md`, `security.md`, `kanban-integration.md`), add:

```markdown
- **`references/local-verification.md`** — the opt-in pre-push hook scripts (`assets/<lang>/pre-push.sh`), what they run locally vs. leave to CI, and the prerequisites per language. Read this when the user wants faster local feedback before pushing — and note explicitly that this is a convenience layer, not a merge gate; CI + CODEOWNERS remain what's actually enforced.
```

In the per-language asset table (the one listing CI pipeline / build-tool config / example tests), add a **Local hook** column with `pre-push.sh` for every language row.

- [ ] **Step 3: Commit**

```bash
git add adv-framework/SKILL.md
git commit -m "$(cat <<'EOF'
Point SKILL.md at the new local-verification reference and pre-push assets

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `README.md` section

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `adv-framework/references/local-verification.md` (Task 9).

- [ ] **Step 1: Add a new section**

Insert a new `## Running gates locally before push` section, in the same style as the existing `## Security` and `## Guarding against agent-specific failure modes` sections (front-load the framing paragraph, same as those two do), placed after `## Guarding against agent-specific failure modes` and before `## Adopting incrementally`:

```markdown
## Running gates locally before push

This is a fast-feedback convenience, not a gate — it catches problems
before a push instead of after one. It doesn't change what's enforced:
the CI pipeline and `CODEOWNERS` remain the only things that actually
gate a merge, and `git push --no-verify` skips it entirely.

Each language ships an opt-in pre-push hook (`assets/<lang>/pre-push.sh`)
that runs Static, Build, Unit (with diff-coverage), and Property locally
— the four gates that need nothing but your own toolchain. Contract,
Regression, and Deploy Gate stay CI-only. See
`adv-framework/references/local-verification.md` for prerequisites,
the install step, and why three of the CI's static jobs (`sast`,
`dependency_scanning`, `secret_detection`) aren't mirrored locally.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Document local pre-push verification in README

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Plan self-review notes

- **Spec coverage**: every section of the design doc maps to a task — framing (Task 9 opening + Tasks 2–8 headers + Task 11), scope/exclusions (Global Constraints + every script's comment header), structure (`assets/<lang>/pre-push.sh`, Tasks 2–8), script behavior (Task 1's validated harness), install mechanism (Task 9), documentation touch points (Tasks 9–11), testing/validation plan (Task 1 automates the harness; Tasks 2–8 Step 3 carries forward the manual per-language checklist since no language folder ships a full runnable project), open risk (default-branch detection — called out in Task 9's doc with the `ADV_DEFAULT_BRANCH` escape hatch).
- **Placeholder scan**: no TBD/TODO; every step has complete, runnable code or an exact command with expected output.
- **Type/interface consistency**: `run_stage "<name>" "<cmd>"...` signature is identical across Task 1's validation and all seven scripts in Tasks 2–8. `ADV_DEFAULT_BRANCH` / `DEFAULT_BRANCH` naming is consistent across every script and the reference doc.
