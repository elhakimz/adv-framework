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
