# Bundle Self-Check — Design

**Status**: Draft, pending review
**Date**: 2026-08-16

## Motivation

Two defects reached `main` in the gate-integrity change and were caught only by a whole-branch LLM review, not by any deterministic check:

1. `references/gate-structure.md` pointed at `the README's "Guarding against agent-specific failure modes"`. `README.md` lives at the repo root and is **not** installed with the skill (`cp -r adv-framework ~/.claude/skills/adv-framework`), so every installation would have received a pointer it could not resolve. The section title was also wrong by one word — the bundle's own equivalent section is titled "Guard**rails**", not "Guard**ing**".
2. `SKILL.md`'s enumeration of `gate-structure.md`'s contents went stale when two sections were added. Because `SKILL.md` is the routing layer that decides whether an agent opens a reference file at all, both new sections became unreachable via the intended path.

Neither was visible to a per-file review: each file was internally correct, and the defect lived in the relationship between files — one at the bundle boundary, one between a manifest and the thing it indexes.

ADV's own ratchet rule prescribes the response:

> When something escapes to production despite a green pipeline, the fix is never just patching the bug — it's adding the deterministic gate that would have caught it. The verification suite only grows.

The repo currently has **no automated verification of itself at all**. Every check in the work that produced these defects was a human or an LLM reading files — which is precisely the anti-pattern the framework exists to name.

## Scope and honest framing

This ships as a script plus a **pre-push hook**, not a CI gate. That is a deliberate choice for a repo with no existing CI, but it must be described accurately: `references/local-verification.md` opens by insisting a pre-push hook is a fast-feedback convenience and that CI plus `CODEOWNERS` are the only things that actually gate a merge. This self-check is therefore **advisory** by the framework's own definition. Documentation must not call it a gate. Wiring it into CI later is the step that would make it one, and the design keeps that path open by putting all logic in a standalone script the hook merely invokes.

**In scope**: the published product — `adv-framework/**/*.md`, plus root `README.md` and `PROMPTING_GUIDE.md`.

**Out of scope**: `docs/**`. Specs and plans legitimately reference files that do not exist yet — a plan's whole job is to describe files to be created — so including them would guarantee false positives.

## Location

`scripts/check-bundle-integrity.py` and `scripts/heading-manifest.json`, at the repo root — deliberately **not** inside `adv-framework/`. The bundle is what ships to every user's skills directory; this tooling verifies *this repo's* copy of it and has no purpose in an installed skill.

**Language**: Python 3.10, standard library only (`pathlib`, `re`, `hashlib`, `json`, `sys`, `argparse`). Matches the one existing Python asset in the repo and requires no install step. Note the machine's `python` on PATH is a pip-less MSYS2 build; the working interpreter is `C:\Users\HP\AppData\Local\Programs\Python\Python310\python.exe`. Stdlib-only means the checker runs under either.

## The load-bearing rule: resolution base depends on the containing file

This is the rule that catches defect 1, and it is the design's core idea.

- A reference inside `adv-framework/**` **must resolve inside `adv-framework/`** — the bundle ships alone, so a reference that only resolves from the repo root is broken for every installation. Bases tried: the containing file's directory, then the bundle root. The repo root is deliberately **not** an accepted base for bundle files.
- A reference inside root `README.md` or `PROMPTING_GUIDE.md` resolves from the **repo root**. These are repo-level documents and may legitimately reference anything in the repo.

## Check 1 — Path references (Static-gate-shaped)

A backticked string counts as a path reference **only if it contains a `/`** and ends in one of the extensions actually used in this repo: `.md`, `.yml`, `.yaml`, `.toml`, `.json`, `.sh`, `.py`, `.xml`, `.ts`, `.js`, `.go`, `.rs`, `.cs`, `.props`. A trailing-slash directory reference (e.g. `tests/unit/`) also counts, and must resolve to an existing directory.

This single rule is derived from the actual reference data in the bundle, not invented. Surveying every backticked file-like token showed two distinct populations:

- **With a slash** — `assets/golang/pre-push.sh`, `references/kanban-integration.md`, `src/calculator/__init__.py`. These state where something lives. Checkable.
- **Without a slash** — `pre-push.sh`, `vitest.config.ts`, `coverage.xml`, `mypy`, `cargo-mutants`, `.gitlab-ci.yml`. These are *mentions*: a tool name, a generated artifact, or — in `.gitlab-ci.yml`'s case — a file the reader creates in their own repo. Checking these would produce false positives on every one.

