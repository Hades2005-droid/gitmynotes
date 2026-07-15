/**
 * 4.2 Shadow Jing Garden — playable round layer.
 *
 * Turns the APP INDEX Spacetime ledger (date -> Tarot archetype) into the turn
 * prompt that frames one bounded party-game round, then resolves the round from
 * the headless mechanics sim. Deterministic and local: same date + seed + anchor
 * always yields the same outcome. No network, no media, no external writes.
 *
 * The ledger table is loaded from src/game/ledger.json, which is exported from
 * the canonical Python codex (eden/app_index_codex.py --ledger-json) so the game
 * and the codex never diverge.
 */

import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

import { GameSimulation, makeRng, CHARACTERS } from "../../simulations/run-4.2-game-simulation.js";

const _here = dirname(fileURLToPath(import.meta.url));
const LEDGER = JSON.parse(readFileSync(join(_here, "ledger.json"), "utf8"));
const MASTER_NUMBERS = new Set(LEDGER.masterNumbers);

/** Digit-sum reduce to 1-9, preserving master numbers 11/22/33 (mirrors codex). */
export function reduce(n) {
  if (MASTER_NUMBERS.has(n)) return n;
  while (n > 9) {
    n = String(n).split("").reduce((a, d) => a + Number(d), 0);
    if (MASTER_NUMBERS.has(n)) return n;
  }
  return n;
}

function digitSum(...nums) {
  return nums.reduce((acc, n) => acc + String(n).split("").reduce((a, d) => a + Number(d), 0), 0);
}

function archetype(coord) {
  const entry = LEDGER.ledger[String(coord)] || LEDGER.ledger[String(reduce(coord))];
  return entry || { name: "Unknown", flavor: "" };
}

/** Map a Date to the round's Micro/Macro turn prompt from the ledger. */
export function dateTurnPrompt(d) {
  const month = d.getUTCMonth() + 1;
  const day = d.getUTCDate();
  const year = d.getUTCFullYear();
  const microRaw = digitSum(month, day);
  const macroRaw = digitSum(month, day, year);
  const micro = archetype(microRaw);
  const macro = archetype(macroRaw);
  return {
    date: d.toISOString().slice(0, 10),
    micro: { raw: microRaw, reduced: reduce(microRaw), ...micro },
    macro: { raw: macroRaw, reduced: reduce(macroRaw), ...macro },
  };
}

// Which anchor matriarch a Micro reduced-frequency emphasizes (1-4 cycle).
function anchorForFrequency(reduced) {
  const idx = ((reduced - 1) % 4) + 1;
  return idx;
}

/**
 * Play one complete, bounded round.
 *
 * Returns a JSON-able result with: the turn prompt, the anchor matriarch, the
 * mechanics outcome, and an explainable resolution (win/hold/lose) against a
 * harmony threshold — a visible end state the UI (or a test) can assert on.
 */
export function startRound({ date = new Date(), seed = 42, durationMs = 12000, anchor } = {}) {
  const prompt = dateTurnPrompt(date);
  const chosenAnchor = anchor || anchorForFrequency(prompt.micro.reduced);

  const sim = new GameSimulation(makeRng(seed));
  sim.currentChar = chosenAnchor;
  const outcome = sim.run(durationMs);

  // Explainable resolution: master-number Micro days raise the bar (bigger stakes).
  const threshold = MASTER_NUMBERS.has(prompt.micro.raw) ? 70 : 50;
  let resolution = "hold";
  if (outcome.finalHarmony >= threshold + 20) resolution = "win";
  else if (outcome.finalHarmony < threshold) resolution = "lose";

  return {
    schema: "shadow_jing.party_round.v1",
    domain: LEDGER.domain,
    turnPrompt: prompt,
    anchor: { id: chosenAnchor, name: CHARACTERS[chosenAnchor].name, glyph: CHARACTERS[chosenAnchor].glyph },
    outcome,
    threshold,
    resolution,
  };
}

/** Play N sequential rounds (restart / new-round support). Deterministic per seed. */
export function playRounds({ date = new Date(), seed = 42, rounds = 3, durationMs = 12000 } = {}) {
  const results = [];
  for (let i = 0; i < rounds; i++) {
    results.push(startRound({ date, seed: seed + i, durationMs }));
  }
  const tally = results.reduce(
    (acc, r) => ((acc[r.resolution] = (acc[r.resolution] || 0) + 1), acc),
    {}
  );
  return { rounds: results, tally };
}
