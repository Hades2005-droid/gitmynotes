# Asana Bootstrap Record — GitMyNotes

**Date:** 2026-07-08
**Branch:** `claude/nww-asana-connector-2gst3u`
**Account tier:** Free (portfolios + custom fields unavailable)

## Live GIDs (bootstrapped)

| Object | Name | GID |
|--------|------|-----|
| Workspace | (frederickpr10@gmail.com) | `1216280230062995` |
| Project | GitMyNotes Sync Pipeline | `1216393172829085` |
| Seed task | Baseline metrics — GitMyNotes Sync Pipeline | `1216393467845621` |

Project: https://app.asana.com/1/1216280230062995/project/1216393172829085

## Mode: free-tier fallback

The workspace is on Asana's **free tier**, where **portfolios** (Advanced only)
and **custom fields** (Starter+) are not available. The connector therefore runs
in `NWW_FREE_TIER_FALLBACK=true` mode:

- No portfolio is created; `ASANA_PORTFOLIO_ID` is left unset.
- Metrics are written into the **task description** plus a fenced
  **`Metrics JSON`** block (schema `nww.metrics.v1`) rather than custom fields.
- The six planned fields — Resonance Score, Technique Mastery,
  Copy Technique Success, Soul Alignment, Last Reported, Metrics JSON — are
  carried as keys inside that JSON block.

## Upgrade path

On upgrade to a paid plan:
1. Create the 6 custom fields and attach them to project `1216393172829085`.
2. Record the field GIDs in `.env` (add `ASANA_CUSTOM_FIELD_*`).
3. Flip `ASANA_TIER=starter` (or higher) and `NWW_FREE_TIER_FALLBACK=false`.
4. The existing project + task GIDs remain valid — no re-bootstrap needed.

## Not a Jira replacement

Asana reporting is **additive**. It does not fork or replace any existing
workflow; disable it entirely with `DISABLE_ASANA=false`.
