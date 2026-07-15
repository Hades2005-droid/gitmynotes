#!/usr/bin/env python3
"""Sovereign boundary truth line -- the two-door federation policy.

Encodes the Vector-11 (Justice / tensegrity) boundary between the two sovereign
nodes as a deterministic, local policy:

  * **Internal reads / actions / insertions** -> ``open_door_default = true``.
    Reads, local file staging, catalog insertions, dry-runs, and local render
    previews are auto-approved. This is the Yang side: generative, in-repo, and
    fully local -- nothing leaves the machine.
  * **External writes** -> ``closed_door_default = true``. Grok ``--send``, Qdrant
    upsert, GitHub push, Atlassian / X / Slack posts, and remote render are the
    Yin side: they cross the bridge to the outer world and therefore require a
    **per-action confirm**. They are *never* blanket-granted -- that gate is the
    tensegrity that keeps the two nodes stable.

"Reversing the polarity in accordance with the eternal Dao" means exactly this:
internal is held open (auto) and external is held closed (confirm). The dividing
line is the boundary truth line, and the terminal state at the bridge is the
**Asuna 0-point chamber** (Wuji / Dimension 0): a contained end state where an
external write resolves as a dry-run unless a per-action confirm token is present.

This module makes zero network calls, holds no credentials, and performs no
writes. It only *classifies* and *decides*; a downstream runtime -- never this
module -- would act on a confirmed decision under its own controls.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional

CONTENT_DOMAIN = "fictional_adult_18plus_simulation_game"
POLICY = "no_scrape_pointer_only"
SURFACE = "sovereign_boundary_truth_line"
TENSEGRITY_VECTOR = 11  # Justice / balance

# Internal (Yang) actions: open door, auto-approved, local-only.
INTERNAL_ACTIONS = (
    "read",
    "open",
    "local_file_staging",
    "catalog_insertion",
    "dry_run",
    "local_render_preview",
)

# External (Yin) actions: closed door, per-action confirm, never blanket.
EXTERNAL_ACTIONS = (
    "grok_send",
    "qdrant_upsert",
    "github_push",
    "atlassian_write",
    "x_write",
    "slack_write",
    "remote_render",
)

OPEN_DOOR = "open_door_default"     # internal default
CLOSED_DOOR = "closed_door_default"  # external default

CHAMBER = {
    "name": "asuna_0_point_chamber",
    "archetype": "Wuji / Dimension 0 / Absolute Vacuum",
    "meaning": (
        "The contained terminal state at the bridge to the outer world. External "
        "writes resolve here as a dry-run unless a per-action confirm is present; "
        "by default nothing crosses."
    ),
    "externalWriteByDefault": False,
}


class BoundaryError(ValueError):
    """Raised when the boundary policy would be violated (e.g. a blanket grant)."""


def build_boundary() -> Dict[str, object]:
    """Return the full two-door boundary policy (pure/local, JSON-able)."""
    return {
        "surface": SURFACE,
        "policy": POLICY,
        "domain": CONTENT_DOMAIN,
        "tensegrityVector": TENSEGRITY_VECTOR,
        "internal": {
            "door": OPEN_DOOR,
            "default": "auto",
            "openDoorDefault": True,
            "actions": list(INTERNAL_ACTIONS),
            "note": "Yang side: reads/actions/insertions are auto, local-only.",
        },
        "external": {
            "door": CLOSED_DOOR,
            "default": "confirm",
            "closedDoorDefault": True,
            "blanketGrant": False,
            "perActionConfirm": True,
            "actions": list(EXTERNAL_ACTIONS),
            "note": "Yin side: outbound writes require per-action confirm; never blanket.",
        },
        "chamber": dict(CHAMBER),
    }


def classify(action: str) -> str:
    """Return 'internal' or 'external' for a known action. Unknown -> external.

    Unknown actions are treated as external (closed door) on purpose: the safe
    default is to require confirmation, never to auto-open.
    """
    if action in INTERNAL_ACTIONS:
        return "internal"
    if action in EXTERNAL_ACTIONS:
        return "external"
    return "external"


def decide(action: str, confirm_token: Optional[str] = None) -> Dict[str, object]:
    """Decide how an action resolves under the boundary. Never performs it.

    - Internal action  -> door open, auto, allowed, no external effect.
    - External action  -> door closed. Without a per-action ``confirm_token`` it
      resolves as a **dry-run into the Asuna 0-point chamber** (nothing crosses).
      With a token it is marked ``confirmed`` so a downstream runtime *may* act --
      but this module still performs no write and opens no socket.
    """
    side = classify(action)
    if side == "internal":
        return {
            "action": action,
            "side": "internal",
            "door": OPEN_DOOR,
            "allowed": True,
            "requiresConfirm": False,
            "dryRun": False,
            "externalWritePerformed": False,
            "chamber": None,
        }

    confirmed = bool(confirm_token)
    return {
        "action": action,
        "side": "external",
        "door": CLOSED_DOOR,
        "allowed": confirmed,           # only a per-action confirm allows crossing
        "requiresConfirm": True,
        "blanketGrant": False,
        "dryRun": not confirmed,
        # This surface never writes, even when confirmed -- defer to a runtime.
        "externalWritePerformed": False,
        "chamber": None if confirmed else CHAMBER["name"],
        "note": (
            "confirmed per-action -- defer the actual write to an approved runtime"
            if confirmed
            else "closed door -- dry-run into the Asuna 0-point chamber; nothing crosses"
        ),
    }


def validate_boundary(boundary: Optional[Dict[str, object]] = None) -> None:
    """Assert the tensegrity invariants. Raises :class:`BoundaryError`."""
    boundary = boundary or build_boundary()

    if boundary["domain"] != CONTENT_DOMAIN:
        raise BoundaryError(f"domain must be {CONTENT_DOMAIN!r}")

    internal = boundary["internal"]
    external = boundary["external"]

    if not internal["openDoorDefault"]:
        raise BoundaryError("internal must be open_door_default = true")
    if internal["default"] != "auto":
        raise BoundaryError("internal default must be 'auto'")

    if not external["closedDoorDefault"]:
        raise BoundaryError("external must be closed_door_default = true")
    if external["default"] != "confirm":
        raise BoundaryError("external default must be 'confirm'")
    if external["blanketGrant"]:
        raise BoundaryError("external writes must never be blanket-granted")
    if not external["perActionConfirm"]:
        raise BoundaryError("external writes must require per-action confirm")

    # An internal action must never be classifiable as external and vice-versa.
    overlap = set(internal["actions"]) & set(external["actions"])
    if overlap:
        raise BoundaryError(f"internal/external action overlap: {sorted(overlap)}")

    # Every external action must resolve to a dry-run by default (no token).
    for action in external["actions"]:
        d = decide(action)
        if d["allowed"] or not d["dryRun"] or d["externalWritePerformed"]:
            raise BoundaryError(f"external action {action!r} must default to a contained dry-run")
        if d["chamber"] != CHAMBER["name"]:
            raise BoundaryError(f"external action {action!r} must land in the 0-point chamber by default")

    # Even confirmed, this surface performs no write.
    if decide("github_push", confirm_token="ok")["externalWritePerformed"]:
        raise BoundaryError("this surface must never perform an external write, even when confirmed")

    if boundary["chamber"]["externalWriteByDefault"]:
        raise BoundaryError("chamber must not perform external writes by default")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sovereign boundary truth line -- two-door federation policy (local).",
    )
    parser.add_argument("--validate", action="store_true", help="Validate the policy and exit.")
    parser.add_argument("--json", metavar="PATH", help="Write the boundary policy JSON to a file.")
    parser.add_argument("--decide", metavar="ACTION", help="Show how one action resolves.")
    parser.add_argument("--confirm", metavar="TOKEN", help="Per-action confirm token for --decide.")
    args = parser.parse_args(argv)

    boundary = build_boundary()
    validate_boundary(boundary)

    if args.decide:
        print(json.dumps(decide(args.decide, args.confirm), indent=2, sort_keys=True))
        return 0

    if args.json:
        payload = json.dumps(boundary, indent=2, sort_keys=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"Wrote sovereign boundary policy to {args.json}")
        return 0

    if args.validate:
        print(
            "OK: internal open_door_default=true (auto); external closed_door_default=true "
            "(per-action confirm, no blanket) -> Asuna 0-point chamber"
        )
        return 0

    print(json.dumps(boundary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
