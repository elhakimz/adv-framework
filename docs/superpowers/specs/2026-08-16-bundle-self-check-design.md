# Bundle Self-Check — Design

**Status**: Draft, pending review
**Date**: 2026-08-16

## Motivation

Two defects reached `main` in the gate-integrity change and were caught only by a whole-branch LLM review, not by any deterministic check:

1. `references/gate-structure.md` pointed at `the README's "Guarding against agent-specific failure modes"`. `README.md` lives at the repo root and is **not** installed with the skill (`cp -r adv-framework ~/.claude/skills/adv-framework`), so every installation would have received a pointer it could not resolve. The section title was also wrong by one word — the bundle's own section is titled "Guard**rails**", not "Guard**ing**".
2. `SKILL.md`'s enumeration of `gate-structure.md`'s contents went stale when two sections were added. Because `SKILL.md` is the routing layer deciding whether an agent opens a reference file at all, both new sections became unreachable via the intended path.

Neither was visible to a per-file review: each file was internally correct, and the defect lived in the relationship *between* files.

ADV's own ratchet rule prescribes the response:

> When something escapes to production despite a green pipeline, the fix is never just patching the bug — it's adding the deterministic gate that would have caught it. The verification suite only grows.

The repo has **no automated verification of itself**. Every check in the work that produced these defects was a human or an LLM reading files — the precise anti-pattern the framework exists to name.

## What this covers, and why it is wider than documentation

An initial draft of this spec covered only documentation cross-references. That addressed the smallest gap. A survey of what is actually *proven* about this repo found:

| Artifact | Evidence before this work | Verdict |
|---|---|---|
| Python example project | Real end-to-end run: fail → fix → pass | Proven |
| 7 GitLab CI pipelines | None — never parsed, never run | Unverified |
| 7 `pre-push.sh` scripts | `sh -n` (parse only) | Weakly verified |
| All docs and references | LLM review | Unverified by the framework's own standard |

`sh -n` proves a script *parses*. It cannot catch unquoted expansions, wrong test operators, or unreachable code — the bug classes most likely to lurk in seven hand-written scripts, six of which have never been executed. So this self-check covers three artifact classes, not one.

## Baseline established during design (2026-08-16)

Every check below was run manually against the current repo before being specified, so the spec asserts nothing unproven and the implementation has a known-good baseline:

