/**
 * Playable-slice smoke test (node --test).
 *
 * Verifies the three headless sims are deterministic and side-effect free when
 * imported, and that the clock scheduler fires every scheduled event.
 *
 * Run: node --test eden/game/simulations/slice.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { GameSimulation, makeRng, CHARACTERS } from "./run-4.2-game-simulation.js";
import { runClockTest } from "./clock-test.js";
import { runSimulation, seededRandom } from "./nyc-local-dev-simulator.js";

test("four matriarch characters are defined", () => {
  assert.deepEqual(Object.keys(CHARACTERS), ["1", "2", "3", "4"]);
});

test("game sim is deterministic under a fixed seed", () => {
  const a = new GameSimulation(makeRng(42)).run(6000);
  const b = new GameSimulation(makeRng(42)).run(6000);
  assert.deepEqual(a, b);
  assert.ok(a.finalHarmony >= 0 && a.finalHarmony <= 100);
});

test("clock scheduler fires all four scheduled events in order", () => {
  const { fired, finalFrame } = runClockTest(70);
  assert.equal(fired.length, 4);
  assert.equal(finalFrame, 70);
  assert.deepEqual(fired, [
    "Makima Q ends",
    "Seiko E harmony pulse",
    "Momo Phase Shift ends",
    "Big lattice sync event",
  ]);
});

test("nyc simulator is reproducible under a fixed seed", () => {
  const opts = { totalRequests: 40, endpoints: undefined, runs: 1, seed: 42, json: true };
  // Rebuild default endpoints via a fresh parseArgs-free call:
  const withDefaults = { ...opts, endpoints: [
    { path: "/api/v1/auth", baseLatency: 120, variance: 60, errorChance: 0.02 },
    { path: "/api/v1/metrics", baseLatency: 55, variance: 35, errorChance: 0.01 },
    { path: "/api/v1/users", baseLatency: 65, variance: 40, errorChance: 0.03 },
    { path: "/healthz", baseLatency: 4, variance: 3, errorChance: 0.05 },
  ]};
  const r1 = runSimulation(withDefaults);
  const r2 = runSimulation(withDefaults);
  assert.deepEqual(r1, r2);
  assert.ok(typeof seededRandom(1)() === "number");
});
