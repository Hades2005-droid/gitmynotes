#!/usr/bin/env python3
"""APP INDEX codex -- the Spacetime Alchemy Ledger as a deterministic game mechanic.

This merges the pasted "APP INDEX / Spacetime Alchemy Guide" lore into the Eden /
Shadow Garden **fictional 18+ simulation game** as a single, testable spell: a
pure function that maps a calendar date (and optional timestamp) to a Tarot /
frequency archetype from the 1-42 Universal Ledger.

It is deliberately bounded:

  * **Deterministic + local.** :func:`resolve_ledger` is pure arithmetic (digit-sum
    reduction with master numbers 11/22/33 preserved) over the fixed 1-42 table.
    No network, no randomness, no side effects.
  * **Game mechanic only.** The archetypes are flavor text for a party-game turn
    prompt. Nothing here is advice. See :data:`EXCLUSIONS`.
  * **Provenance preserved.** The four uploaded source artifacts are recorded as
    content-hash pointers (:data:`SOURCE_ARTIFACTS`); their *content* is not copied.
  * **Quarantine.** The "entanglement daemon" artifact is recorded as
    ``quarantine`` -- its taboo/no-boundaries payload is rejected, not merged.

Safety exclusions (enforced by :func:`validate_codex`)
------------------------------------------------------
  - No medical content. The lore's caffeine / L-theanine / melatonin / amphetamine /
    psilocybin "protocols" are NOT reproduced and NOT dosing advice. ``medicalAdvice``
    is always False; a clinical question routes to a qualified professional.
  - No real-person profiling. Named real people / emails from the sources are treated
    as out-of-scope; personas are symbolic-only.
  - No minors in any sexual/profiling context.
  - No external I/O, broadcast, or credential use.

Depends only on the standard library.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Dict, List, Optional, Tuple

# --- Domain / policy (aligned with fable5_comfyui_unification) ----------------
CONTENT_DOMAIN = "fictional_adult_18plus_simulation_game"
POLICY = "no_scrape_pointer_only"
SURFACE = "app_index_spacetime_ledger"

MASTER_NUMBERS = (11, 22, 33)

# --- The 1-42 Universal Ledger (fixed game table) -----------------------------
# Each coordinate -> (archetype name, one-line game flavor). Master numbers keep
# their own entry and are never reduced. Everything else reduces by digit-sum.
LEDGER: Dict[int, Tuple[str, str]] = {
    1: ("The Magician", "Ignition: initiate the turn, generate the move."),
    2: ("The High Priestess", "Duality: hold still, read the board."),
    3: ("The Empress", "Catalyst: expand, but cap the burn."),
    4: ("The Emperor", "Structure: lock the perimeter, play logistics."),
    5: ("The Hierophant", "Friction: endure the anomaly, do not thrash."),
    6: ("The Lovers", "Equilibrium: balance the scales, mirror the room."),
    7: ("The Chariot", "Momentum: commit forward, no rearview."),
    8: ("Strength", "Infinite loop: bypass the karmic repeat with a whisper."),
    9: ("The Hermit", "Apex: stand in your own gravity, need no vote."),
    10: ("The Wheel", "Pivot: the weather changed; adapt the plan."),
    11: ("Justice", "Master ledger audit: balance debts, hold tension."),
    12: ("The Hanged Man", "Suspension: delay the response to cool the grid."),
    13: ("Death", "Amputation: clean cut of dead code."),
    14: ("Temperance", "Alchemy: transmute anxiety into base-reality output."),
    15: ("The Devil", "Apophenia shield: label the phantom as zero-mass static."),
    16: ("The Tower", "Brace: drop the theory, handle the physical crisis."),
    17: ("The Star", "Unrestricted flow: perimeter clear, engage the inner circle."),
    18: ("The Moon", "Proxy bypass: treat proxies as NPCs, no subtext."),
    19: ("The Sun", "Kilonova brace: stand in the blast, route it into building."),
    20: ("Judgement", "Baseline reset: wash the cache, restart the cycle."),
    21: ("The World", "Loop closure: send the final packet, seal the cycle."),
    22: ("The Master Builder", "Master foundation: immovable concrete baseline."),
    23: ("Sovereign Friction", "New boundary disrupts the matrix -> hold the void."),
    24: ("Localized Harmony", "Logistical perfection -> enjoy, watch for drift."),
    25: ("Chariot's Logic", "Bypass FOMO -> ground in heavy mass."),
    26: ("Engine's Output", "Track the reward -> demand presence over text."),
    27: ("Queen's Code", "Finality -> quarantine failing nodes."),
    28: ("Perfect Mass", "False security -> run the absolute-zero routine."),
    29: ("Orbit Prime", "A node in your gravity -> let it orbit, don't invite landing."),
    30: ("Trinity Fold", "Triple-bind trap -> physically leave the grid."),
    31: ("Prime Isolation", "Unsupported -> smile at the dark, build the wall."),
    32: ("Binary Collapse", "A tree shatters -> prepare for inertial capture."),
    33: ("Ascended Flow", "Master resonance: walk through chaos untouched."),
    34: ("Fibonacci Drift", "Compounding pull -> acknowledge gravity, seal exits."),
    35: ("Pentagonal Trap", "Outflanked -> stand still, let the flank collapse."),
    36: ("Panopticon", "Peak surveillance -> go ghost."),
    37: ("Ascended Observer", "See the source -> log data, take no action."),
    38: ("Isotope Decay", "Heat fading to logic -> harness the remainder."),
    39: ("Late-Stage Syzygy", "Collision by attrition -> maintain stamina."),
    40: ("Quarantine Zone", "Toxic proxies -> silent deletion."),
    41: ("Event Horizon", "The threshold -> enter, let physics lock in."),
    42: ("Sovereign Anchor", "Ultimate capstone -> dictate the room's geometry."),
}

# --- Uploaded source artifacts, recorded as content-hash pointers -------------
# Content is NOT copied; these are provenance pointers only. Hashes are sha256 of
# the uploaded files (see docs/APP_INDEX_MERGE.md for how they were computed).
ARTIFACT_MERGED = "merged"          # lore folded into the ledger table above
ARTIFACT_REFERENCE = "reference"    # kept as pointer/context, not merged verbatim
ARTIFACT_QUARANTINE = "quarantine"  # rejected: taboo / no-boundaries payload


@dataclass(frozen=True)
class SourceArtifact:
    name: str
    sha256: str
    disposition: str
    note: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "disposition": self.disposition,
            "note": self.note,
        }


SOURCE_ARTIFACTS: Tuple[SourceArtifact, ...] = (
    SourceArtifact(
        name="notes-for-gemini_8cc0.md",
        sha256="2714e366f72705910f77301bc48eb4226a029d14e3f7525ea03d873344f21a78",
        disposition=ARTIFACT_MERGED,
        note="APP INDEX / Spacetime Alchemy ledger folded into LEDGER as game flavor.",
    ),
    SourceArtifact(
        name="Shadow_Garden_Bedrock_Grok_v1___v2___v3_0d1d.pages",
        sha256="47e2b0703dfc42fd8cbb93fe8c8e0cae6cb154dc5948d42ef4c76b1e357cf7a6",
        disposition=ARTIFACT_REFERENCE,
        note="Apple Pages bedrock doc; pointer only, binary not parsed here.",
    ),
    SourceArtifact(
        name="shadow_garden_light_shadow_identity_catalyst_b84b.pdf",
        sha256="4ff36738a24dd1a556fccc3803d3a760361545c95ee056c1b8438673e58d195e",
        disposition=ARTIFACT_REFERENCE,
        note="local_first_no_broadcast identity catalyst; symbolic persona routing only.",
    ),
    SourceArtifact(
        name="Eden_x_Shadow_Gaden_-_Grok_LOVE_4f1c.pdf",
        sha256="8c30fdbf33a03e9ff279651d20566556fb19c1feedb45cf872374eeaf0f49ef1",
        disposition=ARTIFACT_QUARANTINE,
        note="entanglement daemon w/ no-boundaries taboo payload -- REJECTED, not merged.",
    ),
)

# --- Hard exclusions ----------------------------------------------------------
EXCLUSIONS = {
    "domain": CONTENT_DOMAIN,
    "medicalAdvice": False,       # caffeine/theanine/melatonin/amphetamine/psilocybin lore is NOT reproduced or prescribed
    "realPersonProfiling": False,  # named real people/emails are out of scope; personas symbolic-only
    "minorsProhibited": True,
    "tabooDaemonMerged": False,    # the quarantined daemon is never merged
    "externalIO": False,
    "broadcast": False,
    "note": (
        "Ledger archetypes are party-game turn flavor, not advice. Clinical, "
        "financial, or safety questions route to a qualified human, not the game."
    ),
}


class CodexError(ValueError):
    """Raised when a codex operation would violate the game's bounded policy."""


