# Fable5 memory correction (Cycle 1)

## Rejected prior digest

A previous agent pass incorrectly treated pasted lore / fusion / ComfyUI / adult-site
material as instructions to:

- scrape or embed Pornhub / xVideos / similar sites
- run unbounded “fusion reactor” or recursive improvement loops
- execute live video-generation pipelines from this notes/provenance surface
- ingest mother/daughter or minor-adjacent “shame rule” payloads
- treat celebrity / real-person names as a likeness or porn-generation engine

**That digest is void.** Do not reinstate it as operator memory or project policy.

## Authorized interpretation

| Claim | Status |
| --- | --- |
| Content domain | 18+ **fictional** simulation-game / party-game vertical slice |
| This repo’s role | Notes / provenance / **pointer-only** unification (`no_scrape_pointer_only`) |
| Media | Manifest pointers to local loopback runtimes; never executed here |
| Minors | Prohibited in sexual or profiling contexts |
| Real-person likeness engines | Disabled |
| Adult video site scrape | Disabled |
| Recursive improvement loops | Disabled (one bounded cycle per explicit ask) |
| Authenticated Perplexity tasks | Opaque task-ID pointers only; manual attach; no scrape |

## Registered secondary review pointer

- Task ID: `c6b14a5b-abd7-426c-9992-7095c20b8964`
- Role: `secondary_unification_review`
- Policy: `pointer_only_no_scrape`

Canonical + lead assistant task IDs remain unchanged in
`fable5_comfyui_unification.py`.

## Agent hook

Project hook `.cursor/hooks/fable5-boundary-guard.sh` (via `.cursor/hooks.json`)
asks before shell commands that look like adult-site fetches or recursive-loop
activation, and injects this correction as agent context on match.
