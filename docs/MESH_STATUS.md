# Grok/xAI mesh readiness cue (Cycle 6)

`eden/mesh_status.py` is an **opt-in, offline playtest cue** — "is the Grok/xAI
lane ready?" — for the party-round slice. It is not core play, and it makes no
network calls.

## What it reads (all local, deterministic)

| Reader | Source | Surfaced |
| --- | --- | --- |
| `grok_cli_status()` | `grok --version` (local CLI, only if on PATH) | present / path / version line |
| `xai_env_ready()` | env var **names** (`XAI_API_KEY`) | booleans keyed by name — **never the value** |
| `jing_power_pointer()` | `~/ShadowGarden/live/spacetime_alchemy/jing_power_latest.json` | metadata fields only |
| `asuna_point0_pointer()` | `~/ShadowGarden/live/spacetime_alchemy/github_asuna_point0_latest.json` | schema / generated_at / phase |

`mesh_status()` aggregates them and reports `grokLaneReady = (grok present AND
XAI_API_KEY name set)`.

```bash
python3 eden/mesh_status.py            # prints the readiness JSON
```

## Guarantees (enforced by `tests/test_mesh_status.py`)

- **No network.** No `socket`/`urllib`/`requests`/`http.client`; `grok --version`
  is a local, offline command run only when the CLI is on PATH.
- **Secret values never leak.** `xai_env_ready` reports only booleans keyed by env
  var *name*; a test sets `XAI_API_KEY` to a sentinel and asserts it never appears
  in the output.
- **Metadata-only + graceful absence.** Pointer readers surface only whitelisted
  top-level fields and return `{ok: false}` when a file is missing or unpar05sable
  (which is the case in this cloud workspace — `~/ShadowGarden` isn't mounted).

## Pipeline ingestion

`eden/asuna_handoff.py` includes `mesh_status()` as the bundle's `meshReadiness`
field, so the Fable5 → Perplexity → Asuna-0 handoff carries the lane cue. Under the
sovereign boundary this is an **internal open-door read** (`mesh_readiness_read`):
auto, local, no external write.
