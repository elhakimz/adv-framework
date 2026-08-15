# Python example — local pre-push hook demo

A minimal, runnable calculator project for trying the ADV framework's
[local pre-push verification hook](../../references/local-verification.md)
without setting anything up yourself.

## Setup

From this directory:

```bash
pip install -e ".[dev]"
```

If your shell's default `python`/`pip` aren't the toolchain you want (e.g.
multiple Python installs on PATH), make sure the interpreter whose `pip`
you used above is also the one whose `Scripts`/`bin` directory is on PATH
when you run the hook below — it calls `ruff`, `mypy`, `pytest`, etc. by
bare name.

## Run the hook

No copying needed — the hook script's commands operate on your current
directory, not on where the script file itself lives:

```bash
sh ../../assets/python/pre-push.sh
```

If default-branch resolution fails (e.g. no network access to parse
`git remote show origin`), set `export ADV_DEFAULT_BRANCH=main` first.

## What you'll see the first time

The **static** stage fails on exactly one check:

```
── static ──
  ✗ ruff format --check .
❌ static failed
```

`ruff check .`, `mypy src/ --strict`, and `bandit -r src/ -q` all pass —
only formatting is broken. This project ships with `src/calculator/__init__.py`
containing one single-quoted string where `ruff format` wants double quotes,
specifically so you see the hook's collect-all-failures reporting do
something real on the very first run.

## Fix it and re-run

```bash
ruff format .
sh ../../assets/python/pre-push.sh
```

This time static, build, unit, and property should all pass.

## A note on the diff-coverage check

The hook's Unit stage includes a diff-coverage gate that compares your
changes against `origin/<default-branch>` — but this example lives inside
the ADV framework's own git repository. Right after this project is merged,
there's no diff on these files yet, so diff-coverage will trivially pass
with nothing to check. That's expected, not a sign the gate is broken —
edit a file locally (like the fix above) to see it evaluate a real diff.

## What's not exercised here

This example only has unit and property tests. The pre-push hook's
Contract, Regression, and Deploy Gate stages aren't run locally at all
(by design — see the reference doc linked above), so there's no
regression test in this project either.
