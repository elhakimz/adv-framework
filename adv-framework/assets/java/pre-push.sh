#!/usr/bin/env sh
# pre-push.sh — Java
# Mirrors: gitlab-ci-java-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# adv-framework/references/local-verification.md before wiring this up.
#
# This hook only VERIFIES (spotless:check). It never rewrites files — a hook
# that edits the working tree during a push would push the unfixed commits.
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
  "mvn $MAVEN_CLI_OPTS spotless:check" \
  "mvn $MAVEN_CLI_OPTS checkstyle:check" \
  "mvn $MAVEN_CLI_OPTS pmd:check" \
  "semgrep scan --config .semgrep/rules.yml --error"
if [ "$fail" -eq 1 ]; then
  echo "Formatting / PMD findings? The opt-in autofix script can clear the mechanical ones:"
  echo "  sh .githooks/autofix.sh   (see references/local-verification.md, Autofix tier)"
  exit 1
fi

run_stage "build" \
  "mvn $MAVEN_CLI_OPTS compile"
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
[ -n "$DEFAULT_BRANCH" ] || { echo "Could not resolve default branch; set ADV_DEFAULT_BRANCH" >&2; exit 1; }
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "mvn $MAVEN_CLI_OPTS test" \
  "mvn jacoco:report" \
  "diff-cover target/site/jacoco/jacoco.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "mvn $MAVEN_CLI_OPTS test -Pproperty-tests"

exit $fail