Placeholder expansion: `<lang>` expands across the seven language directories (`java`, `python`, `dotnet`, `golang`, `nodejs`, `bun`, `rust`), and **all seven** must exist. So `assets/<lang>/pre-push.sh` verifies seven files rather than being skipped — a strictly stronger check than treating the placeholder as unresolvable.

## Check 2 — Documentary references to other docs

Catches defect 1's exact shape. Two forms, both scoped by the resolution rule above:

- **Quoted section form**: `<doc>'s "<Section Title>"` — the named doc must exist (per the resolution rule) *and* contain a heading whose text matches the quoted title exactly. This is what catches `"Guarding"` vs the actual `"Guardrails"`.
- **Bare doc-name form**: the doc token may appear as `SKILL.md`, `gate-structure.md`, or bare `README` (the original defect wrote "the README's", with no extension), so the pattern must accept an optional `.md` and the bare word `README`.

There is exactly **one** such reference in the bundle today — the one already fixed. That is not a reason to skip the check; it is the check that would have prevented the defect, and its subject count will grow.

## Check 3 — Manifest freshness tripwire (Regression-gate-shaped)

`SKILL.md`'s reference-file bullets describe each reference doc's contents in prose. That prose deliberately does not string-match the headings it describes: "the full 7-gate table" describes a section titled "The 7 gates, in order"; "incremental adoption order" describes "Adopting incrementally". Fuzzy matching across that gap would produce both false positives and false negatives, and `references/security.md` already warns that a check which cries wolf trains people to ignore it.

So the check does not judge the prose. It records, in `scripts/heading-manifest.json`, a hash of each reference file's **ordered list of headings at both `##` and `###` level**. Both levels matter: SKILL.md's bullet for `gate-structure.md` names "complexity budget, suite health, real execution", which are `###` subsections under a single `##` parent — a `##`-only hash would miss a new or renamed subsection that the bullet's parenthetical should have mentioned. On mismatch it fails with the specific file and an actionable message:

> `references/gate-structure.md`'s headings changed since SKILL.md's manifest was last verified. Re-read SKILL.md's bullet for this file, update it if the change should be reflected there, then re-record with `--update`.

This is a tripwire, not a validator: it makes no claim about whether the prose is correct, only that the thing the prose describes has changed and a human should look. Zero false positives by construction.

A `--update` flag re-records the hashes deliberately. This mirrors how ADV already treats snapshot updates throughout the framework — a human decision made after confirming intent, never something automated. The hook must never pass `--update`.

Structurally, Check 3 is a golden-file check (ADV's Regression gate, #6) and Check 1 is a static analysis (Static gate, #1), applied to the framework by the framework.

## Component 2 — the pre-push hook

`.githooks/pre-push`, invoking the checker. Installed via `git config core.hooksPath .githooks` — reusing the exact mechanism `references/local-verification.md` already documents for the seven language hooks, rather than inventing a second convention for the same job.

## Testing

The checker gets its own tests. An untested checker that silently always exits 0 is worse than no checker: it manufactures false confidence, which is the failure mode ADV's newly-added anti-gaming rule 5 names directly ("never report a check that wasn't run"). A checker nobody has seen fail has not been shown to run at all.

Fixture-based, using temporary directories built per test:

| Fixture | Expectation |
|---|---|
| Clean bundle | exit 0, no findings |
| Bundle file referencing a path that exists only at repo root | exit non-zero, names the file and the unresolvable reference |
| Bundle file referencing a path that exists nowhere | exit non-zero |
| Quoted section title not present in the named doc | exit non-zero, names both |
| Quoted section title present and exact | exit 0 |
| `<lang>` placeholder where one of seven is missing | exit non-zero, names the missing language |
| Heading added to a reference file without re-recording | exit non-zero with the tripwire message |
| Heading list unchanged | exit 0 |
| `--update` after a heading change | exit 0, manifest file rewritten |

Run with `pytest`. The tests live in `scripts/test_check_bundle_integrity.py`.

Additionally, the checker must be run once against the **real current repo** and exit 0 — establishing the baseline honestly rather than shipping a check whose first real run is someone else's problem.

## Non-goals

- Not a CI gate, and not to be described as one — see "Scope and honest framing".
- Not a general-purpose markdown link checker. It checks the two defect classes that actually escaped, plus placeholder expansion. Broad link-checking would pull in external URLs, anchors, and image paths — scope creep with a worse false-positive profile.
- Not shipped inside `adv-framework/`. This is repo tooling; installing it into users' skill directories would be meaningless.
- Not checking `docs/**`, for the false-positive reason given in Scope.
- Not validating that SKILL.md's prose is *accurate* — only that it has been re-examined since the described file changed.
