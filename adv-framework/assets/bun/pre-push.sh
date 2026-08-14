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
