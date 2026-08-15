#!/usr/bin/env sh
# pre-push.sh — Go
# Mirrors: gitlab-ci-golang-adv.yml stages 1 (Static), 2 (Build), 3 (Unit),
# 4 (Property). KEEP IN SYNC — if a job's script: changes in the CI yml,
# update it here too.
#
# NOT part of what's enforced. This is fast local feedback, not a gate —
# CI + CODEOWNERS are what actually gate a merge. See
# adv-framework/references/local-verification.md before wiring this up.
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
#
# Static stage's gosec drops CI's `-fmt=junit-xml -out=gosec-report.xml`
# flags — locally you want findings printed to the terminal, not only
# written to a junit XML file.
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
  "gosec ./..." \
  "govulncheck ./..."
[ "$fail" -eq 1 ] && exit 1

run_stage "build" \
  "go build ./..."
[ "$fail" -eq 1 ] && exit 1

DEFAULT_BRANCH="${ADV_DEFAULT_BRANCH:-$(git remote show origin | sed -n '/HEAD branch/s/.*: //p')}"
[ -n "$DEFAULT_BRANCH" ] || { echo "Could not resolve default branch; set ADV_DEFAULT_BRANCH" >&2; exit 1; }
git fetch -q origin "$DEFAULT_BRANCH"
run_stage "unit" \
  "go test ./... -race -coverprofile=coverage.out -covermode=atomic" \
  "gocov convert coverage.out | gocov-xml > coverage.xml" \
  "diff-cover coverage.xml --compare-branch=origin/$DEFAULT_BRANCH --fail-under=80"
[ "$fail" -eq 1 ] && exit 1

run_stage "property" \
  "go test -tags=property ./... -run TestProperty -v"

exit $fail
