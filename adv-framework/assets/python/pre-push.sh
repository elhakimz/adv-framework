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
