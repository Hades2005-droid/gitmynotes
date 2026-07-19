#!/usr/bin/env python3
"""Discord Developer Platform x Perplexity unification -- pointer catalog only.

Mirrors the operator's terminal brief as a *local, pointer-only* catalog. It
records which Discord platform doc "lanes" map to which local game bridge, and
the phase status of each -- WITHOUT making any Discord API call, requiring any
token, or posting anywhere.

Hard invariants (enforced by :func:`validate_unify`)
----------------------------------------------------
  - **No network / no tokens.** ``externalRequests == 0``. The Discord webhook
    stays ``ARMED_AWAITING_TOKEN`` until the operator puts a URL in ``.env`` and
    explicitly runs the live bridge elsewhere; this module never sends.
  - **No auto-broadcast.** ``broadcast is False``. The Perplexity central task is
    an opaque pointer; nothing is scraped or posted to it.
  - **Social SDK deferred.** The ``social_layer`` lane requires explicit approval
    and stays ``deferred`` here.
  - **Fictional-sim domain.** Same content boundary as the rest of the surface.

Depends only on the standard library.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional

CONTENT_DOMAIN = "fictional_adult_18plus_simulation_game"
POLICY = "no_scrape_pointer_only"
SURFACE = "discord_pplx_unify"

# Official index the operator pulled; recorded as a pointer, not fetched here.
DISCORD_DOCS_INDEX = "https://docs.discord.com/llms.txt"
# Central Perplexity task -- opaque pointer, no scrape (matches the unification).
PERPLEXITY_CENTRAL_TASK_ID = "2366bfee-b78c-4ddc-9f86-304c30c67c4d"

WEBHOOK_MODE = "ARMED_AWAITING_TOKEN"  # never LIVE from this module

# Doc lanes -> local mapping + phase. Pure descriptive catalog.
LANES = (
    {
        "lane": "webhooks",
        "docsFocus": "platform webhooks + webhook resource",
        "localMapping": "discord_bridge (primary)",
        "phase": "MERGED_LOCAL",
        "status": WEBHOOK_MODE,
    },
    {
        "lane": "bots_apps",
        "docsFocus": "bots, first app, application commands",
        "localMapping": "optional bot + channel id",
        "phase": "commands_wired",
        "status": "optional",
    },
    {
        "lane": "activities_party",
        "docsFocus": "Activities / multiplayer / local dev",
        "localMapping": "party_round + Fable5 :5619 (later)",
        "phase": "docs_only_until_smoke_green",
        "status": "research",
    },
    {
        "lane": "social_layer",
        "docsFocus": "Social SDK / rich presence",
        "localMapping": "deferred",
        "phase": "deferred",
        "status": "needs_explicit_approval",
    },
    {
        "lane": "policy_safety",
        "docsFocus": "ToS, rate limits, OAuth",
        "localMapping": "always on",
        "phase": "always_on",
        "status": "enforced",
    },
)


class DiscordUnifyError(ValueError):
    """Raised when the Discord/PPLX unify catalog would break its bounded policy."""


def build_unify() -> Dict[str, object]:
    """Return the pointer-only Discord x Perplexity unify catalog (pure/local)."""
    return {
        "surface": SURFACE,
        "policy": POLICY,
        "domain": CONTENT_DOMAIN,
        "discordDocsIndex": DISCORD_DOCS_INDEX,
        "perplexityCentralTaskId": PERPLEXITY_CENTRAL_TASK_ID,
        "webhookMode": WEBHOOK_MODE,
        "externalRequests": 0,
        "broadcast": False,
        "tokensRequired": False,
        "lanes": [dict(l) for l in LANES],
        "centralAttach": [
            "PERPLEXITY_CONTEXT_BEDROCK.md",
            "fable5-compact.json",
            "DISCORD_PPLX_UNIFY.md",
            "DISCORD_BRIDGE_STATUS.json (optional)",
        ],
        "goLiveNote": (
            "To go live on Discord the operator puts DISCORD_WEBHOOK_URL in "
            "~/ShadowGarden/.env and runs the bridge THERE. This surface never "
            "sends, scrapes, or posts."
        ),
    }


def validate_unify(unify: Optional[Dict[str, object]] = None) -> None:
    """Assert the bounded, pointer-only invariants. Raises :class:`DiscordUnifyError`."""
    unify = unify or build_unify()

    if unify["domain"] != CONTENT_DOMAIN:
        raise DiscordUnifyError(f"domain must be {CONTENT_DOMAIN!r}")
    if unify["externalRequests"] != 0:
        raise DiscordUnifyError("externalRequests must be 0 (no Discord API calls here)")
    if unify["broadcast"]:
        raise DiscordUnifyError("broadcast must be False (no auto-post)")
    if unify["tokensRequired"]:
        raise DiscordUnifyError("tokensRequired must be False")
    if unify["webhookMode"] != WEBHOOK_MODE:
        raise DiscordUnifyError(f"webhookMode must stay {WEBHOOK_MODE!r} in this surface")

    lanes = {l["lane"]: l for l in unify["lanes"]}
    if lanes.get("social_layer", {}).get("phase") != "deferred":
        raise DiscordUnifyError("social_layer lane must stay deferred (needs approval)")
    if lanes.get("policy_safety", {}).get("phase") != "always_on":
        raise DiscordUnifyError("policy_safety lane must be always_on")


def render_markdown(unify: Optional[Dict[str, object]] = None) -> str:
    """Render the DISCORD_PPLX_UNIFY.md handoff (paste target for central PPLX)."""
    unify = unify or build_unify()
    lines = [
        "# Discord Developer Platform x Perplexity unify",
        "",
        f"- Domain: {unify['domain']}",
        f"- Policy: {unify['policy']} (no Discord API calls, no tokens, no broadcast)",
        f"- Discord docs index: {unify['discordDocsIndex']}",
        f"- Perplexity central task: {unify['perplexityCentralTaskId']} (pointer only)",
        f"- Webhook mode: {unify['webhookMode']}",
        "",
        "## Lanes",
        "",
        "| Lane | Docs focus | Local mapping | Phase |",
        "| --- | --- | --- | --- |",
    ]
    for l in unify["lanes"]:
        lines.append(f"| {l['lane']} | {l['docsFocus']} | {l['localMapping']} | {l['phase']} |")
    lines += [
        "",
        "## For central Perplexity chat, attach:",
        "",
    ]
    for item in unify["centralAttach"]:
        lines.append(f"- {item}")
    lines += ["", f"> {unify['goLiveNote']}", ""]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discord x Perplexity unify catalog (local, pointer-only, no tokens).",
    )
    parser.add_argument("--validate", action="store_true", help="Validate and exit.")
    parser.add_argument("--markdown", action="store_true", help="Emit the handoff markdown.")
    parser.add_argument("--out", metavar="PATH", help="Write JSON catalog to a local file.")
    args = parser.parse_args(argv)

    unify = build_unify()
    validate_unify(unify)

    if args.validate and not (args.markdown or args.out):
        print("OK: Discord/PPLX unify is pointer-only (no API calls, no tokens, no broadcast)")
        return 0
    if args.markdown:
        print(render_markdown(unify))
        return 0

    payload = json.dumps(unify, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"Wrote Discord/PPLX unify catalog to {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