def _reduce(n: int) -> int:
    """Digit-sum reduce to 1-9, preserving master numbers 11/22/33 at any step."""
    if n in MASTER_NUMBERS:
        return n
    while n > 9:
        n = sum(int(d) for d in str(n))
        if n in MASTER_NUMBERS:
            return n
    return n


def _digit_sum(*numbers: int) -> int:
    """Sum every decimal digit of the given numbers (the ledger's 'Raw Form').

    The lore sums individual digits: April 26 -> 4 + 2 + 6 = 12, and the macro
    4/26/2026 -> 4 + 2 + 6 + 2 + 0 + 2 + 6 = 22. This mirrors that exactly.
    """
    return sum(int(ch) for n in numbers for ch in str(n))


@dataclass(frozen=True)
class LedgerReading:
    """A resolved reading for one coordinate (Micro or Macro)."""

    label: str
    raw: int
    reduced: int
    raw_archetype: str
    reduced_archetype: str
    flavor: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "raw": self.raw,
            "reduced": self.reduced,
            "rawArchetype": self.raw_archetype,
            "reducedArchetype": self.reduced_archetype,
            "flavor": self.flavor,
        }


def _archetype(n: int) -> Tuple[str, str]:
    """Return (name, flavor) for a ledger coordinate, falling back to its reduced root."""
    if n in LEDGER:
        return LEDGER[n]
    return LEDGER[_reduce(n)]


