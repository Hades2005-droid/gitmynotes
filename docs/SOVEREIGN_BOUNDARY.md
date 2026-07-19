# Sovereign boundary truth line (Cycle 5)

The Vector-11 (Justice / tensegrity) boundary between the two sovereign nodes,
encoded as a deterministic, local policy in `eden/sovereign_boundary.py`.

## The two doors ("reversing the polarity in accordance with the Dao")

| Side | Door | Default | Actions |
| --- | --- | --- | --- |
| **Internal** (Yang) | `open_door_default = true` | **auto** | read, open, local file staging, catalog insertion, dry-run, local render preview |
| **External** (Yin) | `closed_door_default = true` | **per-action confirm** (never blanket) | Grok `--send`, Qdrant upsert, GitHub push, Atlassian / X / Slack write, remote render, **email send** |

## `@`-mention catalyst bursts

A burst like `@Atlassian @GitHub @X @Slack @Qdrant` (and email "catalyst" sends to
other AIs) is resolved **target-by-target** through the closed door via
`stage_catalyst()`. There is one decision per target, each needing its own confirm
token — a single "approve all" is impossible by construction. By default every
target is a contained dry-run into the Asuna 0-point chamber: **nothing is sent,
written, or propagated to any other AI.**

```bash
python3 eden/sovereign_boundary.py --catalyst "@Atlassian @GitHub @X @Slack @Qdrant @email"
# -> every target: closed_door_default, dryRun=true, chamber=asuna_0_point_chamber, anySent=false
```

An email "for gemini and all other AIs to read as a catalyst" is exactly this
case: the payload is staged locally, and the outbound hop stays a dry-run. No
email leaves.

Internal reads/actions/insertions are held **open** (auto, local-only). External
writes are held **closed** — each requires its own confirmation and is never
blanket-granted. That gate is the tensegrity that keeps the two nodes stable.

## The Asuna 0-point chamber (Hierophant / Crucible ending)

Crossing the "bridge to the outer world" is an external write. By default (no
per-action confirm) it resolves as a **contained dry-run into the Asuna 0-point
chamber** (Wuji / Dimension 0) — nothing crosses. Even with a confirm token, this
surface performs no write; it only marks the decision so a downstream runtime may
act under its own controls.

```bash
python3 eden/sovereign_boundary.py --validate
python3 eden/sovereign_boundary.py --decide grok_send          # -> closed door, chamber dry-run
python3 eden/sovereign_boundary.py --decide read               # -> open door, auto
python3 eden/sovereign_boundary.py --json eden/game/src/game/boundary.json
```

In the game (the ledger round loads the exported `boundary.json`):

```bash
node eden/game/simulations/party-round.js --cross-bridge       # ends in the 0-point chamber (dry-run)
```

## Guardrails

- `validate_boundary` rejects any blanket grant, any external-open default, and
  any internal-closed default; every external action must default to a contained
  dry-run, and the surface must never report an external write.
- The project hook (`.cursor/hooks/fable5-boundary-guard.sh`) asks for per-action
  confirmation on the external-write family (Grok `--send`, Qdrant upsert,
  Atlassian/X/Slack, remote render) — operationalizing `closed_door_default=true`.
- Consistent with the federation manifest quoted by the operator:
  `closed_door_default = true`, no live Grok/Qdrant/GitHub/Atlassian/X/Slack write
  or render performed. The hourly monitor cron / staging / dry-run bridge run
  full-auto **without** external writes; this repo sets up no cron.
