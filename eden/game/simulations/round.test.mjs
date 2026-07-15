/**
 * Playable-round convergence test (node --test).
 *
 * Asserts the date -> ledger archetype turn prompt drives a bounded round with a
 * visible resolution, that runs are deterministic per seed, that restart works,
 * and that the JS ledger mirrors the canonical Python-exported ledger.json.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

import { startRound, playRounds, reduce, dateTurnPrompt } from "../src/game/round.js";

const _here = dirname(fileURLToPath(import.meta.url));
const LEDGER = JSON.parse(readFileSync(join(_here, "../src/game/ledger.json"), "utf8"));

test("ledger.json is the canonical 1-42 table", () => {
  assert.equal(Object.keys(LEDGER.ledger).length, 42);
  assert.equal(LEDGER.ledger["1"].name, "The Magician");
  assert.equal(LEDGER.ledger["42"].name, "Sovereign Anchor");
  assert.deepEqual(LEDGER.masterNumbers, [11, 22, 33]);
});

test("reduce preserves master numbers and mirrors the codex", () => {
  assert.equal(reduce(11), 11);
  assert.equal(reduce(22), 22);
  assert.equal(reduce(21), 3);
  assert.equal(reduce(19), 1);
});

test("date turn prompt resolves Micro and Macro archetypes", () => {
  // 4/26/2026: micro 12->3, macro 22 (master)
  const p = dateTurnPrompt(new Date("2026-04-26T12:00:00Z"));
  assert.equal(p.micro.raw, 12);
  assert.equal(p.micro.reduced, 3);
  assert.equal(p.macro.raw, 22);
  assert.equal(p.macro.reduced, 22);
  assert.equal(p.macro.name, "The Master Builder");
});

test("a round completes with a visible resolution", () => {
  const r = startRound({ date: new Date("2026-07-15T12:00:00Z"), seed: 42 });
  assert.ok(["win", "hold", "lose"].includes(r.resolution));
  assert.ok(r.outcome.finalHarmony >= 0 && r.outcome.finalHarmony <= 100);
  assert.ok(r.anchor.id >= 1 && r.anchor.id <= 4);
  assert.equal(r.turnPrompt.date, "2026-07-15");
});

test("rounds are deterministic per seed", () => {
  const a = startRound({ date: new Date("2026-07-15T12:00:00Z"), seed: 7 });
  const b = startRound({ date: new Date("2026-07-15T12:00:00Z"), seed: 7 });
  assert.deepEqual(a, b);
});

test("restart plays N rounds and tallies resolutions", () => {
  const { rounds, tally } = playRounds({ date: new Date("2026-07-15T12:00:00Z"), seed: 42, rounds: 3 });
  assert.equal(rounds.length, 3);
  const total = Object.values(tally).reduce((a, b) => a + b, 0);
  assert.equal(total, 3);
});
