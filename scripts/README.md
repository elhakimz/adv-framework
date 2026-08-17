# Repo self-check

Deterministic checks over the `adv-framework/` bundle. This is repo
tooling — it is deliberately **not** inside `adv-framework/`, because
that directory is what ships to users' skill directories.

**This is advisory, not a gate.** It runs from a pre-push hook, and
`adv-framework/references/local-verification.md` is emphatic that such
hooks enforce nothing: they are bypassable with `--no-verify` and absent
until someone runs the install step. Wiring this into CI is what would
make it a gate.

## Run it

```bash
python scripts/check-bundle-integrity.py
```

Exit codes: **0** all checks ran and passed · **1** findings · **2** all
runnable checks passed but at least one was skipped.

## Install the hook

```bash
git config core.hooksPath .githooks
```

Per-clone local config, so every contributor runs it once. It overrides
any existing `core.hooksPath` — check for one first.

## Checks

| Check | What it catches |
|---|---|
| `path-refs` | A backticked path that does not resolve. Inside the bundle, references must resolve *within the bundle* — one that only resolves from the repo root is broken for every installation. |
| `doc-refs` | `<doc>'s "Section"` where the doc or the heading does not exist. |
| `manifest` | A reference doc's headings changed since SKILL.md's bullet describing it was last verified. |
| `shellcheck` | Shell bugs in the seven shipped hooks, plus committed CRLF (which breaks the shebang on Linux/macOS). |
| `ci-structure` | A CI job using an undeclared stage, or a `needs` pointing at no job. |

All checks read **committed bytes**, never the working tree: on Windows
the tree holds CRLF while the index holds LF, so linting the tree would
report carriage-return errors that do not exist in what ships.

## Working on a fix? Commit before you re-check

Because every check reads committed bytes, a fix that only exists in
your working tree is invisible to the checker — running it again after
editing a file will still report the original finding until you commit
the edit. That's the right behavior for the pre-push hook itself (you're
pushing commits, so committed content is exactly what should be judged),
but it can be surprising when you're iterating on a fix ad hoc and expect
each save to be picked up immediately. If you want to check something
other than `HEAD` — a work-in-progress commit, a branch, a tag — `--rev`
accepts any revision.

## Updating the heading manifest

When you intentionally add or rename a section in a reference doc,
re-read SKILL.md's bullet for that file, update it if needed, then:

```bash
python scripts/check-bundle-integrity.py --update
```

Never automate this, and never let the hook pass `--update` — accepting a
changed baseline is a human decision, the same rule this framework
applies to snapshot updates everywhere else.

`check_manifest` reads the manifest from **committed bytes**, same as
every other input. Commit the regenerated `scripts/heading-manifest.json`
before you push — an uncommitted `--update` result is invisible to the
checker and to the pre-push hook, so a stale committed manifest would
otherwise slip through.

## Dependencies

`pip install pyyaml shellcheck-py`. Missing tools are reported as
`SKIPPED` and produce exit 2 — never a silent pass.

## What a green run does not mean

Six of the seven `pre-push.sh` scripts have never been *executed*, and no
CI pipeline has ever run on a real GitLab runner. shellcheck proves the
absence of a class of shell bugs; it does not prove `mvn`, `cargo`, or
`bun` behave as the scripts assume. Green here means structurally sound
and internally consistent — bounded, auditable confidence, not proof.
