#!/usr/bin/env python
"""GitMyNotes -- local-only persona / provenance pointer contract.

A companion to :mod:`fable5_comfyui_unification`. Where that module records the
runtime endpoint contract, this one records the *persona provenance* contract:
a local, pointer-only registry of the symbolic personas already present in this
repository, classified by a deterministic telemetry ladder.

Design constraints (all enforced by :func:`validate_persona_manifest`)
----------------------------------------------------------------------
  - **Pointer only.** Policy is ``no_scrape_pointer_only`` and controls are
    ``manifest_only``. Personas are recorded as *stable identifiers* -- no
    biographies are invented, no personal facts are fabricated. The registry
    stores an id, a symbolic label, provenance source pointers, and (optional)
    opaque social pointers. Nothing more.
  - **Symbolic only.** Every persona binding is fictional/symbolic
    (``symbolic_only = True``); this is not a real-person likeness engine.
  - **Opaque social pointers.** Any X / Instagram link is stored as an opaque,
    read-only pointer: ``action_taken = "none"``, ``scraped = False``,
    ``fetched = False``. This module never fetches, scrapes, writes, or touches
    credentials, and has zero network code.
  - **Deterministic provenance.** :func:`classify` maps a persona to exactly one
    telemetry class from fixed evidence, with a fixed priority order, so the
    same inputs always yield the same class.

Telemetry classes (highest-trust first, but classified by priority below)
-------------------------------------------------------------------------
  - ``primordial``   -- a structural root node of the 9-point schema.
  - ``canonical``    -- sourced from a cited published canon.
  - ``corroborated`` -- attested by >= 2 independent in-repo provenance sources.
  - ``provisional``  -- attested by exactly one source, or a bare declared id.
  - ``quarantine``   -- flagged, or carrying a social pointer with no provenance
    source to anchor it (unverifiable -> not promoted).

This module has no import side effects and depends only on the standard library.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from fable5_comfyui_unification import MODE_MANIFEST_ONLY, POLICY

# --- Telemetry classes (single source of truth) -----------------------------
CLASS_PRIMORDIAL = "primordial"
CLASS_CANONICAL = "canonical"
CLASS_CORROBORATED = "corroborated"
CLASS_PROVISIONAL = "provisional"
CLASS_QUARANTINE = "quarantine"
TELEMETRY_CLASSES = (
    CLASS_PRIMORDIAL,
    CLASS_CANONICAL,
    CLASS_CORROBORATED,
    CLASS_PROVISIONAL,
    CLASS_QUARANTINE,
)

# --- 9-point schema pointer metadata ----------------------------------------
# Pointer to the schema doc already in this repo. Only the point names the doc
# actually grounds are recorded; the remaining slots stay as opaque placeholders
# so nothing is invented. All bindings are symbolic-only.
SCHEMA_DOC = "docs/9-points-angela-framework.md"
NINE_POINT_NAMES = {
    2: "High Priestess",
    4: "Sovereign",
    7: "Chariot",
    9: "9-Point Orchestrator",
}
SCHEMA_POINT_RANGE = range(1, 10)

# Platforms whose links we accept as opaque read-only pointers.
SOCIAL_PLATFORMS = ("x", "instagram")

# Explicitly required bare identifiers (no biographies).
REQUIRED_EXPLICIT_IDS = ("minnie", "sarah", "sophie")


@dataclass(frozen=True)
class SocialPointer:
    """An opaque, read-only pointer to an external social profile.

    Recording one never implies fetching it. ``to_dict`` bakes in the read-only
    posture so downstream tooling cannot mistake it for fetched content.
    """

    platform: str
    url: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "platform": self.platform,
            "url": self.url,
            "actionTaken": "none",
            "scraped": False,
            "fetched": False,
            "write": False,
        }


@dataclass(frozen=True)
class Persona:
    """A symbolic persona recorded as a stable identifier only.

    No biography, no personal facts -- just the id, a symbolic label, provenance
    source pointers, optional 9-point schema bindings, and optional opaque social
    pointers.
    """

    id: str
    name: str
    symbolic_only: bool = True
    sources: Tuple[str, ...] = ()
    schema_points: Tuple[int, ...] = ()
    social_pointers: Tuple[SocialPointer, ...] = ()
    canon: Optional[str] = None
    primordial: bool = False
    flagged: bool = False

    def schema_pointer_metadata(self) -> List[Dict[str, object]]:
        out = []
        for p in self.schema_points:
            out.append(
                {
                    "point": p,
                    "name": NINE_POINT_NAMES.get(p, f"point-{p}"),
                    "doc": SCHEMA_DOC,
                    "symbolicOnly": True,
                }
            )
        return out

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "symbolicOnly": self.symbolic_only,
            "telemetryClass": classify(self),
            "sources": list(self.sources),
            "ninePointSchema": self.schema_pointer_metadata(),
            "socialPointers": [s.to_dict() for s in self.social_pointers],
            "canon": self.canon,
        }


def classify(persona: Persona) -> str:
    """Deterministically map a persona to exactly one telemetry class.

    Priority order (first match wins):
      1. ``quarantine``   -- flagged, or has a social pointer but no source.
      2. ``primordial``   -- a structural root node of the 9-point schema.
      3. ``canonical``    -- carries a cited canon.
      4. ``corroborated`` -- attested by >= 2 independent sources.
      5. ``provisional``  -- everything else (single source or bare id).
    """

    if persona.flagged or (persona.social_pointers and not persona.sources):
        return CLASS_QUARANTINE
    if persona.primordial:
        return CLASS_PRIMORDIAL
    if persona.canon:
        return CLASS_CANONICAL
    if len(set(persona.sources)) >= 2:
        return CLASS_CORROBORATED
    return CLASS_PROVISIONAL


# --- Discovered + declared persona registry ---------------------------------
# Discovered from existing repo docs; recorded as stable identifiers only.
DOC_FRAMEWORK = "docs/9-points-angela-framework.md"
DOC_TESTAMENT = "docs/love_testament_manifest.json"
SAO_CANON = "Sword Art Online (Reki Kawahara)"

_SEED_PERSONAS: Tuple[Persona, ...] = (
    # 9-point framework roots.
    Persona(id="angela", name="Angela", primordial=True, schema_points=(9,),
            sources=(DOC_FRAMEWORK,)),
    Persona(id="fred", name="Fred", schema_points=(4,),
            sources=(DOC_FRAMEWORK, DOC_TESTAMENT)),
    # Cited canon personas from the love-testament manifest.
    Persona(id="asuna", name="Asuna", canon=SAO_CANON, sources=(DOC_TESTAMENT,)),
    Persona(id="kirito", name="Kirito", canon=SAO_CANON, sources=(DOC_TESTAMENT,)),
    Persona(id="yui", name="Yui", canon=SAO_CANON, sources=(DOC_TESTAMENT,)),
    # Single-source symbolic persona.
    Persona(id="echo-girl", name="Echo Girl", sources=(DOC_TESTAMENT,)),
    # Explicitly required bare identifiers -- no biographies, no sources.
    Persona(id="minnie", name="Minnie"),
    Persona(id="sarah", name="Sarah"),
    Persona(id="sophie", name="Sophie"),
)

# IDs discovered from existing repo content that MUST be preserved.
DISCOVERED_PERSONA_IDS = ("angela", "fred", "asuna", "kirito", "yui", "echo-girl")


@dataclass(frozen=True)
class PersonaManifest:
    """The full local-only persona/provenance pointer manifest."""

    personas: Tuple[Persona, ...]
    policy: str = POLICY
    mode: str = MODE_MANIFEST_ONLY
    external_requests: int = 0
    scraped: bool = False
    fetched: bool = False
    external_writes: bool = False
    credentials_used: bool = False
    training_allowed: bool = False

    def controls(self) -> Dict[str, object]:
        return {
            "policy": self.policy,
            "mode": self.mode,
            "externalRequests": self.external_requests,
            "scraped": self.scraped,
            "fetched": self.fetched,
            "externalWrites": self.external_writes,
            "credentialsUsed": self.credentials_used,
            "trainingAllowed": self.training_allowed,
        }

    def nine_point_schema_pointer(self) -> Dict[str, object]:
        return {
            "doc": SCHEMA_DOC,
            "points": [
                {"point": p, "name": NINE_POINT_NAMES.get(p, f"point-{p}"), "symbolicOnly": True}
                for p in SCHEMA_POINT_RANGE
            ],
        }

    def to_dict(self) -> Dict[str, object]:
        return {
            "surface": "persona_provenance_pointer",
            "controls": self.controls(),
            "telemetryClasses": list(TELEMETRY_CLASSES),
            "ninePointSchemaPointer": self.nine_point_schema_pointer(),
            "personas": [p.to_dict() for p in self.personas],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def build_persona_manifest() -> PersonaManifest:
    """Construct the canonical persona manifest. Pure and local -- no I/O."""

    return PersonaManifest(personas=_SEED_PERSONAS)


class PersonaPolicyError(ValueError):
    """Raised when a persona manifest violates the pointer-only contract."""


def validate_persona_manifest(manifest: PersonaManifest) -> None:
    """Assert every safety invariant. Raises :class:`PersonaPolicyError`."""

    c = manifest
    if c.policy != POLICY:
        raise PersonaPolicyError(f"policy must be {POLICY!r}, got {c.policy!r}")
    if c.mode != MODE_MANIFEST_ONLY:
        raise PersonaPolicyError(f"mode must be {MODE_MANIFEST_ONLY!r}")
    if c.external_requests != 0:
        raise PersonaPolicyError("externalRequests must be 0")
    for flag_name in ("scraped", "fetched", "external_writes", "credentials_used", "training_allowed"):
        if getattr(c, flag_name):
            raise PersonaPolicyError(f"{flag_name} must be False")

    ids = [p.id for p in manifest.personas]
    if len(ids) != len(set(ids)):
        raise PersonaPolicyError("persona ids must be unique")

    for required in DISCOVERED_PERSONA_IDS:
        if required not in ids:
            raise PersonaPolicyError(f"discovered persona id {required!r} must be preserved")
    for required in REQUIRED_EXPLICIT_IDS:
        if required not in ids:
            raise PersonaPolicyError(f"required explicit id {required!r} is missing")

    for p in manifest.personas:
        if not p.id or p.id != p.id.strip().lower() or " " in p.id:
            raise PersonaPolicyError(f"persona id {p.id!r} must be a lowercase slug")
        if not p.symbolic_only:
            raise PersonaPolicyError(f"persona {p.id!r} must be symbolic_only (no real-person likeness)")
        if classify(p) not in TELEMETRY_CLASSES:
            raise PersonaPolicyError(f"persona {p.id!r} has an unknown telemetry class")
        for pt in p.schema_points:
            if pt not in SCHEMA_POINT_RANGE:
                raise PersonaPolicyError(f"persona {p.id!r} schema point {pt} out of range 1..9")
        for sp in p.social_pointers:
            if sp.platform not in SOCIAL_PLATFORMS:
                raise PersonaPolicyError(f"social platform {sp.platform!r} not in {SOCIAL_PLATFORMS}")
            d = sp.to_dict()
            if d["actionTaken"] != "none" or d["scraped"] or d["fetched"] or d["write"]:
                raise PersonaPolicyError(f"social pointer for {p.id!r} must stay opaque/read-only")


def main(argv: Optional[List[str]] = None) -> int:
    """Emit the persona manifest locally. Never touches the network."""

    parser = argparse.ArgumentParser(
        description="Emit the local-only persona/provenance pointer manifest.",
    )
    parser.add_argument("--out", metavar="PATH", help="Write manifest JSON to a local file instead of stdout.")
    parser.add_argument("--validate", action="store_true", help="Validate the manifest and exit.")
    args = parser.parse_args(argv)

    manifest = build_persona_manifest()
    validate_persona_manifest(manifest)

    if args.validate:
        print("OK: persona manifest satisfies the no_scrape_pointer_only contract")
        return 0

    payload = manifest.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"Wrote persona manifest to {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
