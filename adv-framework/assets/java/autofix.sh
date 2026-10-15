#!/usr/bin/env sh
# autofix.sh — Java (opt-in LOCAL autofix tier)
#
# NOT a gate and NOT part of what CI enforces. CI only ever runs
# spotless:check / checkstyle:check / pmd:check (verify, never modify). This
# script is where the mechanical fixes happen, on a developer's or agent's
# machine, before the result is committed and re-verified by the real gates.
# See adv-framework/references/local-verification.md, "Autofix tier".
#
# What it does, in order:
#   1. OpenRewrite (-Pautofix) — semantic PMD fixes (unused locals/fields/
#      private methods, missing @Override, ...). Skip with ADV_AUTOFIX_REWRITE=0.
#   2. Spotless apply (google-java-format) — formatting + unused imports.
#   3. Show the diff summary so a human can review it.
#   4. Re-run the same static commands CI runs, so whatever autofix could NOT
#      fix is listed instead of hidden.
#   5. Re-run unit tests if OpenRewrite ran — it changes behavior-bearing code,
#      a formatter does not.
# It never runs `git add` or `git commit`.
#
# Prerequisites: the autofix profile from pom-adv-fragment.xml in your pom.xml.
set -u

if [ "${ADV_AUTOFIX_ALLOW_DIRTY:-0}" != "1" ]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Uncommitted changes present. Commit or stash first so the autofix diff" >&2
    echo "can be reviewed on its own (override: ADV_AUTOFIX_ALLOW_DIRTY=1)." >&2
    exit 1
  fi
fi

rewrite="${ADV_AUTOFIX_REWRITE:-1}"

if [ "$rewrite" = "1" ]; then
  echo "── autofix: OpenRewrite ──"
  mvn --errors -Pautofix rewrite:run || { echo "✗ rewrite:run failed — stopping"; exit 1; }
fi

echo "── autofix: Spotless (google-java-format) ──"
mvn --errors spotless:apply || { echo "✗ spotless:apply failed — stopping"; exit 1; }

echo "── changes to review (not staged, not committed) ──"
git diff --stat

fail=0
echo "── re-verify: same commands as CI's static stage ──"
for cmd in \
  "mvn --errors --fail-at-end spotless:check" \
  "mvn --errors --fail-at-end checkstyle:check" \
  "mvn --errors --fail-at-end pmd:check"
do
  if ! eval "$cmd"; then
    echo "  ✗ $cmd"
    fail=1
  fi
done

if [ "$rewrite" = "1" ]; then
  echo "── re-verify: unit tests (OpenRewrite changed code, not just layout) ──"
  mvn --errors --fail-at-end test || { echo "  ✗ mvn test"; fail=1; }
fi

if [ "$fail" -eq 1 ]; then
  echo "❌ Violations remain that have no mechanical fix — fix them by hand, then re-run the gates."
  exit 1
fi
echo "✅ Clean. Review the diff above, commit it, and let CI verify."