- **CI YAML parse**: all 7 pipelines + `security-debt-ci-job.yml` parse cleanly. *(First time this has ever been verified; an earlier claim in this repo's history that YAML edits were "safe by construction" was reasoning, not evidence.)*
- **CI structural invariants**: 0 issues. Every job's `stage` is declared in `stages`; every `needs` target resolves to a job in the same file. The 21 script-less jobs are the intended `sast`/`dependency_scanning`/`secret_detection` GitLab-template stubs.
- **shellcheck on all 7 `pre-push.sh`**: 0 findings, exit 0, against committed bytes.

So these checks are **preventive, not corrective** — they found no existing bugs, and the spec must not imply otherwise. Their value is keeping these properties true as the files change.

## The committed-bytes rule (learned the hard way during design)

Running shellcheck against the working tree reported `SC1017: Literal carriage return` on all seven scripts — which, taken at face value, means a CRLF shebang and `bad interpreter: No such file or directory` for every Linux and macOS user.

It was a false positive. `git ls-files --eol` shows `i/lf w/crlf`: the **committed** content is LF, and the CRLF exists only in this Windows working tree because `core.autocrlf=true` converts on checkout. Re-running against `git show HEAD:<path>` output produced zero findings.

**Therefore: every content check operates on committed bytes (`git show`/`git cat-file`), never on the working-tree file.** A checker that lints the working tree would fail on every Windows clone, and a check that cries wolf gets ignored — a failure mode `references/security.md` already warns about.

## Companion fix: `.gitattributes` (a real gap this surfaced)

The repo has **no `.gitattributes`**. The LF-in-index property that makes the shipped hooks executable on Unix is therefore an accident of one contributor's `core.autocrlf=true`, not an enforced invariant. A contributor with different git config who edits a `.sh` file could commit CRLF, and every Unix user's hook would break at the shebang.

This design adds `.gitattributes` at the repo root enforcing `*.sh text eol=lf` (and `eol=lf` for the other shipped text assets), converting an accidental property into a guaranteed one. This is a genuine latent-defect fix, not incidental tidying, and it is cheaper and more reliable than any check that merely detects the problem after the fact.

## Scope and honest framing

This ships as a script plus a **pre-push hook**, not a CI gate. That is a deliberate choice for a repo with no CI, but must be described accurately: `references/local-verification.md` opens by insisting a pre-push hook is a fast-feedback convenience, and that CI plus `CODEOWNERS` are the only things that actually gate a merge. This self-check is therefore **advisory** by the framework's own definition. Documentation must not call it a gate. All logic lives in a standalone script the hook merely invokes, keeping the path to a real CI gate open.

**In scope for doc checks**: `adv-framework/**/*.md`, plus root `README.md` and `PROMPTING_GUIDE.md`.

**Out of scope**: `docs/**`. Specs and plans legitimately reference files that do not exist yet — describing files to be created is a plan's whole job — so including them would guarantee false positives.

## Location and dependencies

`scripts/check-bundle-integrity.py` and `scripts/heading-manifest.json`, at the repo root — deliberately **not** inside `adv-framework/`. The bundle ships to users' skill directories; this tooling verifies *this repo's* copy and has no purpose in an installed skill.

**Language**: Python 3.10.

**Dependencies and their absence**: the doc checks (1–3) are stdlib-only. Check 4 needs `shellcheck`, check 5 needs `PyYAML`. Neither may be silently skipped — anti-gaming rule 5 ("never report a check that wasn't run") applies to this checker itself. When a tool is missing the script prints an unmistakable `SKIPPED (tool not installed)` line for that check, includes it in a summary of skipped checks, and still exits non-zero if any *runnable* check failed. A run with skips must never be reportable as a clean pass.

Install notes, verified on this machine: `pip install shellcheck-py pyyaml`. This machine's Avast TLS interception breaks PyPI access, requiring `--cert "C:\ProgramData\AVAST Software\Avast\wscert.pem"`; note it in the script's docstring so the next person does not re-derive it. Also note the working interpreter is `C:\Users\HP\AppData\Local\Programs\Python\Python310\python.exe` — the `python` on PATH is a pip-less MSYS2 build.

## The load-bearing rule for doc checks: resolution base depends on the containing file

This is what catches defect 1.

- A reference inside `adv-framework/**` **must resolve inside `adv-framework/`** — the bundle ships alone, so a reference resolving only from the repo root is broken for every installation. Bases tried: the containing file's directory, then the bundle root. The repo root is deliberately **not** accepted for bundle files.
- A reference inside root `README.md` or `PROMPTING_GUIDE.md` resolves from the **repo root**. These are repo-level documents and may reference anything in the repo.

## Check 1 — Path references (Static-gate-shaped)

A backticked string counts as a path reference **only if it contains a `/`** and ends in one of the extensions used in this repo: `.md`, `.yml`, `.yaml`, `.toml`, `.json`, `.sh`, `.py`, `.xml`, `.ts`, `.js`, `.go`, `.rs`, `.cs`, `.props`. A trailing-slash directory reference (e.g. `tests/unit/`) also counts and must resolve to a directory.

The slash rule is derived from the bundle's actual reference data, not invented. Surveying every backticked file-like token showed two populations:

- **With a slash** — `assets/golang/pre-push.sh`, `references/kanban-integration.md`, `src/calculator/__init__.py`. These state where something lives. Checkable.
- **Without a slash** — `pre-push.sh`, `vitest.config.ts`, `coverage.xml`, `mypy`, `cargo-mutants`, `.gitlab-ci.yml`. These are *mentions*: a tool name, a generated artifact, or — for `.gitlab-ci.yml` — a file the reader creates in their own repo. Checking these would false-positive on every one.

`<lang>` expands across the seven language directories (`java`, `python`, `dotnet`, `golang`, `nodejs`, `bun`, `rust`) and **all seven must exist**, so `assets/<lang>/pre-push.sh` verifies seven files rather than being skipped.

## Check 2 — Documentary references to other docs

Catches defect 1's exact shape. Two forms, both scoped by the resolution rule:

- **Quoted section form**: `<doc>'s "<Section Title>"` — the named doc must exist *and* contain a heading matching the quoted title exactly. This is what catches `"Guarding"` vs the actual `"Guardrails"`.
- **Bare doc-name form**: the token may appear as `SKILL.md`, `gate-structure.md`, or bare `README` (the original defect wrote "the README's", no extension), so the pattern accepts an optional `.md` and the bare word `README`.

Exactly **one** such reference exists in the bundle today — the one already fixed. That is not a reason to skip the check; it is the check that would have prevented the defect.

## Check 3 — Manifest freshness tripwire (Regression-gate-shaped)

`SKILL.md`'s reference-file bullets describe each doc's contents in prose that deliberately does not string-match the headings: "the full 7-gate table" describes a section titled "The 7 gates, in order"; "incremental adoption order" describes "Adopting incrementally". Fuzzy matching across that gap produces both false positives and false negatives.

So the check does not judge the prose. It records in `scripts/heading-manifest.json` a hash of each reference file's **ordered list of headings at both `##` and `###` level**. Both levels matter: SKILL.md's bullet names "complexity budget, suite health, real execution", which are `###` subsections under one `##` parent — a `##`-only hash would miss a new or renamed subsection the bullet should mention.

On mismatch it fails with an actionable message:

> `references/gate-structure.md`'s headings changed since SKILL.md's manifest was last verified. Re-read SKILL.md's bullet for this file, update it if the change should be reflected, then re-record with `--update`.

A tripwire, not a validator: it claims nothing about whether the prose is correct, only that what the prose describes has changed and a human should look. Zero false positives by construction. `--update` re-records deliberately, mirroring how ADV treats snapshot updates throughout — a human decision, never automated. The hook must never pass `--update`.

## Check 4 — shellcheck on the shipped hooks

Run `shellcheck -s sh` against the committed bytes of all seven `assets/<lang>/pre-push.sh`. Baseline is clean (verified above), so any finding is a regression introduced by a change.

`-s sh` (POSIX) rather than bash, matching the scripts' `#!/usr/bin/env sh` shebang and the portability the framework claims for them.

## Check 5 — GitLab CI structural validation

For each `assets/*/gitlab-ci-*-adv.yml`, parse and assert:

- Every job's `stage` value is declared in the file's `stages` list.
- Every `needs` entry resolves to a job defined in the same file.

Jobs with no `script`/`extends`/`trigger` are reported informationally, not as failures — `sast`, `dependency_scanning`, and `secret_detection` are intentionally body-less, supplied by the GitLab templates the file `include`s. Baseline: 0 issues, 21 informational.

This is not full GitLab CI schema validation; that needs GitLab's own CI Lint API and a project token. These two invariants are the ones a local edit realistically breaks.

## Testing

The checker gets its own tests. An untested checker that silently exits 0 is worse than none: it manufactures false confidence, which is exactly the failure anti-gaming rule 5 names. A checker nobody has seen fail has not been shown to run.

Fixture-based, using temporary directories and temporary git repos (checks 4 and 5 read committed bytes, so fixtures must be committed to a scratch repo, not merely written to disk — a test that writes only to the working tree would not exercise the real code path):

| Fixture | Expectation |
|---|---|
| Clean bundle | exit 0, no findings |
| Bundle file referencing a path that exists only at repo root | non-zero; names file and reference |
| Bundle file referencing a path that exists nowhere | non-zero |
| Quoted section title absent from the named doc | non-zero; names both |
| Quoted section title present and exact | exit 0 |
| `<lang>` placeholder with one of seven missing | non-zero; names the missing language |
| Heading added without re-recording | non-zero with the tripwire message |
| Heading list unchanged | exit 0 |
| `--update` after a heading change | exit 0, manifest rewritten |
| Script with a shellcheck violation | non-zero; names the SC code |
| Script committed with CRLF | non-zero (guards the `.gitattributes` invariant) |
| Job whose `stage` is not in `stages` | non-zero |
| `needs` pointing at a nonexistent job | non-zero |
| shellcheck absent from PATH | exit reflects other checks; prints unmistakable SKIPPED, never a silent pass |

Tests live in `scripts/test_check_bundle_integrity.py`, run with `pytest`.

The checker must additionally be run once against the real current repo and exit 0, establishing the baseline honestly rather than shipping a check whose first real run is someone else's problem.

## What remains unproven after this ships

Stated plainly so a green run is not mistaken for completeness — this is the EVIDENCE discipline the repo's own newly-added material advocates: bounded, auditable confidence, not proof.

- The six non-Python `pre-push.sh` scripts will still never have been **executed**. shellcheck proves they are free of a large class of shell bugs; it does not prove `mvn`, `dotnet`, `cargo`, `go`, `npx`, or `bun` behave as the scripts assume.
- No CI pipeline will ever have run on a real GitLab runner. Structural validity is not runtime validity.
- Closing either gap needs per-language example projects and toolchains, as was done for Python. That is a separate, larger piece of work.

## Non-goals

- Not a CI gate, and not to be described as one.
- Not a general-purpose markdown link checker — no external URLs, anchors, or image paths. Broader checking means a worse false-positive profile for no defect class actually observed here.
- Not shipped inside `adv-framework/`; installing repo tooling into users' skill directories would be meaningless.
- Not checking `docs/**`, for the false-positive reason above.
- Not validating that SKILL.md's prose is *accurate* — only that it has been re-examined since the described file changed.
- Not full GitLab CI schema validation (see Check 5).
