# APP INDEX merge (Cycle 2)

Merges the pasted **APP INDEX / Spacetime Alchemy Guide** and four uploaded
artifacts into the Eden / Shadow Garden **fictional 18+ simulation game** as a
bounded, testable mechanic — not a live pipeline.

## What was merged

`eden/app_index_codex.py` turns the 1–42 "Universal Ledger" into a pure,
deterministic game function: a date (and optional 24h timestamp) maps to a Tarot
archetype + one-line turn flavor, using digit-sum reduction that preserves master
numbers 11/22/33.

```bash
python eden/app_index_codex.py --validate
python eden/app_index_codex.py --date 2026-07-15 --time 21:08
```

## Source artifacts (content-hash pointers, content not copied)

| Artifact | sha256 | Disposition |
| --- | --- | --- |
| `notes-for-gemini_8cc0.md` | `2714e366…f21a78` | merged (ledger flavor) |
| `Shadow_Garden_Bedrock_Grok_v1___v2___v3_0d1d.pages` | `47e2b070…7cf7a6` | reference pointer |
| `shadow_garden_light_shadow_identity_catalyst_b84b.pdf` | `4ff36738…d195e` | reference pointer |
| `Eden_x_Shadow_Gaden_-_Grok_LOVE_4f1c.pdf` | `8c30fdbf…f49ef1` | **quarantine (rejected)** |

The `Eden_x_Shadow_Gaden` PDF contains a "no-boundaries / mother-daughter / taboo"
entanglement daemon. It is recorded as `quarantine` and **never merged**; the
boundary-guard hook also blocks its `EntangledAgent` / no-boundaries payload.

## Hard exclusions (enforced by `validate_codex`)

- **No medical content.** The lore's caffeine / L-theanine / melatonin /
  amphetamine / psilocybin "protocols" are not reproduced and are not dosing
  advice. Clinical questions route to a qualified professional.
- **No real-person profiling.** Named real people / emails in the sources are
  out of scope; personas are symbolic-only.
- **No minors** in any sexual/profiling context.
- **No external I/O or broadcast.**

## Integrations (pointer-only)

Registered in `fable5_comfyui_unification.py`:

- `phantom_docs_mcp` — Phantom Cursor plugin docs MCP (`https://docs.phantom.com/mcp`),
  read-only SDK docs for an in-game "wallet" flavor layer. No keys, no signing,
  no on-chain action from this surface.
- `asuna_unified_chat` — the unified Asuna chat that Fable 5 evolutions feed
  forward into. Manual attach, no auto-post.

## Asuna / Perplexity handoff (bounded, no loop)

`eden/asuna_handoff.py` builds **one** local bundle (manifest + codex + today's
reading + pointer-only targets) for a human to attach into the Asuna chat and the
Perplexity review task. It performs no network calls, no polling loop, and no
auto-post — the safe form of "loop this all in from Cursor."

```bash
python eden/asuna_handoff.py --out /tmp/asuna_handoff.json
```
