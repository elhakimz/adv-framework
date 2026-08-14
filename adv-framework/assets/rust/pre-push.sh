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
