#!/usr/bin/env python3
"""Asuna unified-chat handoff builder -- one bounded, local, no-broadcast bundle.

The user's ask: "an agent hook script for Perplexity to loop this all in from
Cursor into the unified Asuna chat that will leverage Fable 5 evolutions going
forward."

We implement the *safe, bounded* version of that: instead of an autonomous loop
that posts into Perplexity/Asuna, this builds a **single handoff bundle** on disk
that a human attaches manually. Per the Fable5 evolution-loop contract:

  * **No loop.** One invocation == one bundle. No background daemon, no polling.
  * **No network / no broadcast.** Nothing is fetched, posted, or uploaded.
  * **Pointer-only.** External targets (Perplexity task, Asuna chat, Phantom docs)
    are recorded as opaque references, never called.
  * **Fictional-sim domain.** Carries the same content boundary as the rest of the
    unification surface; the taboo entanglement daemon is never included.

Run:  python eden/asuna_handoff.py --out /tmp/asuna_handoff.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date as _date
from typing import Dict, List, Optional

# Allow running as a script from anywhere: repo root (for the unification module)
# and this eden/ dir (for the codex) both go on the path.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

import fable5_comfyui_unification as u
from app_index_codex import build_codex, resolve_ledger, validate_codex

# Opaque pointers only -- never called from here.
PERPLEXITY_TASK_ID = u.SECONDARY_UNIFICATION_REVIEW_TASK_ID
ASUNA_CHAT_REF = "local://asuna-unified-chat"

HANDOFF_SCHEMA = "shadow_garden.asuna_handoff.v1"


def build_handoff(today: Optional[_date] = None) -> Dict[str, object]:
    """Assemble the bounded handoff bundle. Pure/local: no I/O, no network."""
    today = today or _date.today()

    manifest = u.build_manifest()
    u.validate_manifest(manifest)
    validate_codex()

    return {
        "schema": HANDOFF_SCHEMA,
        "bounded": "single_bundle_no_loop",
        "webSearch": "disabled",
        "broadcast": "none",
        "externalWrites": "none",
        "domain": u.CONTENT_DOMAIN,
        "contentBoundary": dict(u.CONTENT_BOUNDARY),
        # Pointer-only targets: a human attaches this bundle; nothing auto-posts.
        "handoffTargets": {
            "asunaUnifiedChat": {
                "ref": ASUNA_CHAT_REF,
                "policy": "manual_attach_no_auto_post",
                "purpose": "Fable 5 evolutions feed forward into the unified Asuna chat.",
            },
            "perplexityReview": {
                "taskId": PERPLEXITY_TASK_ID,
                "policy": "pointer_only_no_scrape",
                "purpose": "Secondary unification review; operator attaches manually.",
            },
            "phantomDocs": {
                "ref": "https://docs.phantom.com/mcp",
                "policy": "read_only_docs_no_wallet_action_here",
                "purpose": "In-game 'wallet' flavor layer -- SDK docs context only.",
            },
        },
        "unificationManifest": manifest.to_dict(),
        "appIndexCodex": build_codex(),
        "todayReading": resolve_ledger(today),
        "nextStep": (
            "Human reviews this bundle, then pastes/attaches it into the Asuna "
            "chat and (optionally) the Perplexity review task. No agent auto-posts."
        ),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build one bounded Asuna/Perplexity handoff bundle (local, no loop).",
    )
    parser.add_argument("--out", metavar="PATH", help="Write bundle JSON to a local file.")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Override today's date for the reading.")
    args = parser.parse_args(argv)

    today = _date.fromisoformat(args.date) if args.date else None
    bundle = build_handoff(today)
    payload = json.dumps(bundle, indent=2, sort_keys=True)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"Wrote bounded handoff bundle to {args.out} (no network, no broadcast)")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