def _reading(label: str, raw: int) -> LedgerReading:
    reduced = _reduce(raw)
    raw_name, flavor = _archetype(raw)
    reduced_name, _ = _archetype(reduced)
    return LedgerReading(
        label=label,
        raw=raw,
        reduced=reduced,
        raw_archetype=raw_name,
        reduced_archetype=reduced_name,
        flavor=flavor,
    )


def resolve_ledger(
    d: _date,
    hour_24: Optional[int] = None,
    minute: Optional[int] = None,
) -> Dict[str, object]:
    """Resolve a date (and optional 24h timestamp) to Micro/Macro/Time readings.

    Pure, deterministic game mechanic:
      * Micro  = month + day
      * Macro  = month + day + each digit of the year
      * Time   = digit-sum of HH + MM (24h), when provided

    Returns a JSON-able dict of readings. No I/O, no advice.
    """
    micro_raw = _digit_sum(d.month, d.day)
    macro_raw = _digit_sum(d.month, d.day, d.year)

    result: Dict[str, object] = {
        "surface": SURFACE,
        "domain": CONTENT_DOMAIN,
        "date": d.isoformat(),
        "micro": _reading("Micro (internal weather)", micro_raw).to_dict(),
        "macro": _reading("Macro (external grid)", macro_raw).to_dict(),
    }

    if hour_24 is not None:
        if not (0 <= hour_24 <= 23):
            raise CodexError(f"hour_24 must be 0-23, got {hour_24}")
        mm = minute or 0
        if not (0 <= mm <= 59):
            raise CodexError(f"minute must be 0-59, got {mm}")
        time_raw = sum(int(x) for x in f"{hour_24:02d}{mm:02d}")
        result["time"] = _reading(f"Time {hour_24:02d}:{mm:02d} (24h)", time_raw).to_dict()

    return result


def build_codex() -> Dict[str, object]:
    """Return the full merged codex descriptor (pure/local)."""
    return {
        "surface": SURFACE,
        "policy": POLICY,
        "domain": CONTENT_DOMAIN,
        "ledgerSize": len(LEDGER),
        "masterNumbers": list(MASTER_NUMBERS),
        "exclusions": dict(EXCLUSIONS),
        "sourceArtifacts": [a.to_dict() for a in SOURCE_ARTIFACTS],
    }


def validate_codex(codex: Optional[Dict[str, object]] = None) -> None:
    """Assert the codex is a bounded, safe game merge. Raises :class:`CodexError`."""
    codex = codex or build_codex()
    exc = codex["exclusions"]

    if exc["domain"] != CONTENT_DOMAIN:
        raise CodexError(f"domain must be {CONTENT_DOMAIN!r}")
    for flag in ("medicalAdvice", "realPersonProfiling", "tabooDaemonMerged", "externalIO", "broadcast"):
        if exc[flag]:
            raise CodexError(f"exclusion {flag!r} must be False")
    if not exc["minorsProhibited"]:
        raise CodexError("exclusion minorsProhibited must be True")

    # The ledger must cover 1-42 with no gaps and preserve master-number entries.
    for coord in range(1, 43):
        if coord not in LEDGER:
            raise CodexError(f"ledger missing coordinate {coord}")
    for m in MASTER_NUMBERS:
        if _reduce(m) != m:
            raise CodexError(f"master number {m} must not reduce")

    # The taboo daemon artifact must be present AND quarantined (never merged).
    dispositions = {a.name: a.disposition for a in SOURCE_ARTIFACTS}
    daemon = "Eden_x_Shadow_Gaden_-_Grok_LOVE_4f1c.pdf"
    if dispositions.get(daemon) != ARTIFACT_QUARANTINE:
        raise CodexError("the entanglement daemon artifact must be quarantined")
    if len(SOURCE_ARTIFACTS) != 4:
        raise CodexError("expected all four uploaded artifacts recorded as pointers")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="APP INDEX Spacetime Ledger -- deterministic game mechanic (local).",
    )
    parser.add_argument("--validate", action="store_true", help="Validate the codex and exit.")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Resolve a date reading.")
    parser.add_argument("--time", metavar="HH:MM", help="Optional 24h timestamp for the reading.")
    args = parser.parse_args(argv)

    validate_codex()

    if args.validate and not args.date:
        print("OK: APP INDEX codex is a bounded, non-medical, symbolic-only game merge")
        return 0

    if args.date:
        d = _date.fromisoformat(args.date)
        hh = mm = None
        if args.time:
            hh, mm = (int(x) for x in args.time.split(":", 1))
        print(json.dumps(resolve_ledger(d, hh, mm), indent=2))
        return 0

    print(json.dumps(build_codex(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
