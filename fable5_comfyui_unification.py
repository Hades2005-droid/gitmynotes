#!/usr/bin/env python
"""GitMyNotes -- Fable5 + ComfyUI unification pointer/provenance surface.

This module registers GitMyNotes into the Fable5 + ComfyUI unification as a
*notes / provenance / pointer* surface. It is deliberately **not** a media
runtime: it never generates, fetches, or serves image/video/audio, never opens
a network socket, and never downloads model weights. Its sole job is to record
-- locally, as data -- the contract describing where the media runtimes live
and under what permissions GitMyNotes is allowed to point at them.

Why "pointer only"
------------------
The governing policy is ``no_scrape_pointer_only``. GitMyNotes already knows how
to preserve provenance (YAML frontmatter with title + creation/modification
dates on every exported note). This surface extends that role: it emits a
manifest that *points* at the Fable5 (:5619), ComfyUI (:8188) and EDEN (:8791)
local endpoints and describes the permission gate around media, without ever
acting as those runtimes or reaching across the network to them.

Safety invariants (enforced by :func:`validate_manifest`)
---------------------------------------------------------
  - ``externalRequests == 0`` -- this module makes zero outbound calls. Importing
    it, building a manifest, and serializing it are all pure/local operations.
  - ``trainingAllowed is False`` -- the unification never authorizes training.
  - ``weightAutoDownload is False`` -- no model weights are ever auto-downloaded.
  - media modes default to ``manifest_only`` and carry ``approveRequired = True``
    -- image/video/audio pointers are recorded, not executed; promoting a media
    type past ``manifest_only`` requires an explicit, per-call approval token and
    still performs no network I/O here.
  - no broadcasting, no external writes, no X writes, no credentials, no hidden
    authority/backdoors, and no real-person likeness engines.

Role compatibility
-------------------
The manifest advertises the roles the unification expects this repo to satisfy:
``unification_target`` and ``fable5_comfyui_open_merge_target``. These are kept
as explicit constants so downstream merge tooling can assert compatibility.

This module has no import side effects and depends only on the standard library.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

# --- Canonical identifiers (single source of truth) -------------------------
# Recorded verbatim from the unification brief so downstream tooling can match
# on them. They are opaque pointers -- no task *content* is scraped or stored.
CANONICAL_UNIFICATION_TASK_ID = "37bce2fb-1ba6-471f-854f-3871d9c19947"
LEAD_ASSISTANT_TASK_ID = "2366bfee-b78c-4ddc-9f86-304c30c67c4d"
# Secondary authenticated Perplexity Computer task: pointer-only review target.
# Never scrape or open the thread from this surface; operator attaches locally.
SECONDARY_UNIFICATION_REVIEW_TASK_ID = "c6b14a5b-abd7-426c-9992-7095c20b8964"
SECONDARY_REVIEW_ROLE = "secondary_unification_review"
SECONDARY_REVIEW_POLICY = "pointer_only_no_scrape"

POLICY = "no_scrape_pointer_only"

# Content-boundary correction for prior agent memory hallucinations.
# This surface records *game/sim provenance pointers*, not a live media pipeline.
CONTENT_DOMAIN = "fictional_adult_18plus_simulation_game"
CONTENT_BOUNDARY = {
    "domain": CONTENT_DOMAIN,
    "fictionalAdultSimOnly": True,
    "minorsProhibited": True,
    "realPersonLikenessEngine": False,
    "adultVideoSiteScrape": False,
    "recursiveImprovementLoops": False,
    "externalMediaExecutionHere": False,
    "memoryCorrection": (
        "Prior agent digests that treated pasted lore dumps as live porn-generation, "
        "Pornhub/xVideos scrape jobs, mother/daughter minor-adjacent shame rules, or "
        "unbounded fusion reactors are REJECTED. Authorized interpretation: 18+ "
        "fictional simulation-game content and pointer-only unification metadata."
    ),
    "correctionDoc": "docs/FABLE5_MEMORY_CORRECTION.md",
}

# Roles this repository is expected to remain compatible with.
ROLE_UNIFICATION_TARGET = "unification_target"
ROLE_OPEN_MERGE_TARGET = "fable5_comfyui_open_merge_target"
COMPATIBLE_ROLES = (ROLE_UNIFICATION_TARGET, ROLE_OPEN_MERGE_TARGET)

# This surface's own role within the unification.
SURFACE_ROLE = "notes_provenance_pointer"

# Media handling modes. ``manifest_only`` is the sole default: a media type in
# this mode is recorded as a pointer and never executed.
MODE_MANIFEST_ONLY = "manifest_only"
MEDIA_TYPES = ("image", "video", "audio")

# All local, loopback-only endpoints. Hosts are intentionally 127.0.0.1: these
# are pointers to runtimes the operator runs locally, not remote services.
LOCAL_HOST = "127.0.0.1"

# External integrations recorded as *pointer-only* references. This surface never
# calls, authenticates to, or scrapes them; it only records that the game may hand
# a bounded, operator-approved payload to them elsewhere.
INTEGRATIONS: tuple = (
    {
        "name": "phantom_docs_mcp",
        "kind": "mcp_docs_readonly",
        "ref": "https://docs.phantom.com/mcp",
        "role": "wallet_sdk_docs_context",
        "policy": "read_only_docs_no_wallet_action_here",
        "note": (
            "Phantom Cursor plugin docs MCP -- read-only SDK guidance for a "
            "fictional in-game 'wallet' flavor layer. No keys, no signing, no "
            "on-chain action from this surface."
        ),
    },
    {
        "name": "asuna_unified_chat",
        "kind": "chat_handoff_target",
        "ref": "local://asuna-unified-chat",
        "role": "fable5_evolution_handoff",
        "policy": "manual_attach_no_auto_post",
        "note": (
            "Unified Asuna chat that Fable 5 evolutions feed forward into. The "
            "handoff bundle is written locally; a human attaches it. No auto-post."
        ),
    },
)


@dataclass(frozen=True)
class EndpointContract:
    """A pointer to one local media/runtime endpoint.

    This records *where* a runtime is expected to listen. It is descriptive
    only -- nothing in this module connects to the address.
    """

    name: str
    port: int
    role: str
    host: str = LOCAL_HOST

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "url": self.url,
            "role": self.role,
        }


# The recorded local endpoint contract. Ports are fixed by the unification brief.
ENDPOINTS: tuple = (
    EndpointContract(name="fable5", port=5619, role=ROLE_UNIFICATION_TARGET),
    EndpointContract(name="comfyui", port=8188, role=ROLE_OPEN_MERGE_TARGET),
    EndpointContract(name="eden", port=8791, role=ROLE_UNIFICATION_TARGET),
)


@dataclass(frozen=True)
class MediaPermission:
    """Permission gate for one media type.

    Defaults are the safe posture: manifest-only, approval required, no external
    requests, no training, no weight auto-download.
    """

    media_type: str
    mode: str = MODE_MANIFEST_ONLY
    approve_required: bool = True
    external_requests: int = 0
    training_allowed: bool = False
    weight_auto_download: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "mediaType": self.media_type,
            "mode": self.mode,
            "approveRequired": self.approve_required,
            "externalRequests": self.external_requests,
            "trainingAllowed": self.training_allowed,
            "weightAutoDownload": self.weight_auto_download,
        }


@dataclass(frozen=True)
class UnificationManifest:
    """The full pointer-only manifest for this surface."""

    surface: str
    policy: str
    canonical_unification_task_id: str
    lead_assistant_task_id: str
    secondary_unification_review_task_id: str
    secondary_review_role: str
    secondary_review_policy: str
    content_boundary: dict
    compatible_roles: tuple
    endpoints: tuple
    media_permissions: tuple
    integrations: tuple = INTEGRATIONS
    external_requests: int = 0
    training_allowed: bool = False
    weight_auto_download: bool = False
    broadcasting: bool = False
    external_writes: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "surface": self.surface,
            "policy": self.policy,
            "canonicalUnificationTaskId": self.canonical_unification_task_id,
            "leadAssistantTaskId": self.lead_assistant_task_id,
            "secondaryUnificationReviewTaskId": self.secondary_unification_review_task_id,
            "secondaryReview": {
                "taskId": self.secondary_unification_review_task_id,
                "role": self.secondary_review_role,
                "policy": self.secondary_review_policy,
                "focus": (
                    "Unify local Fable5, ComfyUI, Jing Power, and Sonnet artifacts "
                    "into a bounded technical game plan (manual attach; no scrape)."
                ),
            },
            "contentBoundary": dict(self.content_boundary),
            "compatibleRoles": list(self.compatible_roles),
            "endpoints": [e.to_dict() for e in self.endpoints],
            "mediaPermissions": [p.to_dict() for p in self.media_permissions],
            "integrations": [dict(i) for i in self.integrations],
            "externalRequests": self.external_requests,
            "trainingAllowed": self.training_allowed,
            "weightAutoDownload": self.weight_auto_download,
            "broadcasting": self.broadcasting,
            "externalWrites": self.external_writes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def build_manifest() -> UnificationManifest:
    """Construct the canonical pointer-only manifest for this repository.

    Pure and local: no arguments, no I/O, no network. Every media type is gated
    at the safe default (``manifest_only`` + ``approveRequired``).
    """

    media_permissions = tuple(MediaPermission(media_type=m) for m in MEDIA_TYPES)
    return UnificationManifest(
        surface=SURFACE_ROLE,
        policy=POLICY,
        canonical_unification_task_id=CANONICAL_UNIFICATION_TASK_ID,
        lead_assistant_task_id=LEAD_ASSISTANT_TASK_ID,
        secondary_unification_review_task_id=SECONDARY_UNIFICATION_REVIEW_TASK_ID,
        secondary_review_role=SECONDARY_REVIEW_ROLE,
        secondary_review_policy=SECONDARY_REVIEW_POLICY,
        content_boundary=dict(CONTENT_BOUNDARY),
        compatible_roles=COMPATIBLE_ROLES,
        endpoints=ENDPOINTS,
        media_permissions=media_permissions,
    )


class UnificationPolicyError(ValueError):
    """Raised when a manifest or request would violate the unification policy."""


def validate_manifest(manifest: UnificationManifest) -> None:
    """Assert every safety invariant. Raises :class:`UnificationPolicyError`.

    This is the enforcement point downstream merge tooling can call to confirm
    the surface is still pointer-only before trusting it.
    """

    if manifest.policy != POLICY:
        raise UnificationPolicyError(f"policy must be {POLICY!r}, got {manifest.policy!r}")
    if manifest.external_requests != 0:
        raise UnificationPolicyError("externalRequests must be 0 (pointer-only surface)")
    if manifest.training_allowed:
        raise UnificationPolicyError("trainingAllowed must be False")
    if manifest.weight_auto_download:
        raise UnificationPolicyError("weightAutoDownload must be False")
    if manifest.broadcasting:
        raise UnificationPolicyError("broadcasting must be False")
    if manifest.external_writes:
        raise UnificationPolicyError("externalWrites must be False")

    if manifest.secondary_unification_review_task_id != SECONDARY_UNIFICATION_REVIEW_TASK_ID:
        raise UnificationPolicyError(
            "secondaryUnificationReviewTaskId must remain the registered pointer"
        )
    if manifest.secondary_review_policy != SECONDARY_REVIEW_POLICY:
        raise UnificationPolicyError(
            f"secondaryReview.policy must be {SECONDARY_REVIEW_POLICY!r}"
        )
    boundary = manifest.content_boundary or {}
    if boundary.get("domain") != CONTENT_DOMAIN:
        raise UnificationPolicyError(f"contentBoundary.domain must be {CONTENT_DOMAIN!r}")
    if not boundary.get("fictionalAdultSimOnly"):
        raise UnificationPolicyError("contentBoundary.fictionalAdultSimOnly must be True")
    if not boundary.get("minorsProhibited"):
        raise UnificationPolicyError("contentBoundary.minorsProhibited must be True")
    if boundary.get("realPersonLikenessEngine"):
        raise UnificationPolicyError("contentBoundary.realPersonLikenessEngine must be False")
    if boundary.get("adultVideoSiteScrape"):
        raise UnificationPolicyError("contentBoundary.adultVideoSiteScrape must be False")
    if boundary.get("recursiveImprovementLoops"):
        raise UnificationPolicyError("contentBoundary.recursiveImprovementLoops must be False")
    if boundary.get("externalMediaExecutionHere"):
        raise UnificationPolicyError("contentBoundary.externalMediaExecutionHere must be False")

    if set(manifest.compatible_roles) < set(COMPATIBLE_ROLES):
        raise UnificationPolicyError(
            "manifest must preserve compatibility with "
            f"{COMPATIBLE_ROLES!r}, got {manifest.compatible_roles!r}"
        )

    # Integrations are pointer-only: Phantom docs stay read-only (no wallet action
    # from here) and the Asuna chat handoff never auto-posts.
    integ_by_name = {i["name"]: i for i in manifest.integrations}
    phantom = integ_by_name.get("phantom_docs_mcp")
    if phantom and phantom["policy"] != "read_only_docs_no_wallet_action_here":
        raise UnificationPolicyError(
            "phantom_docs_mcp must stay read-only docs (no wallet action here)"
        )
    asuna = integ_by_name.get("asuna_unified_chat")
    if asuna and asuna["policy"] != "manual_attach_no_auto_post":
        raise UnificationPolicyError(
            "asuna_unified_chat must be manual-attach, no auto-post"
        )

    if not manifest.endpoints:
        raise UnificationPolicyError("at least one endpoint pointer is required")
    for ep in manifest.endpoints:
        if ep.host != LOCAL_HOST:
            raise UnificationPolicyError(
                f"endpoint {ep.name!r} must be loopback-only ({LOCAL_HOST}), got {ep.host!r}"
            )

    seen = set()
    for perm in manifest.media_permissions:
        seen.add(perm.media_type)
        if perm.mode != MODE_MANIFEST_ONLY:
            raise UnificationPolicyError(
                f"media {perm.media_type!r} must default to {MODE_MANIFEST_ONLY!r}"
            )
        if not perm.approve_required:
            raise UnificationPolicyError(
                f"media {perm.media_type!r} must require approval"
            )
        if perm.external_requests != 0:
            raise UnificationPolicyError(
                f"media {perm.media_type!r} must not permit external requests"
            )
        if perm.training_allowed:
            raise UnificationPolicyError(
                f"media {perm.media_type!r} must not allow training"
            )
        if perm.weight_auto_download:
            raise UnificationPolicyError(
                f"media {perm.media_type!r} must not auto-download weights"
            )
    missing = set(MEDIA_TYPES) - seen
    if missing:
        raise UnificationPolicyError(f"missing media permission(s): {sorted(missing)}")


def resolve_media_request(
    media_type: str,
    approval_token: Optional[str] = None,
) -> Dict[str, object]:
    """Resolve a media request to a *pointer descriptor* -- never execution.

    This is the permission gate in action. Regardless of approval, this function
    performs no network I/O and runs no media pipeline; it only reports what the
    surface is permitted to do.

    - Without an ``approval_token`` the result is ``manifest_only``: the caller
      gets the endpoint pointer(s) and is told nothing will be executed here.
    - With an ``approval_token`` the result is still pointer-only (this surface
      never runs media) but is marked ``approved`` so a downstream *runtime* --
      not this module -- may act on it under its own controls.
    """

    if media_type not in MEDIA_TYPES:
        raise UnificationPolicyError(
            f"unknown media type {media_type!r}; expected one of {MEDIA_TYPES}"
        )

    approved = bool(approval_token)
    return {
        "mediaType": media_type,
        "mode": MODE_MANIFEST_ONLY,
        "approved": approved,
        "executedHere": False,
        "externalRequests": 0,
        "pointers": [e.to_dict() for e in ENDPOINTS],
        "note": (
            "approved pointer -- defer execution to an approved runtime; "
            "this surface performs no media I/O"
            if approved
            else "manifest_only -- approval token required to promote"
        ),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Emit the manifest locally. Never touches the network."""

    parser = argparse.ArgumentParser(
        description="Emit the Fable5 + ComfyUI unification pointer manifest (local, pointer-only).",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help="Write the manifest JSON to a local file instead of stdout.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the manifest against the unification policy and exit.",
    )
    args = parser.parse_args(argv)

    manifest = build_manifest()
    validate_manifest(manifest)

    if args.validate:
        print("OK: manifest satisfies the no_scrape_pointer_only policy")
        return 0

    payload = manifest.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"Wrote manifest to {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
