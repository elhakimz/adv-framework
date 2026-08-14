# Integrating ADV with Kanban-style Project Management — Reference

## Core principle

The Kanban board should reflect gate results — it never replaces the gates themselves. A card reaching "Done" is a signal derived from the pipeline, not a substitute for it.

## The state mapping

| Pipeline event | Kanban state |
|---|---|
| Card picked up, branch created | To Do → In Progress |
| MR/PR opened | In Progress → In Review |
| All deterministic gates pass | In Review → **Verification Passed** |
| Any gate fails | Card tagged `blocked`, stays in place, comment with which gate failed |
| Change touches a `CODEOWNERS`-protected file | Verification Passed → **Human Gate** (WIP-limited column) |
| Human approves + merges | → Done |
| Escaped bug found later | Auto-creates new card: "Add deterministic gate for X," linked to the incident |

**Human Gate** is the important addition beyond a standard board — most cards skip it (pipeline green → straight to Done); only cards touching the protected surface stop there. An agent should never be the one moving a card out of Human Gate — that's the Kanban-level enforcement of "the agent can't certify its own work."

## Plane.so — native GitLab integration

Plane has a first-party GitLab integration: MR states drive work-item states through a configurable mapping (draft → open → approved → merged) without custom scripting. Map GitLab's "approved" state (only reached after the pipeline is green and any `CODEOWNERS` approval is done) to Plane's "Verification Passed" or "Human Gate cleared" — reserve "Done" for actual merge.

Plane also exposes a REST API (`https://api.plane.so/api/v1/...`), webhooks, and a native MCP server for anything the native integration doesn't cover — e.g. auto-filing a card when the security gate's severity-based blocking fires a Critical finding.

**Note**: Plane is migrating `/issues/` endpoints to `/work-items/` — `/issues/` support ends March 31, 2026. Use `/work-items/` in any new integration code.

Ready-to-use asset: `assets/security/create_security_debt_cards.py` — parses a Trivy JSON report and files Plane work items for Critical/High findings via the `/work-items/` API, with an idempotency check via `external_id`/`external_source` to avoid duplicate cards across repeated pipeline runs.

## Asana — native integration is comment-only, expect to build the glue

GitLab's built-in Asana integration posts commit/MR activity as comments on a linked Asana task via a personal access token — it does not natively drive Asana task state or custom fields the way Plane's GitLab integration does. Building the equivalent state-machine mapping means:

- GitLab project webhooks (pipeline events, MR state changes) → a small relay (serverless function, n8n, Make) → Asana API call that moves the task's section or sets a custom "Verification Status" field.
- Asana's own Rules can only react to changes *within* Asana — they can't watch GitLab directly, so the webhook relay is what feeds the trigger.

## One design rule regardless of tool

Resist adding a column per pipeline stage ("Static," "Build," "Unit"...) — that mirrors the CI log and adds noise. The board only needs to answer: *is this blocked, does it need a human, or is it done.* The pipeline itself remains the place to check which specific gate is failing.
